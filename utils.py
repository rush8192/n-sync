import json
import socket
import flask 
import pickle
import hashlib
from constants import *

def format_rpc_response(success, command, params, msg='', command_epoch=None):
  resp = {'success': success, 'command':command, 'params': params}
  if msg != '':
    resp['msg'] = msg
  if command_epoch != None:
    resp['command_epoch'] = command_epoch 
  return resp

def format_client_response(success, command, params, msg='', client_req_id=None):
  resp = {'success': success, 'command': command, 'params': params}
  if msg != None:
    resp['msg'] = msg
  if client_req_id != None:
    resp['client_req_id'] =  client_req_id
  return resp

def serialize_response(res):
  return pickle.dumps(res)

def unserialize_response(res):
  return pickle.loads(res)

def get_music_path(song_hash):
  return MUSIC_DIR + song_hash + EXT

def get_ip_addr():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("google.com",80))
    ip_addr = s.getsockname()[0]
    s.close()
    return ip_addr

def hash_string(s):
  return hashlib.sha224(s).hexdigest()

class ReplicaRecovery():
  def __init__(self, in_recovery, last_hb_ts):
    self._in_recovery = in_recovery
    # array of [epoch, ts]
    self._last_hb_ts = last_hb_ts

def load_playlist_state(file_content):
    file_dict = pickle.loads(file_content)
    return (file_dict['playlist'], file_dict['current_song'], file_dict['term'], file_dict['timestamp'])

def format_playlist_state(playlist, current_song, term=0, timestamp=0):
  return pickle.dumps({'playlist': playlist, 'current_song': current_song, 'term':term, 'timestamp':timestamp})
