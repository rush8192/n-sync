#!/usr/bin/python
from flask import Flask, request, redirect, Response
import json
import multiprocessing
import Queue
import socket
import sys
import threading
import time
import urllib2
import os
import utils
from constants import *
from master_client_listener_service import MasterClientListenerService
from master_replica_rpc import RPC
import collections
import pickle
import random

# handles play/pause/forward/backward commands received from client listener
# process (MasterClientListenerService)
class MasterMusicService(multiprocessing.Process):
    def __init__(self, replicas, playlist_queue, command_queue, status_queue):
        multiprocessing.Process.__init__(self)
        # stores the song queue
        self._playlist_queue = playlist_queue
        # stores incoming commands
        self._command_queue = command_queue
        # for outgoing status messages (to return to client)
        self._status_queue = status_queue
        
        # list of all replicas IP addresses
        self._replicas = replicas

        # used for tracking latency and clock diffs.
        # accessed by multiple threads
        self._update_lock = threading.Lock()
        self._latency_by_ip = {}
        self._clock_difference_by_ip = {}

        # initialize latency and diff to 0
        for ip in self._replicas:
            self._latency_by_ip[ip] = [0, 0, 0]
            self._clock_difference_by_ip[ip] = [0, 0, 0]
        # set current song state to not playing for master
        self._master_ip = None
        # set current song state to not playing
        self._current_song = None
        self._current_offset = 0
        self._playing = False
        
        # used by rpcs to record responses for enqueue, dequeue, pause, play
        # TODO: Implement read-write locks here for sure
        self.rpc_offsets = []
        self.rpc_response_acks = 0
        self.rpc_not_playing_acks = 0

        # used by rpcs to load songs for responses: TODO: read-write locks?
        self.rpc_not_loaded_ips = Queue.Queue()
        self.rpc_loaded_ips = Queue.Queue()

        # counter that distinguishes commands
        # if write is atomic we are fine, otherwise we should use rw locks
        self.command_epoch = 0

        # current client request, one thread accesses this, no need for locks
        self._client_req_id = None

        self._prev_hb = time.time()
    
    # updates the running average clock diff for a given ip
    def update_clock_diff(self, ip, diff):
        with self._update_lock:
            cur_avg_diff = self._clock_difference_by_ip[ip][0]
            cur_num_datapoints = self._clock_difference_by_ip[ip][1]
            cur_max_diff = self._clock_difference_by_ip[ip][2]
            new_avg = (cur_avg_diff*cur_num_datapoints + diff) / (1.0 + cur_num_datapoints)
            self._clock_difference_by_ip[ip][1] += 1
            #if (clock_difference_by_ip[ip][1] == 1): # skip first ping; tends to be noisy
            #    return
            self._clock_difference_by_ip[ip][0] = new_avg
            if (diff > cur_max_diff):
                self._clock_difference_by_ip[ip][2] = diff
            if (DEBUG):
                print "avg diff for ip:" + ip + ":" + str(new_avg) + ":" + str(diff)

    # updates the running average latency for an ip
    def update_latency(self, ip, latency):
        with self._update_lock:
            cur_avg_latency = self._latency_by_ip[ip][0]
            cur_num_datapoints = self._latency_by_ip[ip][1]
            cur_max_latency = self._latency_by_ip[ip][2]
            new_avg = (cur_avg_latency*cur_num_datapoints + latency) / (1.0 + cur_num_datapoints)
            self._latency_by_ip[ip][0] = new_avg
            self._latency_by_ip[ip][1] += 1
            if (latency > cur_max_latency):
                self._latency_by_ip[ip][2] = latency
            if (DEBUG):
                print str("avg latency(one-way) for ip:" + ip + ":" + str(new_avg))
    
    # sends a basic heartbeat message to an ip
    def heartbeat(self, replica_ip):
        # spawn new thread, which does an http request to fetch the
        # current timestamp from a replica
        data = {"playing" : self._playing}
        replica_url = 'http://' + replica_ip + TIME_URL
        r = RPC(self, HB, url=replica_url, ip=replica_ip, data=data, master_ip = self._master_ip)
        r.start()
    
    # send heartbeat to all replicas
    def heartbeat_all(self):
        for replica_ip in self._replicas:
            self.heartbeat(replica_ip)
    
    def get_initial_clock_diff(self):
        # get initial latency/clock information
        for i in range(0, INITIAL_CALIBRATION_PINGS):
            self.heartbeat_all()
            time.sleep(HEARTBEAT_PAUSE)
    
    # Waits for f+1 responses from replicas before returning
    # Otherwise exponentially backs off until RPC success
    def exponential_backoff(self, rpc_data, OP, OP_URL, time_to_sleep):
        print 'master music: ' + OP + ' timeout'
        if 2*self.rpc_response_acks - 1 >= len(self._replicas):
            return
        for replica_ip in self._replicas:
            replica_url = \
                 'http://' + replica_ip + OP_URL
            r = RPC(self, OP, url=replica_url, \
                    ip=replica_ip, data=rpc_data)
            r.start()
        time.sleep(time_to_sleep)
        self.exponential_backoff(rpc_data, OP, OP_URL, time_to_sleep * 2)

    # Reset all the rpc parameters everytime we are doing a new command
    def reset_rpc_parameters(self):
        # Guaranteed no races since new command_epoch prevents previous
        # rpc calls from writing (short circuits in master_replica_rpc).
        self.rpc_not_loaded_ips.queue.clear()
        self.rpc_loaded_ips.queue.clear()
        self.rpc_offsets = []
        self.rpc_response_acks = 0
        self.not_playing_acks = 0

    # Waits until timeout has occurred for load
    def load_timeout(self):
        start_time = time.time()
        while True:
            if 2*self.rpc_loaded_ips.qsize()-1 >= len(self._replicas):
                return False
            if (time.time() - start_time) > REPLICA_LOAD_TIMEOUT:
                return True
            time.sleep(REPLICA_LOAD_TIMEOUT / 100)

    # Checks with replicas to see if they have song, then sends song to those
    # that do not have song_hash
    def load_song(self, params):
        song_hash = params['song_hash']

        # Check with replicas to see which have song
        rpc_data = {}
        self.exponential_backoff(rpc_data, CHECK, \
                            CHECK_URL + '/' + song_hash, REPLICA_ACK_TIMEOUT)

        # Loads songs to those who don't have it
        rpc_data = None
        while not self.rpc_not_loaded_ips.empty():
            replica_ip = self.rpc_not_loaded_ips.get(block=False)
            replica_url = \
                'http://' + replica_ip + LOAD_URL + "/" + song_hash
            if rpc_data == None:
                with open(utils.get_music_path(song_hash), 'r') as f:
                    rpc_data = {'song_bytes': f.read()}
            r = RPC(self, LOAD, url=replica_url, ip=replica_ip, data=rpc_data)
            r.start()
        
        if self.load_timeout():
            self._status_queue.put(utils.format_client_response(\
                                      False, LOAD, {}, \
                                      msg='Timeout on song load', \
                                      client_req_id=self._client_req_id))
        else:
            self._status_queue.put(utils.format_client_response(\
                                      True, LOAD, {}, \
                                      client_req_id=self._client_req_id))

    # Enqueue song to replicas/replicas using indefinite exponential backoff
    def enqueue_song(self, params):
        song_hash = params['song_hash']
        self._playlist_queue.append(song_hash)
        hashed_post_playlist = utils.hash_string(pickle.dumps(self._playlist_queue))

        rpc_data = {'current_song': self._current_song, \
                    'hashed_post_playlist': hashed_post_playlist}

        self.exponential_backoff(rpc_data, ENQUEUE, \
                                 ENQUEUE_URL + '/' + song_hash, \
                                 REPLICA_ACK_TIMEOUT)
        self._status_queue.put(utils.format_client_response(\
                                   True, ENQUEUE, {}, \
                                   client_req_id=self._client_req_id))

    # Plays current_song at current_offset

    def play(self, return_status=True):
        print 'master service: in play'
        success_response = utils.format_client_response(\
                                True, PLAY, {}, \
                                client_req_id=self._client_req_id)
        # Calls forward then play again
        if self._current_song == None:
            self.current_offset = 0
            if len(self._playlist_queue) > 0:
                self.forward(return_status=False, play=False)
                self.play(return_status=return_status)
                return

        # calculate approximate timeout for replica response
        delay_buffer = 0
        total_max_delay = 0
        for ip in self._replicas:
            total_max_delay += self._latency_by_ip[ip][2]            
        delay_buffer = int(2*total_max_delay)

        # global start time that all replicas must agree on
        start_time = \
            int(round(time.time() * MICROSECONDS)) + delay_buffer + EXTRA_BUFFER

        for replica_ip in self._replicas:
            local_start = start_time + int(self._clock_difference_by_ip[replica_ip][0])
            # each rpc runs on its own thread; send play command for local start time
            # Note that the current song can be None in which case replica
            # will stop playing current song
            req_data = { 'song_hash' : self._current_song, \
                         'offset': self._current_offset, \
                         'start_time': local_start }
            r = RPC(self, PLAY, url='http://' + replica_ip + PLAY_URL, \
                    ip=replica_ip, data=req_data)
            r.start()
         
        # TODO: same as pause to do a better ack-check-wait
        time.sleep(float(2*delay_buffer + 2*EXTRA_BUFFER) / MICROSECONDS)
        if self.rpc_response_acks >= 1: # check for acks
            self._playing = True
            if return_status:
                self._status_queue.put(utils.format_client_response(\
                                           True, PLAY, {}, \
                                           client_req_id=self._client_req_id))
        elif return_status:
            self._status_queue.put(utils.format_client_response(\
                                        False, PLAY, {}, \
                                        client_req_id=self._client_req_id))

    # pause the music
    def pause(self):
        total_max_delay = 0
        for ip in self._replicas:
            total_max_delay += self._latency_by_ip[ip][2]
        delay_buffer = int(2*total_max_delay)
        # set stop time in same fashion as start time 
        stop_time = int(round(time.time() * MICROSECONDS)) + delay_buffer
        for ip in self._replicas:
            local_stop = stop_time + int(self._clock_difference_by_ip[ip][0])
            r = RPC(self, PAUSE, url='http://' + ip + STOP_URL, \
                    ip=ip, data={"stop_time":local_stop}, master_ip = self._master_ip)
            r.start()

        time.sleep(float(2*delay_buffer + 2*EXTRA_BUFFER) / MICROSECONDS)
        # decide how far into song we are based on maximum offset from replicas
        max_offset = 0
        for offset in self.rpc_offsets:
            if offset > self._current_offset:
                self._current_offset = offset
        
        # TODO: currently assume success; could count number of offset responses
        self._playing = False
        self._status_queue.put(utils.format_client_response(\
                                   True, PAUSE, {}, \
                                   client_req_id=self._client_req_id))

    # Go forward to next song, involves a dequeue operation
    # By default auto plays next song but can be set to false
    def forward(self, return_status = True, play=True):
        song = None
        success_response = utils.format_client_response(\
                                          True, FORWARD, {}, \
                                          client_req_id=self._client_req_id)
        # No song in future and no song currently playing, nothing to do.
        if len(self._playlist_queue) == 0 and self._current_song == None:
            if return_status:
                self._status_queue.put(success_response)
            return

        # After a forward command we are always at the start of a song
        self._current_offset = 0
        # No songs to play anymore
        if len(self._playlist_queue) == 0:
            self._current_song = None
        # Pop out a song to play
        else:
            self._current_song = self._playlist_queue.popleft()
        hashed_post_playlist = utils.hash_string(pickle.dumps(self._playlist_queue))

        # Synchronizes dequeue operation across all replicas (for master recovery)
        rpc_data = {'hashed_post_playlist': hashed_post_playlist, \
                    'current_song' : self._current_song}
        # Try indefinitely until we get at least f+1 responses
        # Guaranteed RPC won't add to queue since new command_epoch prevents
        # Holding mutexes just in case
        self.exponential_backoff(rpc_data, DEQUEUE, \
                                 DEQUEUE_URL, \
                                 REPLICA_ACK_TIMEOUT)

        # Start playing the next song
        # (if current_song == None then will just stop playing music)
        if play:
            self.play(return_status)
        if return_status:
            self._status_queue.put(success_response)

    # go back to start of current song
    def backward(self):
        self._current_offset = 0
        # Play if song was previously playing
        if self._playing:
            self.play()
        self._status_queue.put(utils.format_client_response(\
                                   True, BACKWARD, {}, \
                                   client_req_id=self._client_req_id))            
    
    # main loop for music manager
    def run(self):
        self.get_initial_clock_diff()
        while (True):
            # check for command; either perform command or send heartbeat
            self.command_epoch = self.command_epoch + 1
            try:
                command_info = self._command_queue.get(False)
                command = command_info['command']
                params = command_info['params']
                self._master_ip = command_info['master_ip']
                self._client_req_id = command_info['client_req_id']
                self.reset_rpc_parameters()
                if command == PLAY:
                    self.play()
                elif command == PAUSE:
                    self.pause()
                elif command == FORWARD:
                    self.forward()
                elif command == BACKWARD:
                    self.backward()
                elif command == ENQUEUE:
                    self.enqueue_song(params)
                elif command == LOAD:
                    self.load_song(params)
            except Queue.Empty:
                self.reset_rpc_parameters()
                if int(time.time() - self._prev_hb) > HEARTBEAT_INTERVAL:
                    self.heartbeat_all()
                    self._prev_hb = time.time()

                time.sleep(QUEUE_SLEEP)
                # all replicas have finished a song, and state is playing: 
                # play next song if possible
                if self.rpc_not_playing_acks == len(self._replicas) and self._playing:
                    self._playing = False # Prevents infinite tries of HB plays
                    self.forward(return_status=False)
