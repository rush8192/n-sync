# Base music directory
MUSIC_DIR = 'music/'
REPLICA_IP_FILE = 'replica_ips.cfg'
EXT = '.mp3'
# enable more output printing
DEBUG = False

MICROSECONDS = 1000000
MILLISECONDS = 1000

# extra buffer to add to synchronize rpcs to account for unexpected delays
# and shitty pi CPU
EXTRA_BUFFER = 100*1000 # 100 milliseconds
ALLOWED_REPLICA_BUFFER = 400 # 400 microseconds

CLIENT_TIMEOUT = 20 #seconds
REPLICA_ACK_TIMEOUT = 5 # seconds
REPLICA_LOAD_TIMEOUT = 20 # seconds
REPLICA_RECOVERY_TIMEOUT = 1 # seconds

# port numbers
CLIENT_PORT = '8000' # for listening for client requests
REPLICA_PORT = '5000' # for sending music commands to replica

# replica endpoints
TIME_URL = '/time'
PLAY_URL = '/play'
STOP_URL = '/pause'
ENQUEUE_URL = '/enqueue'
DEQUEUE_URL = '/dequeue'
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
DEQUEUE = 'dequeue'
FAILSTOP = 'failstop'

# heartbeat config params
INITIAL_CALIBRATION_PINGS = 12
HEARTBEAT_INTERVAL = 2
HEARTBEAT_PAUSE = 0.5
QUEUE_SLEEP = 0.5

# initial pygame buffer size
INITIAL_BUFFER_SIZE = 512