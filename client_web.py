from flask import Flask, render_template
import sys
import urllib2
import argparse
import hashlib
import json
import os
from constants import *
import utils
import time
from flask_bootstrap import Bootstrap

MASTER_IP = "192.168.1.138"
PORT = "8000"

app = Flask(__name__)
Bootstrap(app)

def get_song_files():
    song_files = []
    all_files = os.listdir(MUSIC_DIR)
    for f in all_files:
        if f.count('.mp3') != 0:
            song_files.append(f)
    return song_files

def get_url(command):
    return "http://" + MASTER_IP + ":" + PORT + "/" + command

@app.route("/")
def index():
    global songfiles, playlist
    return render_template('index.html', song_files = song_files, playlist = playlist)

@app.route("/play")
def play():
    url = get_url(PLAY)
    try:
        r = urllib2.urlopen(url)
        resp = utils.unserialize_response(r.read())
    except Exception:
        resp = {"success": False, "msg": "Error in Playing Song"}
    return resp

@app.route("/pause")
def pause():
    url = get_url(PAUSE)
    try:
        r = urllib2.urlopen(url)
        resp = utils.unserialize_response(r.read())
    except Exception:
        resp = {"success": False, "msg": "Error in Pausing Song"}
    return resp

@app.route("/forward")
def forward():
    global playlist
    url = get_url(FORWARD)
    try:
        r = urllib2.urlopen(url)
        resp = utils.unserialize_response(r.read())
        if len(playlist) != 0:
            playlist.pop(0)
    except Exception:
        resp = {"success": False, "msg": "Error in Forwarding Song"}
    return resp

@app.route("/backward")
def backward():
    url = get_url(BACKWARD)
    try:
        r = urllib2.urlopen(url)
        resp = utils.unserialize_response(r.read())
    except Exception:
        resp = {"success": False, "msg": "Error in Backwarding Song"}
    return resp

@app.route("/load/<song_file>")
def load(song_file):
    song_path = MUSIC_DIR + song_file
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
    return 'load'

@app.route("/enqueue/<song_file>")
def enqueue(song_file):
    global playlist
    playlist.append(song_file)
    return 'songthing'
    song_path = MUSIC_DIR + song_file
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
            playlist.append(song_file)
        else:
            print song_path + ' cannot be enqueued'
        print master_response['client_req_id']
    return 'enqueue'

if __name__ == "__main__":
    song_files = get_song_files()
    loaded_songs = []
    playlist = []
    current_song = None
    app.run()