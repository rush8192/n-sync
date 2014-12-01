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
  def __init__(self, parent, command, ip, url, data, master_ip):
    threading.Thread.__init__(self)
    self._parent = parent
    self._command = command
    self._ip = ip
    self._url = url
    self._data = data
    self._master_ip = master_ip
    self._data['command_epoch'] = self._parent.command_epoch

  # run the rpc; time it and record response depending on RPC type string
  def run(self):
    self._data['master_ip'] = self._master_ip

    request_data = utils.serialize_response(self._data)
    req = urllib2.Request(self._url, request_data) 
    start = int(round(time.time() * MICROSECONDS))
    # TODO: deal with timeout error
    response = urllib2.urlopen(req).read()
    end = int(round(time.time() * MICROSECONDS))

    response_data = utils.unserialize_response(response)
    # Short circuit out to prevent races, ignore timed out rpc calls
    if response_data['command_epoch'] != self._parent.command_epoch:
        return 

    response_command = response_data['command']
    response_success = response_data['success']
    response_params = response_data['params']
    assert(response_command == self._command)

    if response_success:
        # Response received from replica
        self._parent.rpc_response_acks += 1
        # Heartbeat time delay estimate
        if response_command == HB:
            # Replica_playing is True if playing or paused
            # False if song stopped
            replica_playing = int(response_params['replica_playing'])
            response_time = int(response_params['time'])
            self._parent.update_latency(self._ip, (end - start) / 2.0)
            if not replica_playing:
                self._parent.rpc_not_playing_acks += 1
            # estimate for other computers clock time: their time, 
            # plus return network latency, which we approximate with (end-start)/2
            clock_estimate = response_time + (end - start) / 2
            diff = clock_estimate - end
            self._parent.update_clock_diff(self._ip, diff)
        # Check the offsets in PAUSE
        elif response_command == PAUSE:
            response_offset = int(response_params['offset'])
            if response_offset > -1:
                self._parent.rpc_offsets.append(response_offset)
        # Check if song has loaded/not loaded on replica
        elif response_command == LOAD:
            if 'has_song' in response_params:
                self._parent.rpc_loaded_ips.put(response_params['ip'] + ':' + REPLICA_PORT)
        elif response_command == CHECK:
            if 'has_song' in response_params:
                self._parent.rpc_loaded_ips.put(response_params['ip'] + ':' + REPLICA_PORT)
            else:
                self._parent.rpc_not_loaded_ips.put(response_params['ip'] + ':' + REPLICA_PORT)          
    if DEBUG:
        print "ip:" + self._ip + ":" + str(response_data)
