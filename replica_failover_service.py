import time

class ReplicaFailoverService():
  def __init__(self, replica_recovery):
    self._recovery = replica_recovery

  def start(self):
    while True:
      print "Entered Failover Service"
      print self._recovery._in_recovery.value
      time.sleep(2)
      print "Leaving Failover Service"