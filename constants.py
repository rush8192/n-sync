# Base music directory
MUSIC_DIR = 'music/'
REPLICA_IP_FILE = 'replica_ips.cfg'
# enable more output printing
DEBUG = False

MICROSECONDS = 1000000

# extra buffer to add to synchronize rpcs to account for unexpected delays
# and shitty pi CPU
EXTRA_BUFFER = 100*1000 # 100 milliseconds

CLIENT_TIMEOUT = 5 #seconds
REPLICA_ACK_TIMEOUT = 1 # seconds
REPLICA_LOAD_TIMEOUT = 10 # seconds
# port numbers
CLIENT_PORT = '8000' # for listening for client requests
REPLICA_PORT = '5000' # for sending music commands to replica

# replica endpoints
TIME_URL = '/time'
PLAY_URL = '/play'
STOP_URL = '/pause'
QUEUE_URL = '/queue'

# Commands
HB = 'hb'
PLAY = 'play'
PAUSE = 'pause'
FORWARD = 'forward'
BACKWARD = 'backward'
ENQUEUE = 'enqueue'
LOAD = 'load'
# heartbeat config params
INITIAL_CALIBRATION_PINGS = 12
HEARTBEAT_PAUSE = 0.5

