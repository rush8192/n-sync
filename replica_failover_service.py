import time
from constants import *
import threading 
import pickle
import pygame
import os
import Queue
import random
import utils
import urllib2
import multiprocessing
from master_replica_rpc import RPC

class ReplicaFailoverService(threading.Thread):
  def __init__(self, replica_parent):
    threading.Thread.__init__(self)
    self._parent = replica_parent
    self.command_epoch = 0
    self._master_ip = ""


  # recovers state from master; or if cant connect to master, retries getting elected after
  # a random number of failures
  def recover_state(self):
    status_update_dict = { "reset_election" : True }
    self._parent._state_queue.put(status_update_dict)
    num_master_retries = 10 + random.randint(0, 10)
    on_retry = 0
    while True:
      url = "http://" + self._parent._master_ip + ":" + REPLICA_FAIL_PORT + "/" + RECONNECT
      print "connecting to master failover service: " + url
      req = urllib2.Request(url, utils.serialize_response({'msg': 'yo'}))
      try:
        resp = urllib2.urlopen(req)
      except Exception:
        print "failed to reach master"
        on_retry += 1
        if on_retry > num_master_retries:
            return True # attempt to get elected again
        time.sleep(HEARTBEAT_PAUSE * 2)
      else:
        status_update_dict = { "new_master" : True }
        self._parent._state_queue.put(status_update_dict)
        response_data = utils.unserialize_response(resp.read())
        assert (response_data['msg'] == 'yo')
        break

    url = "http://" + self._parent._master_ip + ":" + REPLICA_FAIL_PORT + "/" + RECOVER
    data = {'song_hashes': []}

    # if music directory exists, get the filenames, keep extension on filenames!!!
    if os.path.exists(MUSIC_DIR): 
      for file_name in os.listdir(MUSIC_DIR):
        if (len(file_name) >= len(EXT)) and (file_name.count(EXT) != 0):
          data['song_hashes'].append(file_name)
    else:
      os.makedirs(MUSIC_DIR)

    req = urllib2.Request(url, utils.serialize_response(data))
    try:
      resp = urllib2.urlopen(req)
    except Exception:
      return False
    else:
      # TODO: add timestamp from master
      resp = resp.read()
      # response should be a ton of music mp3 files serialized into a dictionary
      response_data = utils.unserialize_response(resp)
      songs = response_data['params']['songs']
      master_queue = response_data['params']['master_queue']
      current_song = response_data['params']['current_song']
      self._parent._playlist_queue = master_queue
      self._parent._current_song = current_song
      #failed_file_names = []

      # need to update self._song_hashes in replica music server
      for file_name in songs:
        try:
            with open(file_name, 'w') as f:
              f.write(songs[file_name])
        except Exception:
            print 'song failed to download in replica failover'
            #failed_file_names.append(file_name)
        else:
            print 'successfully downloaded ' + file_name + ' in replica failover'
      return True


  def get_new_timeout_threshold(self):
    rand_timeout_component = random.randint(0, int(HEARTBEAT_INTERVAL * MICROSECONDS))
    self._timeout_threshold = rand_timeout_component + (1.5 * HEARTBEAT_INTERVAL * MICROSECONDS)

  def election_reconnect_or_fail(self):
    # first notify election service that we are eligible to cast votes
    # after 0.5 seconds if master hasnt been elected, try to get votes ourselves
    # finally, if we fail to get votes after 1 second, assume we are partitioned
    # and go into failure mode
    my_time = time.time()
    print "writing playlist state to file: " + str(my_time)
    with open(PLAYLIST_STATE_FILE, 'w') as f:
        data = utils.format_playlist_state(self._parent._playlist_queue, self._parent._current_song, \
                                            self._parent._master_term, self._parent._master_timestamp)
        f.write(data)
    print "notifying election service of failure"
    
    replica_url = 'http://' + self._parent._ip + ":" + VOTE_PORT + FAIL_URL
    r = RPC(self, VOTE, url=replica_url, ip=self._parent._ip, data={})
    r.start()
    
    time.sleep(0.5)
    if (time.time()*MICROSECONDS - self._parent._last_hb_ts) > self._timeout_threshold:
        print "failed to elect new master, requesting votes"
        queue_hash = utils.hash_string(pickle.dumps(self._parent._playlist_queue))
        status_update_dict = { "request_votes" : True, "queue_hash" : queue_hash, \
            "current_song": self._parent._current_song, "term":self._parent._master_term,\
            "timestamp" : self._parent._master_timestamp}
        self._parent._state_queue.put(status_update_dict)
        print "waiting for response"
        for i in range(0, 4):
            try:
                resp = self._parent._response_queue.get(True, 0.3)
                print "got response: " + str(resp)
                if "success" in resp:
                    self.get_new_timeout_threshold()
                    my_time = time.time()
                    print "won election, starting master process : " + str(my_time) 
                    os.system("./master.py -r " + str(self._parent._master_term + 1))
                    return
                else:
                    continue
            except Queue.Empty:
                continue
    else:
        replica_url = 'http://' + self._parent._ip + ":" + VOTE_PORT + UNFAIL_URL
        r = RPC(self, VOTE, url=replica_url, ip=self._parent._ip, data={})
        r.start()
    
    # wait for others to try to get elected again
    for i in range (0, 20):
        time.sleep(0.25)        
        # check last time for new master
        if (time.time()*MICROSECONDS - self._parent._last_hb_ts) <= self._timeout_threshold:
            my_time = time.time()
            print "someone won election: " + str(my_time)
            replica_url = 'http://' + self._parent._ip + ":" + VOTE_PORT + UNFAIL_URL
            r = RPC(self, VOTE, url=replica_url, ip=self._parent._ip, data={})
            r.start()
            status_update_dict = { "reset_election" : True }
            self._parent._state_queue.put(status_update_dict)
            return

    # if we get here, we should assume we have failed and enter failure mode
    print "FAILED: going into recovery mode"
    self.get_new_timeout_threshold()
    self._parent._in_recovery = True
    pygame.mixer.music.stop()

  def run(self):
    self.get_new_timeout_threshold()
    while True:
      if self._parent._last_hb_ts != None:
        if ((time.time()*MICROSECONDS - self._parent._last_hb_ts) > self._timeout_threshold and not self._parent._loading_song) and not self._parent._in_recovery:
            self.election_reconnect_or_fail()
        elif self._parent._in_recovery == True:
            if self.recover_state():
                self._parent._in_recovery = False
        time.sleep(0.15)
      else:
        time.sleep(0.15)

