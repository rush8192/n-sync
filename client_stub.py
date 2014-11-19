# client stub - simple way to pass messages to a master using
# one flag at a time (see usage below)

import sys
import urllib2

MASTER_IP = "192.168.1.197"
PORT = "8000"

def get_url(command):
    return "http://" + MASTER_IP + ":" + PORT + "/" + command
    
def play():
    url = get_url("play")
    r = urllib2.urlopen(url)
    print r.read()

def forward():
    url = get_url("forward")
    r = urllib2.urlopen(url)
    print r.read()

def backward():
    url = get_url("backward")
    r = urllib2.urlopen(url)
    print r.read()

def unpause():
    url = get_url("pause")
    r = urllib2.urlopen(url)
    print r.read()
    
def send_queue(queue):
    url = get_url("queue") + "/" + queue
    r = urllib2.urlopen(url)
    print r.read()

def main(argv):
    if (len(argv) == 1):
        print "usage:"
        print "python ./client_stub.py -[pfbu]"
        print "-p = play, -f = forward, -b backward, -u pause"
        return -1
    if (len(argv) == 2):
        if argv[1] == "-p":
            play()
        if argv[1] == "-f":
            forward()
        if argv[1] == "-b":
            backward()
        if argv[1] == "-u":
            unpause()
    if (len(argv) == 3 and argv[1] == "-q"):
        queue_file = argv[2]
        send_queue(queue_file)

sys.exit(main(sys.argv))

