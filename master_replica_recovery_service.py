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

# Allows a replica to recover from a failure by getting state from master 
class MasterReplicaRecoveryService(multiprocessing.Process):
    def __init__(self, ip):
        multiprocessing.Process.__init__(self)
        self._ip = ip

    def recover_replica(self):
        data = utils.unserialize_response(request.get_data())
        replica_song_hashes = data['song_hashes']
        with open(PLAYLIST_STATE_FILE, 'r') as f:
            data = utils.unserialize_response(f.read())
            print data
            master_queue = data['playlist']
            current_song = data['current_song']
        missing_songs = {}

        print master_queue
        for song_hash in master_queue:
            print 'song_hash ' + str(song_hash)
            music_path = utils.get_music_path(song_hash)
            if (os.path.exists(music_path)) and (replica_song_hashes.count(song_hash + EXT) == 0):
                with open(music_path, 'r') as f:
                    song_bytes = f.read()
                missing_songs[song_hash + EXT] = song_bytes
        if current_song != None:
            music_path = utils.get_music_path(current_song)
            if (os.path.exists(current_song + EXT)) and (replica_song_hashes.count(current_song + EXT) == 0):
                with open(music_path, 'r') as f:
                    song_bytes = f.read()
                missing_songs[current_song + EXT] = song_bytes

        resp = utils.format_rpc_response(True, RECOVER, {'songs': missing_songs, 'master_queue': master_queue, 'current_song': current_song})
        return utils.serialize_response(resp)

    def reconnected_replica(self):
        print "RECONNECTING FUCKING REPLICA"
        data = utils.unserialize_response(request.get_data())
        if data['msg'] == 'yo':
            return utils.serialize_response({'msg': 'yo'})

    def run(self):
        self._app = Flask(__name__)
        # Register endpoints
        self._app.add_url_rule("/" + RECOVER, "recover_replica", \
                                self.recover_replica, methods=['GET', 'POST'])
        self._app.add_url_rule("/" + RECONNECT, 'reconnected_replica', \
                                self.reconnected_replica, methods=['GET', 'POST'])
        #self._app.debug = True
        self._app.run(host=self._ip, port=int(REPLICA_FAIL_PORT))

