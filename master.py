#!/usr/local/bin/python

import json
import sys
import threading
import time
import urllib2

#'192.168.1.197:5000', '192.168.1.244:5000', '192.168.1.138:5000'
IP_ADDR = [ '192.168.1.138:5000', '192.168.1.244:5000', '192.168.1.197:5000' ]
TIME_URL = '/time'
PLAY_URL = '/play'
STOP_URL = '/pause'

update_lock = threading.Lock()
latency_by_ip = {}
clock_difference_by_ip = {}

DEBUG = True

MICROSECONDS = 1000000

import threading

# Class that handles all rpcs
class RPC(threading.Thread):
  def set_ip(self, ip):
    self._ip = ip

  def set_url(self, url):
    self._hb = False
    self._url = url
    
  def set_json(self, json):
    self._json = json
    
  def set_heartbeat(self, heartbeat):
    self._hb = heartbeat

  def run(self):
    req = urllib2.Request(self._url, self._json, {'Content-Type': 'application/json'})
    start = int(round(time.time() * MICROSECONDS))
    response = urllib2.urlopen(req)
    end = int(round(time.time() * MICROSECONDS))
    
    if self._hb:
        update_latency(self._ip, (end - start) / 2.0)
    
    data = json.load(response)
    if "time" in data and self._hb:
        # estimate for other computers clock time: their time, 
        # plus return network latency, which we approximate with (end-start)/2
        clock_estimate = int(data["time"]) + (end - start) / 2
        diff = clock_estimate - end
        update_clock_diff(self._ip, diff)
    print "ip:" + self._ip + ":" + str(data)

def update_clock_diff(ip, diff):
    with update_lock:
        cur_avg_diff = clock_difference_by_ip[ip][0]
        cur_num_datapoints = clock_difference_by_ip[ip][1]
        cur_max_diff = clock_difference_by_ip[ip][2]
        new_avg = (cur_avg_diff*cur_num_datapoints + diff) / (1.0 + cur_num_datapoints)
        clock_difference_by_ip[ip][1] += 1
        if (clock_difference_by_ip[ip][1] == 1): # skip first ping; tends to be noisy
            return
        clock_difference_by_ip[ip][0] = new_avg
        if (diff > cur_max_diff):
            clock_difference_by_ip[ip][2] = diff
        if (DEBUG):
            print "avg diff for ip:" + ip + ":" + str(new_avg) + ":" + str(diff)

def update_latency(ip, latency):
    with update_lock:
        cur_avg_latency = latency_by_ip[ip][0]
        cur_num_datapoints = latency_by_ip[ip][1]
        cur_max_latency = latency_by_ip[ip][2]
        new_avg = (cur_avg_latency*cur_num_datapoints + latency) / (1.0 + cur_num_datapoints)
        latency_by_ip[ip][0] = new_avg
        latency_by_ip[ip][1] += 1
        if (latency > cur_max_latency):
            latency_by_ip[ip][2] = latency
        if (DEBUG):
            print str("avg latency(one-way) for ip:" + ip + ":" + str(new_avg))

def heartbeat(ip):
    # spawn new thread, which does an http request to fetch the current timestamp
    # from a replica
    r = RPC()
    r.set_url('http://' + ip + TIME_URL)
    r.set_ip(ip)
    r.set_json(json.dumps({"foo":"bar"}))
    r.set_heartbeat(True)
    r.start()

def main(argv):

    song_name = None
    if len(argv) > 1:
        song_name = argv[1]

    # default to 0
    for ip in IP_ADDR:
        latency_by_ip[ip] = [0, 0, 0]
        clock_difference_by_ip[ip] = [0, 0, 0]
        
    # get initial latency information
    for i in range(0,20):
        for ip in IP_ADDR:
            heartbeat(ip)
        time.sleep(0.5)
        
    #return
    time.sleep(5)
    
    total_max_delay = 0
    for ip in IP_ADDR:
        total_max_delay += latency_by_ip[ip][2]
        
    delay_buffer = int(2*total_max_delay)
    # global start time that all replicas must agree on
    start_time = int(round(time.time() * MICROSECONDS)) + delay_buffer + 2*1000*1000
    
    # choose global start time, make local adjustments
    ARTIFICIAL_DELAY = 0*1000
    on_replica = 0
    print "global start target: " + str(start_time) + " delay buffer:" + str(delay_buffer)
    for ip in IP_ADDR:
        local_start = start_time# + int(clock_difference_by_ip[ip][0]) #+ on_replica*ARTIFICIAL_DELAY
        print "ip:" + ip + " diff:" + str(int(clock_difference_by_ip[ip][0])) + " start:" + str(local_start)
        
        # each rpc runs on its own thread
        r = RPC()
        r.set_url('http://' + ip + PLAY_URL)
        r.set_ip(ip)
        
        if song_name == None:
            start_json = {"start_time":local_start}
        else:
            start_json = {"start_time":local_start, "song":song_name}
        
        r.set_json(json.dumps(start_json))
        r.set_heartbeat(False)
        
        # send play command for local start time
        r.start()
        
        on_replica += 1
    
    time.sleep(1)
    
    # Intermediate heartbeats
    
    #for i in range(0,10):
    #    for ip in IP_ADDR:
    #        heartbeat(ip)
    #    time.sleep(3)
        
    time.sleep(150)
        
    # set stop time in same fashion as start time 
    stop_time = int(round(time.time() * MICROSECONDS)) + delay_buffer
    for ip in IP_ADDR:
        local_stop = stop_time + int(clock_difference_by_ip[ip][0])
        r = RPC()
        r.set_url('http://' + ip + STOP_URL)
        r.set_ip(ip)
        r.set_json(json.dumps({"stop_time":local_stop}))
        r.set_heartbeat(False)
        r.start()
        #time.sleep(20)
        
    
sys.exit(main(sys.argv))
