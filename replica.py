#!/usr/bin/python

import pygame
import time
import flask
import multiprocessing
import Queue
import socket
import sys
import threading
from flask import Flask
from flask import request
from constants import *
import utils
import os
import pickle
import collections
from replica_music_service import ReplicaMusicService
from replica_failover_service import ReplicaFailoverService

# reads initial queue (if present) then starts replica music service
if __name__ == "__main__":
    playlist_queue = collections.deque([])    
    # start replica service
    ip_addr = utils.get_ip_addr()
    print 'Replica IP Address is:' + ip_addr 
    pygame_mixer_queue = multiprocessing.Queue()
    pygame_mixer = pygame.mixer()
    pygame_mixer.init()
    pygame_mixer_queue.put(pygame_mixer)
    replica_recovery = utils.ReplicaRecovery(\
                           multiprocessing.Value('b', False), \
                           multiprocessing.Array('d', [0, -1]))
    replica_service = ReplicaMusicService(playlist_queue, \
                                          ip_addr, \
                                          replica_recovery, \
                                          pygame_mixer_queue)
    replica_service.start()

    replica_failover = ReplicaFailoverService(replica_recovery, \
                                              pygame_mixer_queue)
    replica_failover.start()

