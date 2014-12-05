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

# tune this! TODO
MAX_CLOCK_DRIFT = 10000
CALIBRATION_DATA_POINTS = 10

MAX_OFFSET_DIF = 100

CLIENT_TIMEOUT = 200 #seconds
REPLICA_ACK_TIMEOUT = 1 # seconds
REPLICA_LOAD_TIMEOUT = 200 # seconds
REPLICA_RECOVERY_TIMEOUT = 1 # seconds

# port numbers
CLIENT_PORT = '8000' # for listening for client requests
REPLICA_FAIL_PORT = '3245' # telephone number for fail
REPLICA_PORT = '5000' # for sending music commands to replica
VOTE_PORT = '8683' # tel number for vote

# replica endpoints
TIME_URL = '/time'
PLAY_URL = '/play'
STOP_URL = '/pause'
ENQUEUE_URL = '/enqueue'
DEQUEUE_URL = '/dequeue'
LOAD_URL = '/load'
CHECK_URL = '/check'

VOTE_URL = '/vote'
FAIL_URL = '/fail'
UNFAIL_URL = '/unfail'

PRELOAD_URL = '/preload'
POSTLOAD_URL = '/postload'

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
RECOVER = 'recover'
RECONNECT = 'reconnect'

PRELOAD = 'preload'
POSTLOAD = 'postload'

VOTE = 'vote'

# heartbeat config params
INITIAL_CALIBRATION_PINGS = 12
HEARTBEAT_INTERVAL = 2.5
HEARTBEAT_PAUSE = 0.5
QUEUE_SLEEP = 0.5
MAX_BACKOFF = 4.1

# election config
ELECTION_TIMEOUT = 5 # seconds

# initial pygame buffer size
INITIAL_BUFFER_SIZE = 512

PLAYLIST_STATE_FILE = 'backup/playlist_state'


