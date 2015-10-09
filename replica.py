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
from election_service import ReplicaElectionService


if __name__ == "__main__":    
    # start replica service
    ip_addr = utils.get_ip_addr()

    response_queue = multiprocessing.Queue()
    state_queue = multiprocessing.Queue()
    replica_service = ReplicaMusicService(collections.deque([]), ip_addr, state_queue, response_queue)
    election_service = ReplicaElectionService(ip_addr, state_queue, response_queue)
    replica_service.start()
    election_service.start()
