# client stub - better way to pass messages to a master using argparse

import sys
import urllib2
import argparse
import hashlib
import json
import os

MASTER_IP = "127.0.0.1" #"192.168.1.197"
PORT = "8000"

def get_url(command):
    return "http://" + MASTER_IP + ":" + PORT + "/" + command

def play():
    url = get_url("play")
    try:
        r = urllib2.urlopen(url)
        print r.read()
    except
        print "Error in Playing Song"

def forward():
    url = get_url("forward")
    try:
        r = urllib2.urlopen(url)
        print r.read()
    except
        print "Error in Forwarding Song"

def backward():
    url = get_url("backward")
    try:
        r = urllib2.urlopen(url)
        print r.read()
    except
        print "Error in Backwarding Song"

def pause():
    url = get_url("pause")
    try:
        r = urllib2.urlopen(url)
        print r.read()
    except
        print "Error in Pausing Song"

# Send song hash first, then full song if needed
def enqueue_song(song_path):
    m = hashlib.md5()
    assert(os.path.exists(song_path))
    with open(song_path, 'r') as f:
        song_bytes = f.read()
        song_hash = hashlib.sha224(song_bytes).hexdigest()
    url = get_url("queue") + "/" + song_hash
    try:
        r = urllib2.urlopen(url)
        master_response = r.read()
        print master_response
        has_file = json.loads(master_response, encoding='utf-8')['result']
        if not has_file:
            req = urllib2.Request(url)
            print len(song_bytes)
            req.add_data(song_bytes)
            r = urllib2.urlopen(req)
    except Exception:
        print "Error in Uploading Song to Queue"

if __name__ == "__main__":
    if (len(sys.argv) == 1):
        print "Usage:"
        print "python ./client_stub.py -[pfbu]"
        print "-p play, -f forward, -b backward, -u pause"
        sys.exit()

    parser = argparse.ArgumentParser(description='Client Stub Nsync.')
    parser.add_argument('-p', action='store_true', help='play first song')
    parser.add_argument('-u', action='store_true', help='unpause at master offset')
    parser.add_argument('-f', action='store_true', help='move to next song')
    parser.add_argument('-b', action='store_true', help='move back in queue')
    parser.add_argument('-q', type=str, default=None)
    args = parser.parse_args()
    if args.p:
        play()
    if args.u:
        pause()
    if args.f:
        forward()
    if args.b:
        backward()
    if args.q != None:
        enqueue_song(args.q)