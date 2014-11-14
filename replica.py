#!/usr/bin/python

import pygame
import time
import flask
from flask import Flask
from flask import request

app = Flask(__name__)

PRELOAD = True
    
@app.route("/time", methods=['POST'])
def get_time():
    nanos = int(round(time.time() * 1000000))
    #print request.json['foo']
    f = { "time" : nanos }
    return flask.jsonify(**f)

# start_time
# offset (optional)
@app.route("/play", methods=['POST'])
def start_play():
    content = request.json
    start_time = content['start_time']
    offset = 0.0
    if 'offset' in content:
        offset = content['offset']
    song_name = None
    if 'song' in content:
        song_name = content['song']
    if PRELOAD and song_name != None:
        pygame.mixer.music.load(song_name)
        print song_name
    start_nanos = int(round(time.time() * 1000000))
    while (start_nanos + 400 < start_time):
        start_nanos = int(round(time.time() * 1000000))
    pygame.mixer.music.play(1)
    nanos = int(round(time.time() * 1000000))
    time.sleep(2) # allow mp3 thread to start
    #print str(nanos - start_nanos)
    print str(nanos)
    print "start:" + str(start_nanos)
    f = { "time": nanos }
    return flask.jsonify(**f)

@app.route("/pause", methods=['POST'])
def pause_play():
    content = request.json
    stop_time = content['stop_time']
    stop_nanos = int(round(time.time() * 1000000))
    if (stop_nanos < stop_time):
        time.sleep((stop_time - stop_nanos) / 1000000.0)
    pygame.mixer.music.pause()
    offset = pygame.mixer.music.get_pos()
    nanos = int(round(time.time() * 1000000))
    print str(offset)
    f = { "time": nanos, "offset":  offset}
    return flask.jsonify(**f)

if __name__ == "__main__":
    pygame.mixer.init(buffer=512)
    with open("music.cfg") as music_config:
        song_name = music_config.readline()[:-1]
    pygame.mixer.music.load(song_name)
    app._song_name = song_name
    #app.debug = True
    with open("network.cfg") as net_config:
        ip_addr = net_config.readline()[:-1]
    app.run(host=ip_addr)
