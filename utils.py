import json
import socket
import flask 
import pickle

def format_rpc_response(success, command, params, msg='', command_epoch=None):
  resp = {'success': success, 'command':command, 'params': params}
  if msg != '':
    resp['msg'] = msg
  if command_epoch != None:
    resp['command_epoch'] = command_epoch
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