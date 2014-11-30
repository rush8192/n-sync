import time
from constants import *
import threading 

class ReplicaFailoverService(threading.Thread):
  def __init__(self, replica_parent):
    threading.Thread.__init__(self)
    self._replica_parent = replica_parent

  def run(self):
    while True:
      #if (time.time()*MICROSECONDS - self._recovery._last_hb_ts[1]) > (2 * HEARTBEAT_PAUSE * MICROSECONDS):
      #  print "Entered Failover Service"
      #  self._recovery._in_recovery.value = True
      #  pygame_mixer = self._pygame_mixer_queue.get(True)
      #  pygame_mixer.stop()
      #  self.recover_state()
      #  self._recovery._in_recovery.value = False
      #  self._pygame_mixer_queue.put(pygame_mixer)
      #  print "Leaving Failover Service"
      time.sleep(REPLICA_RECOVERY_TIMEOUT)