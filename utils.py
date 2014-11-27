import json
import socket
import flask 
import pickle
import hashlib

def format_rpc_response(success, command, params, msg='', command_epoch=None):
  resp = {'success': success, 'command':command, 'params': params}
  if msg != '':
    resp['msg'] = msg
  if command_epoch != None:
    resp['command_epoch'] = command_epoch
  return resp

<<<<<<< Updated upstream
def format_client_response(success, command, params, msg='', client_req_id=None):
=======
def format_client_response(success, command, params, msg='', command_id=None):
>>>>>>> Stashed changes
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

def get_ip_addr():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("google.com",80))
    ip_addr = s.getsockname()[0]
    s.close()
    return ip_addr

def hash_string(s):
  return hashlib.sha224(s).hexdigest()
