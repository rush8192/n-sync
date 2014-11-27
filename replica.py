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

# listens for master commands, plays/pauses/skips as needed
class ReplicaMusicService(multiprocessing.Process):
    def __init__(self, playlist_queue, ip_addr):
        multiprocessing.Process.__init__(self)
        self._stop = threading.Event()
        self._playlist_queue = playlist_queue
        self._ip = ip_addr
        self._recovery_mode = False
        self._currently_playing = None

        self._song_hashes = self.initialize_song_hashes()

    # may need to remove .DS_STORE etc
    def initialize_song_hashes(self):
        if not os.path.exists(MUSIC_DIR):
            os.makedirs(MUSIC_DIR)
        song_hashes = set(os.listdir(MUSIC_DIR))
        return song_hashes

    # Receives a json payload with the following fields:
    # start_time
    # queue_index (should be 0 or 1 for now)
    # song_hash (should match queue index value, or we are out of sync)
    # offset
    #
    # route: /play (POST)
    def start_play(self):
        content = request.get_data()
        command_epoch = content['command_epoch']
        if self._recovery_mode:
            # f = {"failure":"replica in recovery mode"}
            resp = utils.format_rpc_response(False, PLAY, {}, \
                                             msg='Replica in recovery mode', \
                                             command_epoch='command_epoch')
            return utils.serialize_response(resp)
        
        # parse payload

        start_time = content['start_time']
        offset = 0
        if 'offset' in content:
            offset = int(content['offset'])
        queue_index = int(content['queue_index'])
        song_hash = content['song_hash']
        
        # not currently playing song: try to get next song if we about to start
        if (self._currently_playing == None and start_time != -1):
            try:
                self._currently_playing = self._playlist_queue.popleft()
            except Queue.Empty:
                # no next song available
                self._currently_playing = None
            print "popped queue:" + str(self._currently_playing)
        
        # make sure we have enough items in queue
        if (start_time != -1 and queue_index > len(self._playlist_queue)):
            self._recovery_mode = True
            # f = {"failure":"error: not enough items in queue"}
            resp = utils.format_rpc_response(False, PLAY, {}, \
                                             msg='Not enough items in queue', \
                                             command_epoch='command_epoch')
            return utils.serialize_response(resp)
            
        # if index is 1, this is a forward command
        if (queue_index == 1):
            # try to skip to next song, if available
            try:
                self._currently_playing = self._playlist_queue.popleft()
            except Queue.Empty:
                # no next song available; stop playing
                self._currently_playing = None
                pygame.mixer.music.stop()
                print "queue empty; stopping music"
        
        # check that song hash matches top of queue
        if (song_hash != self._currently_playing and start_time != -1):
            self._recovery_mode = True
            # f = {"failure":"error: song hash doesnt match top of queue"}
            resp = utils.format_rpc_response(False, PLAY, {}, \
                                             msg='Song hash does not match top of queue', \
                                             command_epoch='command_epoch')
            return utils.serialize_response(resp)
            
        # load file if needed
        new_song = False
        if (offset == 0 or queue_index == 1) and self._currently_playing != None:
            pygame.mixer.music.load(song_hash)
            new_song = True
            
        # can return here if we aren't supposed to start playing
        if start_time == -1:
            print "not playing"
            resp = utils.format_rpc_response(True, PLAY, {}, \
                                             command_epoch='command_epoch')
            return utils.serialize_response(resp)
        else:
            print "playing: " + song_hash
            
        # not new song: calculate our offset diff from master offset and adjust
        if not new_song:
            offset_diff = offset - pygame.mixer.music.get_pos()
            print "offset diff: " + str(offset_diff)
            start_time = start_time - (offset_diff*1000)
        
        # wait until start time, then play
        start_nanos = int(round(time.time() * MICROSECONDS))
        while (start_nanos + 400 < start_time):
            start_nanos = int(round(time.time() * MICROSECONDS))
        if new_song:
            pygame.mixer.music.play(1)
        else:
            pygame.mixer.music.unpause()
        nanos = int(round(time.time() * MICROSECONDS))
        time.sleep(0.2) # allow mp3 thread to start

        resp = utils.format_rpc_response(True, PLAY, {'time': nanos}, \
                                         command_epoch='command_epoch')
        return utils.serialize_response(resp)
        
    # stop the current song.
    # payload has the local stop time ('stop_time')
    # route: /pause (POST)
    def stop_play(self):
        content = utils.unserialize_response(request.get_data())
        command_epoch = content['command_epoch']
        if self._recovery_mode:
            resp = utils.format_rpc_response(False, PAUSE, {}, \
                                             'Replica in recovery mode', \
                                             command_epoch=command_epoch)
            return utils.serialize_response(resp)
        
        stop_time = content['stop_time']
        # wait till appointed stop time
        stop_nanos = int(round(time.time() * MICROSECONDS))
        if (stop_nanos < stop_time):
            time.sleep((stop_time - stop_nanos) / float(MICROSECONDS))
        pygame.mixer.music.pause()
        
        # return offset from start of song
        offset = pygame.mixer.music.get_pos()
        nanos = int(round(time.time() * MICROSECONDS))
        print str(offset)
        resp = \
            utils.format_rpc_response(True, PAUSE, \
                                      {'time': nanos, 'offset': offset}, \
                                      command_epoch=command_epoch)
        return utils.serialize_response(resp)
        
    # get current time. also returns offset in current song (or -1 if not playing)
    # route: /time (POST)
    def get_time(self):
        nanos = int(round(time.time() * MICROSECONDS))
        self._last_beat = nanos
        offset = pygame.mixer.music.get_pos()
        if offset == -1:
            self._currently_playing = None
        resp = utils.format_rpc_response(True, HB, \
                                         {'time' : nanos, 'offset': offset })
        return utils.serialize_response(resp)
    
    # simple method to queue a song (TODO: add acks)
    def enqueue_song(self, song_hash):
        content = utils.unserialize_response(request.get_data())
        command_epoch = content['command_epoch']
        if os.path.exists(MUSIC_DIR + song_hash + EXT):
            self._playlist_queue.append(song_hash)
            resp = utils.format_rpc_response(True, ENQUEUE, {'enqueued': True}, \
                                             command_epoch=command_epoch)
        else:
            resp = utils.format_rpc_response(True, ENQUEUE, {}, \
                                             msg='Replica does not have song', \
                                             command_epoch=command_epoch)
        print self._playlist_queue
        return utils.serialize_response(resp)

    def load_song(self, song_hash):
        content = utils.unserialize_response(request.get_data())
        command_epoch = content['command_epoch']
        song_bytes = content['song_bytes']
        try:
            with open(MUSIC_DIR + song_hash + EXT, 'w') as f:
                f.write(song_bytes)
        except Exception:
            resp = utils.format_rpc_response(False, LOAD, {}, \
                                             msg='Error occured in writing to replica', \
                                             command_epoch=command_epoch)
        else:
            self._song_hashes.add(song_hash)
            resp = utils.format_rpc_response(True, LOAD, {'has_song': True, 'ip':self._ip}, \
                                             command_epoch=command_epoch)
        return utils.serialize_response(resp)

    def check_song(self, song_hash):
        content = utils.unserialize_response(request.get_data())
        command_epoch = content['command_epoch']
        if song_hash in self._song_hashes:
            resp = utils.format_rpc_response(True, CHECK, \
                                             {'has_song': True, 'ip': self._ip}, \
                                             command_epoch = command_epoch)
        else:
            resp = utils.format_rpc_response(True, CHECK, {'ip': self._ip}, \
                                             command_epoch = command_epoch)
        print utils.serialize_response(resp)
        return utils.serialize_response(resp)

    # start replica service: register routes and init music player
    def run(self):
        print "Starting Replica Server"
        self._app = Flask(__name__)
        # modify buffer param (larger=more latency diffs)
        pygame.mixer.init(buffer=INITIAL_BUFFER_SIZE)
        
        # register routes and handler methods

        self._app.add_url_rule("/enqueue/<song_hash>", "enqueue_song", self.enqueue_song)
        self._app.add_url_rule("/load/<song_hash>", "load_song", self.load_song, methods=['POST'])
        self._app.add_url_rule("/check/<song_hash>", "check_song", self.check_song, methods=['POST'])
        self._app.add_url_rule("/play", "start_play", self.start_play, methods=['POST'])
        self._app.add_url_rule("/pause", "stop_play", self.stop_play, methods=['POST'])
        self._app.add_url_rule("/time", "get_time", self.get_time, methods=['POST'])
        #self._app.debug = True
        self._app.run(host=self._ip)

# reads initial queue (if present) then starts replica music service
if __name__ == "__main__":
    playlist_queue = multiprocessing.Queue()    
    # start replica service
    ip_addr = utils.get_ip_addr()
    print 'Replica IP Address is:' + ip_addr 
    replica_service = ReplicaMusicService(playlist_queue, ip_addr)
    replica_service.start()
    