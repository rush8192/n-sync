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

class MasterReplicaRecoveryService(threading.Thread):
    def __init__(self, parent):
        threading.Thread.__init__(self)
        self._parent = parent

    def recover_replica(self):
        data = utils.unserialize_response(request.get_data())
        replica_song_hashes = data['song_hashes']
        master_queue = self._parent._playlist_queue
        current_song = self._parent._current_song
        missing_songs = {}

        for song_hash in master_queue:
            music_path = utils.get_music_path(song_hash)
            if (os.path.exists(music_path)) and (replica_song_hashes.count(song_hash + EXT) == 0):
                with open(music_path, 'r') as f:
                    song_bytes = f.read()
                missing_songs[song_hash + EXT] = song_bytes
        
        music_path = utils.get_music_path(current_song)
        if (current_song != None) and (os.path.exists(current_song + EXT)) and (replica_song_hashes.count(current_song + EXT) == 0):
            with open(music_path, 'r') as f:
                song_bytes = f.read()
            missing_songs[current_song + EXT] = song_bytes

        resp = utils.format_rpc_response(True, RECOVER, {'songs': missing_songs, 'master_queue': master_queue, 'current_song': current_song})
        return utils.serialize_response(resp)

    def run(self):
        self._app = Flask(__name__)
        # Register endpoints
        self._app.add_url_rule("/" + RECOVER, "recover_replica", \
                                self.recover_replica, methods=['GET', 'POST'])
        self._ip = "127.0.0.1"
        self._app.run(host=self._ip, port=int(REPLICA_FAIL_PORT))