mport sys
import urllib2
import argparse
import hashlib
import json
import os
from constants import *
import utils
import time

MASTER_IP = "192.168.1.138"
PORT = "8000"

def get_url(command):
    return "http://" + MASTER_IP + ":" + PORT + "/" + command

def play():
    url = get_url(PLAY)
    try:
        r = urllib2.urlopen(url)
        print utils.unserialize_response(r.read())
    except Exception:
        print "Error in Playing Song"

def forward():
    url = get_url(FORWARD)
    try:
        r = urllib2.urlopen(url)
        print utils.unserialize_response(r.read())
    except Exception:
        print "Error in Forwarding Song"

def backward():
    url = get_url(BACKWARD)
    try:
        r = urllib2.urlopen(url)
        print utils.unserialize_response(r.read())
    except Exception:
        print "Error in Backwarding Song"

def pause():
    url = get_url(PAUSE)
    print url
    try:
        r = urllib2.urlopen(url)
        print utils.unserialize_response(r.read())
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
    except Exception:
        print "Error in Checking Song"
    else:
        master_response = utils.unserialize_response(r.read())
        has_file = master_response['success']
        if not has_file:
            try:
                req = urllib2.Request(url)
            except Exception:
                print "Error in Uploading Song"
            else:
                d = {'song_bytes': song_bytes}
                req.add_data(utils.serialize_response(d))
                r = urllib2.urlopen(req)
                master_response = utils.unserialize_response(r.read())
    
        if not master_response['success']:
            print master_response['msg']
        print master_response['client_req_id']

def enqueue_song(song_path):
    load_song(song_path)
    assert(os.path.exists(song_path))
    with open(song_path, 'r') as f:
        song_bytes = f.read()
        song_hash = utils.hash_string(song_bytes)
    url = get_url(ENQUEUE) + "/" + song_hash
    try: 
        r = urllib2.urlopen(url)
    except Exception:
        print "Error in Enqueue Song"
    else:
        master_response = utils.unserialize_response(r.read())
        if master_response['success'] == True:
            print song_path + ' has been enqueued'
        else:
            print song_path + ' cannot be enqueued'
        print master_response['client_req_id']

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
    parser.add_argument('-q', type=str, default=None)
    args = parser.parse_args()
    start = time.time()
    op = None
    if args.pl:
        play()
        op = PLAY
    if args.pa:
        pause()
        op = PAUSE
    if args.f:
        forward()
        op = FORWARD
    if args.b:
        backward()
        op = BACKWARD
    if args.l != None:
        load_song(args.l)
        op = LOAD
    if args.q != None:
        enqueue_song(args.q)
        op = ENQUEUE
    print op + ' took ' + str(time.time() - start) + ' sec'
    


