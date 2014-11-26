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

# listens for master commands, plays/pauses/skips as needed
class ReplicaMusicService(multiprocessing.Process):
    def __init__(self, song_queue, ip_addr):
        multiprocessing.Process.__init__(self)
        self._stop = threading.Event()
        self._song_queue = song_queue
        self._ip = ip_addr
        self._recovery_mode = False
        self._currently_playing = None
    
    # Receives a json payload with the following fields:
    # start_time
    # queue_index (should be 0 or 1 for now)
    # song_hash (should match queue index value, or we are out of sync)
    # offset
    #
    # route: /play (POST)
    def start_play(self):
        if self._recovery_mode:
            # f = {"failure":"replica in recovery mode"}
            resp = utils.format_rpc_response(False, PLAY, {}, 'Replica in recovery mode')
            return utils.serialize_response(resp)
        
        # parse payload
        content = request.json
        start_time = content['start_time']
        offset = 0
        if 'offset' in content:
            offset = int(content['offset'])
        queue_index = int(content['queue_index'])
        song_hash = content['song_hash']
        
        # not currently playing song: try to get next song if we about to start
        if (self._currently_playing == None and start_time != -1):
            try:
                self._currently_playing = self._song_queue.get(False)
            except Queue.Empty:
                # no next song available
                self._currently_playing = None
            print "popped queue:" + str(self._currently_playing)
        
        # make sure we have enough items in queue
        if (start_time != -1 and queue_index > self._song_queue.qsize()):
            self._recovery_mode = True
            # f = {"failure":"error: not enough items in queue"}
            resp = utils.format_rpc_response(False, PLAY, {}, 'Not enough items in queue')
            return utils.serialize_response(resp)
            
        # if index is 1, this is a forward command
        if (queue_index == 1):
            # try to skip to next song, if available
            try:
                self._currently_playing = self._song_queue.get(False)
            except Queue.Empty:
                # no next song available; stop playing
                self._currently_playing = None
                pygame.mixer.music.stop()
                print "queue empty; stopping music"
        
        # check that song hash matches top of queue
        if (song_hash != self._currently_playing and start_time != -1):
            self._recovery_mode = True
            # f = {"failure":"error: song hash doesnt match top of queue"}
            resp = utils.format_rpc_response(False, PLAY, {}, 'Song hash does not match top of queue')
            return utils.serialize_response(resp)
            
        # load file if needed
        new_song = False
        if (offset == 0 or queue_index == 1) and self._currently_playing != None:
            pygame.mixer.music.load(song_hash)
            new_song = True
            
        # can return here if we aren't supposed to start playing
        if start_time == -1:
            print "not playing"
            # f = {"success" : "not playing"}
            resp = utils.format_rpc_response(True, PLAY, {})
            return utils.serialize_response(resp)
        else:
            print "playing: " + song_hash
            
        # not new song: calculate our offset diff from master offset and adjust
        if not new_song:
            offset_diff = offset - pygame.mixer.music.get_pos()
            print "offset diff: " + str(offset_diff)
            start_time = start_time - (offset_diff*1000)
        
        # wait until start time, then play
        start_nanos = int(round(time.time() * 1000000))
        while (start_nanos + 400 < start_time):
            start_nanos = int(round(time.time() * 1000000))
        if new_song:
            pygame.mixer.music.play(1)
        else:
            pygame.mixer.music.unpause()
        nanos = int(round(time.time() * 1000000))
        time.sleep(0.2) # allow mp3 thread to start

        resp = utils.format_rpc_response(True, PLAY, {'time': nanos})
        return utils.serialize_response(resp)
        
    # stop the current song.
    # payload has the local stop time ('stop_time')
    # route: /pause (POST)
    def stop_play(self):
        if self._recovery_mode:
            resp = utils.format_rpc_response(False, PAUSE, {}, 'Replica in recovery mode')
            return utils.serialize_response(resp)
        
        content = request.json
        stop_time = content['stop_time']
        # wait till appointed stop time
        stop_nanos = int(round(time.time() * 1000000))
        if (stop_nanos < stop_time):
            time.sleep((stop_time - stop_nanos) / 1000000.0)
        pygame.mixer.music.pause()
        
        # return offset from start of song
        offset = pygame.mixer.music.get_pos()
        nanos = int(round(time.time() * 1000000))
        print str(offset)
        resp = utils.format_rpc_response(True, PAUSE, {'time': nanos, 'offset': offset})
        return utils.serialize_response(resp)
        
    # get current time. also returns offset in current song (or -1 if not playing)
    # route: /time (POST)
    def get_time(self):
        nanos = int(round(time.time() * 1000000))
        self._last_beat = nanos
        offset = pygame.mixer.music.get_pos()
        if offset == -1:
            self._currently_playing = None
        resp = utils.format_rpc_response(True, HB, {'time' : nanos, 'offset': offset })
        return utils.serialize_response(resp)
    
    # simple method to queue a song (TODO: add acks)
    def queue_song(self, queue_file):
        self._song_queue.put(queue_file)
        return "success:" + queue_file
      
    # start replica service: register routes and init music player
    def run(self):
        print "STARTING"
        self._app = Flask(__name__)
        # modify buffer param (larger=more latency diffs)
        pygame.mixer.init(buffer=512)
        
        # register routes and handler methods
        self._app.add_url_rule("/queue/<queue_file>", "queue_song", self.queue_song)
        self._app.add_url_rule("/play", "start_play", self.start_play, methods=['POST'])
        self._app.add_url_rule("/pause", "stop_play", self.stop_play, methods=['POST'])
        self._app.add_url_rule("/time", "get_time", self.get_time, methods=['POST'])
        #self._app.debug = True
        self._app.run(host=self._ip)

# reads initial queue (if present) then starts replica music service
if __name__ == "__main__":
    song_q = multiprocessing.Queue()
    argv = sys.argv
    song_name = None
    if len(argv) > 1:
        queue_file = argv[1]
        with open(queue_file) as qf:
            for line in qf.readlines():
                song_hash = line[:-1]
                song_q.put(song_hash)
    
    # start replica service
    ip_addr = utils.get_ip_addr()
    print 'replica ip address is:' + ip_addr 
    replica_service = ReplicaMusicService(song_q, ip_addr)
    replica_service.start()
    