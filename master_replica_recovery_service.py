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

class MasterReplicaRecoveryService(multiprocessing.Process):
    def __init__(self, ip):
        self._ip = ip

    def recover_replica(self):
        data = utils.unserialize_response(request.get_data())
        replica_song_hashes = data['song_hashes']
        missing_songs = {}
        for file_name in os.listdir(MUSIC_DIR):
            if (file_name.count(EXT) != 0) and (replica_song_hashes.count(file_name) == 0):
                with open(file_name, 'r') as f:
                    song_bytes = f.read()
                missing_songs[file_name] = song_bytes
        resp = utils.format_rpc_response(True, RECOVER, {'songs': missing_songs})
        return utils.serialize_response(resp)

    def run(self):
        self._app = Flask(__name__)
        # Register endpoints
        self._app.add_url_rule("/" + RECOVER, "recover_replica", \
                                self.recover_replica, methods=['GET', 'POST'])
        self._ip = "127.0.0.1"
        self._app.run(host=self._ip, port=int(REPLICA_FAIL_PORT))