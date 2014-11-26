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

    client_listener_service = \
        MasterClientListenerService(ip_addr, command_queue, status_queue)
    client_listener_service.start()
        
    # start service that listens for client commands from above process
    # and plays music when instructed
    music_server = \
     MasterMusicService(REPLICA_IP_ADDRS, playlist_queue, \
                        command_queue, status_queue)
    music_server.start()