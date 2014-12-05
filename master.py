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
from master_music_service import MasterMusicService
from master_replica_recovery_service import MasterReplicaRecoveryService
import collections

# main master method: set up services (music service and client listener)
if __name__ == "__main__":
    # load replicas IPs from file
    REPLICA_IP_ADDRS = []
    with open(REPLICA_IP_FILE, "r") as f:
        for ip_addr in f:
            REPLICA_IP_ADDRS.append(ip_addr.strip() + ':' + REPLICA_PORT)
    # determine our IP, start client listener
    print REPLICA_IP_ADDRS

    ip_addr = utils.get_ip_addr()
    command_queue = multiprocessing.Queue()
    status_queue = multiprocessing.Queue()
    playlist_queue = collections.deque([])

    term = 0
    my_current_song = None
    if len(sys.argv) == 3 and sys.argv[1] == "-r":
        with open(PLAYLIST_STATE_FILE) as f:
            playlist_queue, my_current_song, term, timestamp = utils.load_playlist_state(f.read())
        term = int(sys.argv[2])
            


    client_listener_service = \
        MasterClientListenerService(ip_addr, command_queue, status_queue)
    client_listener_service.start()

    # start service that listens for client commands from above process
    # and plays music when instructed
    # playlist_queue.append('84f73f239e681466eb9c9c3adc7e4c15355b538f52b93f7015241348')
    music_server = \
        MasterMusicService(REPLICA_IP_ADDRS, playlist_queue, \
                        command_queue, status_queue, term, ip_addr, my_current_song)
    music_server.start()

    replica_recovery_service = MasterReplicaRecoveryService(ip_addr)
    replica_recovery_service.start()
