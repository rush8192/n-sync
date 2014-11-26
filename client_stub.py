# client stub - better way to pass messages to a master using argparse

import sys
import urllib2
import argparse
import hashlib
import json
import os
from constants import *
import utils

MASTER_IP = "127.0.0.1" #"192.168.1.197"
PORT = "8000"

def get_url(command):
    return "http://" + MASTER_IP + ":" + PORT + "/" + command

def play():
    url = get_url(PLAY)
    try:
        r = urllib2.urlopen(url)
        print r.read()
    except Exception:
        print "Error in Playing Song"

def forward():
    url = get_url(FORWARD)
    try:
        r = urllib2.urlopen(url)
        print r.read()
    except Exception:
        print "Error in Forwarding Song"

def backward():
    url = get_url(BACKWARD)
    try:
        r = urllib2.urlopen(url)
        print r.read()
    except Exception:
        print "Error in Backwarding Song"

def pause():
    url = get_url(PAUSE)
    print url
    try:
        r = urllib2.urlopen(url)
        print r.read()
    except Exception:
        print "Error in Pausing Song"

# Send song hash first, then full song if needed
def load_song(song_path):
    m = hashlib.md5()
    assert(os.path.exists(song_path))
    with open(song_path, 'r') as f:
        song_bytes = f.read()
        song_hash = hashlib.sha224(song_bytes).hexdigest()
    url = get_url(LOAD) + "/" + song_hash
    try:
        r = urllib2.urlopen(url)
        master_response = r.read()
        resp = utils.unserialize_response(master_response)
        has_file = resp['result']
        if not has_file:
            req = urllib2.Request(url)
            d = {'song_bytes': song_bytes}
            req.add_data(utils.serialize_response(d))
            r = urllib2.urlopen(req)
            master_response = r.read()
            print master_response
    except Exception:
        print "Error in Uploading Song to Queue"

if __name__ == "__main__":
    if (len(sys.argv) == 1):
        print "Usage:"
        print "python ./client_stub.py -[pfbu]"
        print "-p play, -f forward, -b backward, -u pause"
        sys.exit()

    parser = argparse.ArgumentParser(description='Client Stub Nsync.')
    parser.add_argument('-pl', action='store_true', help='play first song')
    parser.add_argument('-pa', action='store_true', help='pause at master offset')
    parser.add_argument('-f', action='store_true', help='move to next song')
    parser.add_argument('-b', action='store_true', help='move back in queue')
    parser.add_argument('-l', type=str, default=None)
    args = parser.parse_args()
    if args.pl:
        play()
    if args.pa:
        pause()
    if args.f:
        forward()
    if args.b:
        backward()
    if args.l != None:
        load_song(args.l)


