import time

class ReplicaFailoverService():
  def __init__(self, replica_recovery):
    self._recovery = replica_recovery

  def start(self):
    while True:
      print 'runnin replica failover service'
      print self._recovery._in_recovery
      time.sleep(2)