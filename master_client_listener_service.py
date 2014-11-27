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

        # client request id 
        self._client_req_id = 0

    def inc_client_req_id(self):
        self._client_req_id += 1
        return self._client_req_id
    # TODO: Assign IDs to each command instance to avoid timeout bug
    def wait_on_master_music_service(self):
        status = None
        i = 0
        while(True):
            if (i == 50):
                break
            try:
                status = self._status_queue.get(False)
            except Queue.Empty:
                time.sleep(CLIENT_TIMEOUT / 50.0)
                i += 1
            else:
                if self._client_req_id == status['client_req_id']:
                    break
        if status == None:
            status = utils.format_client_response(False, TIMEOUT, {}, msg='timeout from master')
        return utils.serialize_response(status)

    # TODO: modify this command to accept client request and return response to client
    # currently takes one text command in the url; passes that text command through
    # a Queue to the Master Music synchronizer process, which then executes the command
    # and returns the response message to this process. Waits for a specified timeout
    # to receive a response status from the queue
    # endpoint: /<command_string>
    def execute_command(self, command):
        self.inc_client_req_id()
        if command in [PLAY, PAUSE, FORWARD, BACKWARD]:
            command_info = {'command':command, 'params':{}, 'client_req_id': self._client_req_id}
            self._command_queue.put(command_info)
            return self.wait_on_master_music_service()
        else:
            return utils.serialize_response(utils.format_client_response(True, command, {}))

    # Add a song to our playlist queue
    # endpoint: /queue/<song_hash>
    def enqueue_song(self, song_hash):
        self.inc_client_req_id()
        print 'in enqueue song client master'
        command_info = {'command':ENQUEUE, 'params':{'song_hash':song_hash}, 'client_req_id': self._client_req_id}
        if os.path.exists(MUSIC_DIR + song_hash + EXT):
            # verify song exists on >= f+1 replicas and in their playlist
            # queues
            self._command_queue.put(command_info)
            return self.wait_on_master_music_service()
        # song doesn't exist on master, get the song from the client
        else:
            return utils.serialize_response(utils.format_client_response(False, ENQUEUE, {}, 'Requested song to enqueue does not exist'))

    # Load song into master
    # endpoint /load/<song_hash>
    def load_song(self, song_hash):
        self.inc_client_req_id()
        command_info = {'command':LOAD, 'params':{'song_hash':song_hash}, 'client_req_id': self._client_req_id}
        if request.method == 'GET':
            if os.path.exists(MUSIC_DIR + song_hash + EXT):
                self._command_queue.put(command_info)
                return self.wait_on_master_music_service()
            # song doesn't exist on master, get the song from the client
            else:
                return utils.serialize_response(utils.format_client_response(False, LOAD, {}, msg='Master does not have requested song'))
        elif request.method == 'POST':
            data = utils.unserialize_response(request.get_data())
            with open(MUSIC_DIR + song_hash + EXT, 'w') as f:
                f.write(data['song_bytes'])
            self._command_queue.put(command_info)
            return self.wait_on_master_music_service()

    def run(self):
        self._app = Flask(__name__)
        # Register endpoints
        self._app.add_url_rule("/" + ENQUEUE + "/<song_hash>", "enqueue_song", \
                                self.enqueue_song, methods=['GET', 'POST'])
        self._app.add_url_rule("/<command>", "execute_command", \
                                self.execute_command)
        self._app.add_url_rule("/" + LOAD + "/<song_hash>", "load_song", \
                                self.load_song, methods=['GET', 'POST'])
        #self._app.debug = True
        self._ip = "127.0.0.1"
        self._app.run(host=self._ip, port=int(CLIENT_PORT))


