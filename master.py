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

# handles receiving requests from client and passing onto music processes (MasterMusicService)
class MasterClientListenerService(multiprocessing.Process):
    def __init__(self, ip, command_queue, status_queue):
        multiprocessing.Process.__init__(self)
        # stores outgoing commands
        self._command_queue = command_queue
        # stores incoming status messages
        self._status_queue = status_queue
        # my own ip address/port number
        self._ip = ip

    # TODO: Assign IDs to each command instance to avoid timeout bug
    def wait_on_master_music_service(self):
        status = None
        for i in range(0, 50):
            try:
                status = self._status_queue.get(False)
                break
            except Queue.Empty:
                time.sleep(CLIENT_TIMEOUT / 50.0)
        if status == None:
            print "timeout from master"
            status = "failure"
        return utils.serialize_response(status)

    # TODO: modify this command to accept client request and return response to client
    # currently takes one text command in the url; passes that text command through
    # a Queue to the Master Music synchronizer process, which then executes the command
    # and returns the response message to this process. Waits for a specified timeout
    # to receive a response status from the queue
    # endpoint: /<command_string>
    def execute_command(self, command):
        if command in [PLAY, PAUSE, FORWARD, BACKWARD]:
            command_info = {'command':command, 'params':{}}
            self._command_queue.put(command_info)
            return self.wait_on_master_music_service()
        else:
            return utils.serialize_response({'result':False})

    # Add a song to our playlist queue
    # endpoint: /queue/<song_hash>
    def enqueue_song(self, song_hash):
        command_info = {'command':ENQUEUE, 'params':{'song_hash':song_hash}}
        if request.method == 'GET':
            if os.path.exists(MUSIC_DIR + song_hash):
                # verify song exists on >= f+1 replicas and in their playlist
                # queues
                self._command_queue.put(command_info)
                return self.wait_on_master_music_service()
            # song doesn't exist on master, get the song from the client
            else:
                return utils.serialize_response({'result':False})
        else:
            with open(MUSIC_DIR + song_hash, 'w') as f:
                f.write(request.get_data())
            # verify song exists on >= f+1 replicas and in their playlist
            # queues
            self._command_queue.put(command_info)
            return self.wait_on_master_music_service()

    def run(self):
        self._app = Flask(__name__)
        # Register endpoints
        self._app.add_url_rule("/" + ENQUEUE + "/<song_hash>", "enqueue_song", \
                               self.enqueue_song, methods=['GET', 'POST'])
        self._app.add_url_rule("/<command>", "execute_command", self.execute_command)

        #self._app.debug = True
        self._ip = "127.0.0.1"
        self._app.run(host=self._ip, port=int(CLIENT_PORT))

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
        data = utils.serialize_response({"playing" : self._playing})
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
            r = RPC(self, PAUSE, url='http://' + ip + STOP_URL, ip=ip, data=utils.serialize_response({"stop_time":local_stop}))
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
        start_time = int(round(time.time() * MICROSECONDS)) + delay_buffer + EXTRA_BUFFER
        for ip in self._replicas:
            local_start = start_time + int(self._clock_difference_by_ip[ip][0])
            if not start_song:
                local_start = -1
            # each rpc runs on its own thread; send play command for local start time
            req_data = { "song_hash" : self._current_song, "offset": self._current_offset, "queue_index":qpos, "start_time":local_start }
            r = RPC(self, PLAY, url='http://' + ip + PLAY_URL, ip=ip, data=utils.serialize_response(req_data))
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
        self._playlist_queue.put(song_hash)
        total_responses = 0
        song_bytes = None
        for replica_ip in self._replicas:
            try:
                replica_url = 'http://' + replica_ip + QUEUE_URL + "/" + song_hash
                has_song_resp = urllib2.urlopen(replica_url)        
                has_song = utils.unserialize_response(response.read())['result']
                if not has_song:
                    if song_bytes != None:
                        with open(MUSIC_DIR + song_hash, 'r') as f:
                            song_bytes = f.read()
                    req = urllib2.Request(replica_url)
                    req.add_data(song_bytes)
                    received_song_resp = urllib2.urlopen(req)
                total_responses += 1
            except Exception:
                print "Replica " + replica_ip + " failed to receive song " + song_hash
        if (2 * total_responses - 1) >= len(self._replicas):
            self._status_queue.put("success")
        else:
            self._status_queue.put("failure")

    # main loop for music manager
    def run(self):
        self.get_initial_clock_diff()
        while (True):
            # check for command; either perform command or send heartbeat
            try:
                command_info = self._command_queue.get(False)
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

# Class that handles all master/replica rpcs
# usage (also read init method comment below to see args):
# r = RPC(self, "play", "192.168.1.138:5000", "http://192.168.1.138:5000/play")
# r.start()
class RPC(threading.Thread):
  # init() args: 
  # parent: parent object reference (used to store any response data)
  # type: the rpc type string ("hb" for heartbeat, "play" for play command, etc)
  # ip: target ip address, url: target url, data: POST payload
  def __init__(self, parent, command, ip, url, data):
    threading.Thread.__init__(self)
    self._parent = parent
    self._command = command
    self._ip = ip
    self._url = url
    self._data = data

  # run the rpc; time it and record response depending on RPC type string
  def run(self):
    req = urllib2.Request(self._url, self._data, {'Content-Type': 'application/json'})
    start = int(round(time.time() * MICROSECONDS))
    response = urllib2.urlopen(req)
    end = int(round(time.time() * MICROSECONDS))
    
    response_data = utils.unserialize_response(response)
    response_command = response_data['command']
    response_success = response_data['success']
    response_params = response_data['params']
    assert(response_command == self._command)

    # heartbeat: update latency, diff and check for song ending
    if response_command == HB and response_success:
        response_offset = int(response_params['offset'])
        response_time = int(response_params['time'])
        self._parent.update_latency(self._ip, (end - start) / 2.0)
        if response_offset == -1:
            self._parent.not_playing += 1
        # estimate for other computers clock time: their time, 
        # plus return network latency, which we approximate with (end-start)/2
        clock_estimate = response_time + (end - start) / 2
        diff = clock_estimate - end
        self._parent.update_clock_diff(self._ip, diff)
    elif response_command == PLAY and response_success:
        # successful play: inform parent of ack
        self._parent.responses += 1
    elif response_command == PAUSE and response_success:
        response_offset = int(response_params['offset'])
        if response_offset > -1:
            # paused: record offset in song
            self._parent.offsets.append(response_offset)
    if DEBUG:
        print "ip:" + self._ip + ":" + str(response_data)

# main master method: set up services (music service and client listener)
if __name__ == "__main__":
    # load replicas IPs from file
    REPLICA_IP_ADDRS = []
    with open(REPLICA_IP_FILE, "r") as f:
        for ip_addr in f:
            REPLICA_IP_ADDRS.append(ip_addr.strip() + ':' + REPLICA_PORT)
    # determine our IP, start client listener
    ip_addr = utils.get_ip_addr()
    command_queue = multiprocessing.Queue()
    status_queue = multiprocessing.Queue()
    playlist_queue = multiprocessing.Queue()

    client_listener_service = MasterClientListenerService(ip_addr, command_queue, status_queue)
    client_listener_service.start()
        
    # start service that listens for client commands from above process
    # and plays music when instructed
    # music_server = MasterMusicService(REPLICA_IP_ADDRS, playlist_queue, command_queue, status_queue)
    # music_server.start()