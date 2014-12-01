#!/usr/bin/python

import pygame
import time
import flask
import multiprocessing
import Queue
import socket
import sys
import threading
from flask import Flask
from flask import request
from constants import *
import utils
import os
import pickle
import collections
from replica_failover_service import ReplicaFailoverService

# listens for master commands, plays/pauses/skips as needed
class ReplicaMusicService(multiprocessing.Process):
    def __init__(self, playlist_queue, ip_addr):
        multiprocessing.Process.__init__(self)
        self._stop = threading.Event()
        self._playlist_queue = playlist_queue
        self._ip = ip_addr
        self._song_hashes = self.initialize_song_hashes()
        self._current_song = None

        # Shared state between failover service
        self._pygame_lock = threading.Lock()
        self._in_recovery = False # TODO: Need a rw lock here?

    # TODO: may need to remove .DS_STORE etc
    def initialize_song_hashes(self):
        song_hashes = set([])
        if not os.path.exists(MUSIC_DIR):
            os.makedirs(MUSIC_DIR)
        for file_name in os.listdir(MUSIC_DIR):
            if len(file_name) >= len(EXT):
                song_hashes.add(file_name[:-len(EXT)])
        return song_hashes

    # stop playing current music and play whatever master dictates
    # Also used as unpause command
    # route: /play (POST)
    def play(self):
        # Parse payload
        content = utils.unserialize_response(request.get_data())
        command_epoch = content['command_epoch']
        start_time_microsec = content['start_time']
        # Not sure when it would be -1 but double check
        assert(start_time_microsec >= 0)
        master_offset = 0
        if 'offset' in content:
            master_offset = int(content['offset'])
        # May be None, need to call .stop() then
        song_hash = content['song_hash']

        failover_mode_resp = utils.format_rpc_response(\
                            False, PLAY, {}, \
                            msg='Replica in recovery mode', \
                            command_epoch=command_epoch)

        # Case 1: Failover Mode already
        # Short circuit crucial to not starve failover_service process on
        # pygame_mixer object
        # Case 2: Song hash doesn't exist
        if self._in_recovery or not \
        os.path.exists(utils.get_music_path(song_hash)):
            self._in_recovery = True
            return utils.serialize_response(failover_mode_resp)

        # Could be in recovery mode at this point, wait for it to finish
        # before moving on (True)
        with self._pygame_lock:
            replica_offset = int(round(pygame.mixer.music.get_pos()))
            # Ideally if pygame.mixer.music.play(offset) works then these would not be
            # errors but alas such is life and we must go into recovery
            if master_offset > 0: 
                # Case 3: Unpause command, but songs do not match
                # Case 4: Unpause command, but master's offset is way in future
                #         This should not happen since master determines
                #         offset as max of replica offsets
                if self._current_song != song_hash or \
                   master_offset > replica_offset:
                    self._in_recovery = True
                    return utils.serialize_response(failover_mode_resp)
            elif song_hash != None:
                print "Loaded song"
                pygame.mixer.music.load(utils.get_music_path(song_hash))

            # Adjust start_time_microsec to account for offset difference
            if master_offset > 0:
                offset_diff = master_offset - replica_offset
                start_time_microsec = \
                    start_time_microsec - (offset_diff*MILLISECONDS)
                assert(offset_diff >= 0)
            
            # wait until start time, then play
            curr_replica_microsec = int(round(time.time() * MICROSECONDS))
            print song_hash
            print master_offset
            while (curr_replica_microsec + ALLOWED_REPLICA_BUFFER < start_time_microsec):
                curr_replica_microsec = int(round(time.time() * MICROSECONDS))
            if song_hash == None:
                pygame.mixer.music.stop()
            elif master_offset == 0:
                print "Should play now"
                pygame.mixer.music.play(1)
            else:
                pygame.mixer.music.unpause()
            time.sleep(2) # necessary to allow mp3 thread to start?
            self._current_song = song_hash
            curr_replica_microsec = int(round(time.time() * MICROSECONDS))
            resp = utils.format_rpc_response(True, PLAY, \
                                             {'time': curr_replica_microsec }, \
                                             command_epoch='command_epoch')
            return utils.serialize_response(resp)

    # stop the current song.
    # payload has the local stop time ('stop_time')
    # route: /pause (POST)
    def pause(self):
        content = utils.unserialize_response(request.get_data())
        command_epoch = content['command_epoch']
        master_stop_micros = content['stop_time']
        if self._in_recovery:
            failover_resp = utils.format_rpc_response(False, PAUSE, {}, \
                                                 msg='Replica in recovery mode', \
                                                 command_epoch=command_epoch)
            return utils.serialize_response(failover_resp)
        
        # Wait till appointed stop time, allowed to be less precise than play
        # (if vs while loop)
        curr_replica_micros = int(round(time.time() * MICROSECONDS))
        if (curr_replica_micros < master_stop_micros):
            time.sleep((master_stop_micros - curr_replica_micros) / float(MICROSECONDS))

        with self._pygame_lock:
            pygame.mixer.music.pause()
            
            # return offset from start of song
            replica_offset = int(round(pygame.mixer.music.get_pos()))
            replica_micros = int(round(time.time() * MICROSECONDS))
            resp = \
                utils.format_rpc_response(True, PAUSE, \
                                          {'time': replica_micros, \
                                           'offset': replica_offset}, \
                                           command_epoch=command_epoch)
            return utils.serialize_response(resp)
        
    # get current time. also returns offset in current song (or -1 if not playing)
    # route: /time (POST)
    def get_time(self):
        if self._in_recovery:
            failover_resp = utils.format_rpc_response(False, HB, {}, \
                                                 msg='Replica in recovery mode')
            return utils.serialize_response(failover_resp)
        content = utils.unserialize_response(request.get_data())
        command_epoch = content['command_epoch']
        curr_time = time.time() * MICROSECONDS
        curr_micros = int(round(curr_time)) 
        with self._pygame_lock:
            replica_playing = pygame.mixer.music.get_busy()
        # Song has finished playing
        if not replica_playing:
            self._current_song = None
        resp = utils.format_rpc_response(True, HB, \
                                         {'time' : curr_micros, \
                                          'replica_playing': replica_playing},
                                          command_epoch = command_epoch)
        return utils.serialize_response(resp)

    # Dequeue songs with acks
    def dequeue_song(self):
        print "In Dequeue"
        content = utils.unserialize_response(request.get_data())
        command_epoch = content['command_epoch']
        master_post_hash = content['hashed_post_playlist']
        master_current_song = content['current_song']

        replica_pre_hash = utils.hash_string(pickle.dumps(self._playlist_queue))
        if replica_pre_hash == master_post_hash and self._current_song == master_current_song:
            repeat_resp = utils.format_rpc_response(False, DEQUEUE, {}, \
                                                 msg='Already performed operation', \
                                                 command_epoch=command_epoch)
            return utils.serialize_response(repeat_resp)            

        # Check for length 0 queue
        if len(self._playlist_queue) == 0:
            self._current_song = None
        else:
            self._current_song = self._playlist_queue.popleft()
        replica_post_hash = utils.hash_string(pickle.dumps(self._playlist_queue))

        if self._in_recovery or \
            (replica_post_hash != master_post_hash or self._current_song != master_current_song):            
            self._in_recovery = True
            failover_resp = utils.format_rpc_response(False, DEQUEUE, {}, \
                                                 msg='Replica in recovery mode', \
                                                 command_epoch=command_epoch)
            return utils.serialize_response(failover_resp)

        resp = utils.format_rpc_response(True, DEQUEUE, {}, \
                                         msg='Successfully dequeued', \
                                         command_epoch=command_epoch)
        return utils.serialize_response(resp)

    # Enqueue songs with acks
    def enqueue_song(self, song_hash):
        print "In Enqueue"
        content = utils.unserialize_response(request.get_data())
        command_epoch = content['command_epoch']
        master_post_hash = content['hashed_post_playlist']
        master_current_song = content['current_song']

        replica_pre_hash = utils.hash_string(pickle.dumps(self._playlist_queue))
        if replica_pre_hash == master_post_hash and self._current_song == song_hash:
            repeat_resp = utils.format_rpc_response(False, ENQUEUE, {}, \
                                                 msg='Already performed operation', \
                                                 command_epoch=command_epoch)
            return utils.serialize_response(repeat_resp)            

        # Do enqueue, check for failover mode
        song_not_exist = not os.path.exists(utils.get_music_path(song_hash))
        self._playlist_queue.append(song_hash)
        replica_post_hash = utils.hash_string(pickle.dumps(self._playlist_queue))
        inconsistent_queue = master_post_hash != replica_post_hash or \
                             master_current_song != self._current_song
        replica_failover = song_not_exist or inconsistent_queue
        if self._in_recovery or replica_failover:
            self._in_recovery = True
            failover_resp = utils.format_rpc_response(False, ENQUEUE, {}, \
                                                 msg='Replica in recovery mode', \
                                                 command_epoch=command_epoch)
            return utils.serialize_response(failover_resp)

        resp = utils.format_rpc_response(True, ENQUEUE, {'enqueued': True}, \
                                         command_epoch=command_epoch)
        return utils.serialize_response(resp)

    def load_song(self, song_hash):
        content = utils.unserialize_response(request.get_data())
        command_epoch = content['command_epoch']
        song_bytes = content['song_bytes']
        if self._in_recovery:
            failover_resp = utils.format_rpc_response(False, LOAD, {}, \
                                                 msg='Replica in recovery mode', \
                                                 command_epoch=command_epoch)
            return utils.serialize_response(failover_resp)
        try:
            with open(utils.get_music_path(song_hash), 'w') as f:
                f.write(song_bytes)
        except Exception:
            resp = utils.format_rpc_response(False, LOAD, {}, \
                                             msg='Error occured in writing to replica', \
                                             command_epoch=command_epoch)
        else:
            self._song_hashes.add(song_hash)
            resp = utils.format_rpc_response(True, LOAD, \
                                             {'has_song': True, 'ip':self._ip}, \
                                             command_epoch=command_epoch)
        return utils.serialize_response(resp)

    def check_song(self, song_hash):
        content = utils.unserialize_response(request.get_data())
        command_epoch = content['command_epoch']
        if self._in_recovery:
            failover_resp = utils.format_rpc_response(False, CHECK, {}, \
                                                 msg='Replica in recovery mode', \
                                                 command_epoch=command_epoch)
            return utils.serialize_response(failover_resp)        
        if song_hash in self._song_hashes:
            resp = utils.format_rpc_response(True, CHECK, \
                                             {'has_song': True, 'ip': self._ip}, \
                                             command_epoch = command_epoch)
        else:
            resp = utils.format_rpc_response(True, CHECK, {'ip': self._ip}, \
                                             command_epoch = command_epoch)
        return utils.serialize_response(resp)
    
    # start replica service: register routes and init music player
    def run(self):
        print "Starting Replica Server"
        self._app = Flask(__name__)     
        self._app.debug = True
 
        # register routes and handler methods

        self._app.add_url_rule("/enqueue/<song_hash>", "enqueue_song", \
                               self.enqueue_song, methods=['POST'])
        self._app.add_url_rule("/dequeue", "dequeue_song", \
                               self.dequeue_song, methods=['POST'])
        self._app.add_url_rule("/load/<song_hash>", "load_song", \
                               self.load_song, methods=['POST'])
        self._app.add_url_rule("/check/<song_hash>", "check_song", \
                               self.check_song, methods=['POST'])
        self._app.add_url_rule("/play", "play", self.play, methods=['POST'])
        self._app.add_url_rule("/pause", "pause", self.pause, methods=['POST'])
        self._app.add_url_rule("/time", "get_time", self.get_time, methods=['POST'])
        self._app.debug = True

        pygame.mixer.init()
        rfs = ReplicaFailoverService(self)
        rfs.start()
        self._app.run(host=self._ip)