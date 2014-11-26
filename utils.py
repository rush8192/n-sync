import json
import socket

def serialize_response(d):
  return json.dumps(d)

def get_ip_addr():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("google.com",80))
    ip_addr = s.getsockname()[0]
    s.close()
    return ip_addr