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
import codecs
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
        
        # used for tracking latency and clock diffs. accessed by multiple threads
        self._update_lock = threading.Lock()
        self._latency_by_ip = {}
        self._clock_difference_by_ip = {}
        # initialize latency and diff to 0
        for ip in self._replicas:
            self._latency_by_ip[ip] = [0, 0, 0]
            self._clock_difference_by_ip[ip] = [0, 0, 0]
            
        # set current song state to not playing
        self._current_song = None
        self._current_offset = 0
        self._playing = False
        
        # used by rpcs to record responses
        self.offsets = []
        self.responses = 0
        self.not_playing = 0

        # used for enqueue and load songz
        self.enqueued_acks = 0
        self.not_loaded_ips = []
        self.loaded_acks = 0

        # counter that distinguishes commands
        self.command_epoch = 0
    
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
        # spawn new thread, which does an http request to fetch the current timestamp
        # from a replica
        data = {"playing" : self._playing}
        replica_url = 'http://' + replica_ip + TIME_URL
        r = RPC(self, HB, url=replica_url, ip=replica_ip, data=data)
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
    
    # go forward to next song
    def forward(self):
        song = None
        try:
            # haven't started a song yet; skip first song in queue
            if self._current_song == None:
                self._playlist_queue.get(False)
            
            # select next song in queue to play
            song = self._playlist_queue.get(False)
            self._current_song = song
        except Queue.Empty:
            # if we have no entries, we are now out of songs to play
            self._playing = False
        
        # after a forward command we are always at the start of a song
        self._current_offset = 0
        self._current_song = song
        # we are only starting the song if we are currently playing
        if self._playing:
            self.synchronize(qpos=1, start_song=True)
        else:
            self.synchronize(qpos=1, start_song=False)
    
    # go back to start of current song
    def backward(self):
        self._current_offset = 0
        if self._playing:
            self.synchronize()
        else:
            self._status_queue.put("success")            
    
    # pause the music
    def pause(self):
        self.offsets = []
        total_max_delay = 0
        for ip in self._replicas:
            total_max_delay += self._latency_by_ip[ip][2]            
        delay_buffer = int(2*total_max_delay)
        # set stop time in same fashion as start time 
        stop_time = int(round(time.time() * MICROSECONDS)) + delay_buffer
        for ip in self._replicas:
            local_stop = stop_time + int(self._clock_difference_by_ip[ip][0])
            r = RPC(self, PAUSE, url='http://' + ip + STOP_URL, \
                    ip=ip, data={"stop_time":local_stop})
            r.start()
            
        time.sleep(float(2*delay_buffer + 2*EXTRA_BUFFER) / MICROSECONDS)
        # decide how far into song we are based on maximum offset from replicas
        max_offset = 0
        for offset in self.offsets:
            if offset > self._current_offset:
                self._current_offset = offset
        
        # currently assume success; could count number of offset responses
        self._playing = False
        self._status_queue.put("success")
        
    # synchronize all replicas to the master's state
    def synchronize(self, qpos=0, start_song=True, return_status = True):
        # if we aren't currently playing a song, de-queue the next one
        if self._current_song == None and (qpos == 0 or start_song == True):
            try:
                song = self._playlist_queue.get(False)
                self._current_song = song
                self._current_offset = 0
            except Queue.Empty:
                if return_status:
                    self._status_queue.put("no songs queued")
                return
    
        self.responses = 0  # acks of success
        # calculate approximate timeout for replica response
        total_max_delay = 0
        for ip in self._replicas:
            total_max_delay += self._latency_by_ip[ip][2]            
        delay_buffer = int(2*total_max_delay)
        # global start time that all replicas must agree on
        start_time = \
            int(round(time.time() * MICROSECONDS)) + delay_buffer + EXTRA_BUFFER
        for ip in self._replicas:
            local_start = start_time + int(self._clock_difference_by_ip[ip][0])
            if not start_song:
                local_start = -1
            # each rpc runs on its own thread; send play command for local start time
            req_data = { "song_hash" : self._current_song, \
                         "offset": self._current_offset, \
                         "queue_index":qpos, "start_time":local_start }
            r = RPC(self, PLAY, url='http://' + ip + PLAY_URL, ip=ip, data=req_data)
            r.start()
         
        # wait for a bit, then check for acks (all other responses time out)
        time.sleep(float(2*delay_buffer + 2*EXTRA_BUFFER) / MICROSECONDS)
        if self.responses >= 1 and return_status: # check for acks
            self._playing = start_song
            self._status_queue.put("success")
        elif return_status:
            self._status_queue.put("failure")

    # queue song to replicass/replicas
    # TODO: Asynchronous requests
    # TODO: Take out master's replica in roundtrip TCP to replicas
    def enqueue_song(self, song_hash):
        song_hash = params['song_hash']
        self.enqueued_acks = 0
        for replica_ip in self._replicas:
            replica_url = \
                 'http://' + replica_ip + ENQUEUE_URL + "/" + song_hash
            r = RPC(self, ENQUEUE, url=replica_url, \
                    ip=replica_ip, data={})
        if self.timeout('e', len(self._replicas), ENQUEUE_ACK_TIMEOUT):
            self._status_queue.put('failure timeout')
            return
        self._status_queue.put('success')          

    def timeout(self, left_comp_flag, right_comp, timeout_value):
        start_time = time.time()
        while True:
            if left_comp_flag == 'c':
                left_comp = 2*(self.loaded_acks+len(self.not_loaded_ips))-1
            elif left_comp_flag == 'l':
                left_comp = 2*self.loaded_acks-1
            elif left_comp_flag == 'e':
                left_comp = 2*self.enqueued_acks-1
            if left_comp >= right_comp:
                return False
            if (time.time() - start_time) > timeout_value:
                return True
            time.sleep(timeout_value / 100.0)

    def load_song(self, params):
        song_hash = params['song_hash']
        self.not_loaded_ips = []
        self.loaded_acks = 0
        for replica_ip in self._replicas:
            replica_url = 'http://' + replica_ip + CHECK_URL + '/' + song_hash
            r = RPC(self, CHECK, url=replica_url, ip=replica_ip, data={})
            r.start()
        if self.timeout('c', len(self._replicas), REPLICA_ACK_TIMEOUT):
            self._status_queue.put('failure timeout')
            return
        d = None
        for replica_ip in self._replicas:
            if replica_ip in self.not_loaded_ips:
                replica_url = \
                    'http://' + replica_ip + LOAD_URL + "/" + song_hash
                if d == None:
                    with open(MUSIC_DIR + song_hash + EXT, 'r') as f:
                        d = {'song_bytes': f.read()}
                r = RPC(self, LOAD, url=replica_url, ip=replica_ip, data=d)
                r.start()
        if self.timeout('l', len(self._replicas), REPLICA_LOAD_TIMEOUT):
            self._status_queue.put('failure')
            return
            # should save the song_hash somewhere to indicate successful loading
        self._status_queue.put('success')


    # main loop for music manager
    def run(self):
        self.get_initial_clock_diff()
        while (True):
            # check for command; either perform command or send heartbeat
            try:
                command_info = self._command_queue.get(False)
                self.command_epoch += 1
                command = command_info['command']
                params = command_info['params']
                if command == PLAY:
                    self.synchronize()
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
                time.sleep(HEARTBEAT_PAUSE)
            except Queue.Empty:
                #print "HB"
                self.not_playing = 0
                self.heartbeat_all()
                time.sleep(HEARTBEAT_PAUSE)
                # all replicas have finished a song, and state is playing: 
                # play next song
                if self.not_playing == len(self._replicas) and self._playing:
                    self._current_song = None
                    self._current_offset = 0
                    self._playing = False
                    self.synchronize(return_status = False)
