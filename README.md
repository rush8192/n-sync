TODO:
Sunday/Monday
Rush:
1) Master failover

Before Paper:
1) LRU Cache on Disk (S)
2) Save playlist to disk on replicas (S)
3) Check all the locks (S)
4) Make sure failover works

4) Separate load service for bulk load so client doesn't have to wait (no guarantees it'll finish, but attempt to create cache) / Whisper protocol (can be used for stagger recovery) (W)
5) Better way to get master/replica time estimates (W)
6) Try joining to playing music right after recovery: not sure if possible with pygame (W)

Future Work after paper:
1) P2P File Distribution: Stagger recovery?
2) Client front end
3) ZeroMQ/C++ Music Server?