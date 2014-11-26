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
    if self._command != HB:
        self._data['command_epoch'] = self._parent.command_epoch
    self._data = utils.serialize_response(self._data)
    req = urllib2.Request(self._url, self._data) 
    start = int(round(time.time() * MICROSECONDS))
    response = urllib2.urlopen(req).read()
    end = int(round(time.time() * MICROSECONDS))

    response_data = utils.unserialize_response(response)
    response_command = response_data['command']
    if response_command != HB and \
       response_data['command_epoch'] != self._parent.command_epoch:
        return
    response_success = response_data['success']
    response_params = response_data['params']
    assert(response_command == self._command)
    # Ignore timed out RPCoperations

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
    elif response_command == LOAD and response_success:
        if 'has_song' in response_params:
            self._parent.loaded_ips.put(response_params['ip'] + ':' + REPLICA_PORT)
            self._parent.loaded_ips_count += 1
    elif response_command == CHECK and response_success:
        if 'has_song' in response_params:
            self._parent.loaded_ips.put(response_params['ip'] + ':' + REPLICA_PORT)
            self._parent.loaded_ips_count += 1
        else:
            self._parent.not_loaded_ips.put(response_params['ip'] + ':' + REPLICA_PORT)          
            self._parent.not_loaded_ips_count += 1
    elif response_command == ENQUEUE:
        if 'enqueued' in response_params and response_success:
            self._parent.enqueued_acks += 1
    if DEBUG:
        print "ip:" + self._ip + ":" + str(response_data)
