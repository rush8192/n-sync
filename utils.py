import json
import socket
import flask 

def format_rpc_response(success, command, params, msg=''):
  resp = {'success': success, 'command': command, 'params': params}
  if msg == '':
    return resp
  resp['msg'] = msg
  return resp

def serialize_response(res):
  return flask.jsonify(**res)

def unserialize_response(res):
  return json.loads(res)

def get_ip_addr():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("google.com",80))
    ip_addr = s.getsockname()[0]
    s.close()
    return ip_addr