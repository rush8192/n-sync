import time
from constants import *

class ReplicaFailoverService():
  def __init__(self, replica_recovery, pygame_mixer_queue):
    self._recovery = replica_recovery
    self._pygame_mixer_queue = pygame_mixer_queue

  def recover_state(self):
    print 'in recovery state'

  def start(self):
    while True:
      print "Entered Failover Service"
      print self._recovery._last_hb_ts[1]
      if (time.time()*MICROSECONDS - self._recovery._last_hb_ts[1]) > (2 * HEARTBEAT_PAUSE * MICROSECONDS):
        self._recovery._in_recovery.value = True
        pygame_mixer = self._pygame_mixer_queue.get(True)
        pygame_mixer.stop()
        self.recover_state()
        self._pygame_mixer_queue.put(pygame_mixer)
      print "Leaving Failover Service"