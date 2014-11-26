#!/usr/local/bin/python

import sys
import os
import argparse

REPLICA_IP_FILE = 'replica_ips.cfg'

def upload_dir(args):
    dir_to_push = args.f
    replica_config = args.cfg
    assert(os.path.exists(dir_to_push))
    assert(os.path.isdir(dir_to_push))
    with open(replica_config) as ips:
        for line in ips.readlines():
            ip_addr = line.strip()
            command = 'rsync -r --exclude \".*/\" ' + dir_to_push + \
                      ' pi@' + ip_addr + ':~/cs244b/'
            print command
            os.system(command)            

# python remote_pi_control -f ../nsync
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Raspberry Pi Remote Control")
    parser.add_argument("-f", type=str, default=None)
    parser.add_argument("-cfg", type=str, default=REPLICA_IP_FILE)

    args = parser.parse_args()
    if args.f != None:
        upload_dir(args)