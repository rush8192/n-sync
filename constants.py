# Base music directory
MUSIC_DIR = 'music/'
REPLICA_IP_FILE = 'replica_ips.cfg'
EXT = '.mp3'
# enable more output printing
DEBUG = False

MICROSECONDS = 1000000

# extra buffer to add to synchronize rpcs to account for unexpected delays
# and shitty pi CPU
EXTRA_BUFFER = 100*1000 # 100 milliseconds

CLIENT_TIMEOUT = 100 #seconds
REPLICA_ACK_TIMEOUT = 100 # seconds
REPLICA_LOAD_TIMEOUT = 100 # seconds
ENQUEUE_ACK_TIMEOUT = 100
# port numbers
CLIENT_PORT = '8000' # for listening for client requests
REPLICA_PORT = '5000' # for sending music commands to replica

# replica endpoints
TIME_URL = '/time'
PLAY_URL = '/play'
STOP_URL = '/pause'
ENQUEUE_URL = '/enqueue'
LOAD_URL = '/load'
CHECK_URL = '/check'

# Commands
HB = 'hb'
PLAY = 'play'
PAUSE = 'pause'
FORWARD = 'forward'
BACKWARD = 'backward'
ENQUEUE = 'enqueue'
LOAD = 'load'
CHECK = 'check'

# heartbeat config params
INITIAL_CALIBRATION_PINGS = 12
HEARTBEAT_PAUSE = 0.5

# initial pygame buffer size
INITIAL_BUFFER_SIZE = 512

