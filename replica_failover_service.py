import time
from constants import *
import threading 

class ReplicaFailoverService(threading.Thread):
  def __init__(self, replica_parent):
    threading.Thread.__init__(self)
    self._parent = replica_parent
    self._master_ip = replica_parent._master_ip

  def recover_state(self):
    print 'in recovery state'
    url = "http://" + self._master_ip + ":" + REPLICA_FAIL_PORT + "/" + RECOVER
    data = {'song_hashes': []}

    # if music directory exists, get the filenames, keep extension on filenames!!!
    if os.path.exists(MUSIC_DIR): 
      for file_name in os.listdir(MUSIC_DIR):
        if (len(file_name) >= len(EXT)) and (file_name.count(EXT) != 0):
          data['song_hashes'].append(file_name)
    else:
      os.makedirs(MUSIC_DIR)

    req = urllib2.Request(url, utils.serialize_response(data))
    resp = urllib2.urlopen(req).read()
    # response should be a ton of music mp3 files serialized into a dictionary
    response_data = utils.unserialize_response(resp)
    songs = response_data['params']['songs']
    master_queue = response_data['params']['master_queue']
    current_song = response_data['parans']['current_song']
    self._parent._playlist_queue = master_queue
    self._parent._current_song = current_song
    #failed_file_names = []

    # need to update self._song_hashes in replica music server
    for file_name in songs:
      try:
        with open(file_name, 'w') as f:
          f.write(songs[file_name])
        except Exception:
          print 'song failed to download in replica failover  fuckfuckfuck'
          #failed_file_names.append(file_name)
        else:
          print 'successfully downloaded ' + file_name + ' in replica failover'
    return
  # if len(failed_file_names) == 0:
  #   resp = utils.format_rpc_response(True, RECOVER, {})
  # else:
  #   resp = utils.format_rpc_response(False, RECOVER, {}, 'msg': 'failed to recover ' + str(len(failed_file_names)) + ' songs')
  # return resp

  def run(self):
    while True:
      print "Entered Failover Service"
      print self._parent._last_hb_ts
      if (time.time()*MICROSECONDS - self._parent._last_hb_ts) > (2 * HEARTBEAT_INTERVAL * MICROSECONDS) or self._parent._in_recovery == True:
        self._parent._in_recovery = True
        pygame.mixer.music.stop()
        self.recover_state()
        self._parent._in_recovery = False
      time.sleep(0.1)

