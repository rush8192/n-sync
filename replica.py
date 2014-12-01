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

if __name__ == "__main__":    
    # start replica service
    ip_addr = utils.get_ip_addr()

    replica_service = ReplicaMusicService(collections.deque(['84f73f239e681466eb9c9c3adc7e4c15355b538f52b93f7015241348']), ip_addr)
    replica_service.start()
