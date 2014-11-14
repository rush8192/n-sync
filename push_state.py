#!/usr/local/bin/python

import sys
import os

def main(argv):
    file_to_push = None
    if len(argv) > 1:
        file_to_push = argv[1]

    with open("cohort.cfg") as cohort_config:
        for line in cohort_config.readlines():
            ip_addr = line[:-1]
            if file_to_push == None:
                for filename in os.listdir("."):
                    if filename[0] == '.':
                        continue
                    command = "scp " + filename + " pi@" + ip_addr + ":~/cs244b/" + filename
                    os.system(command)
            else:
                command = "scp " + file_to_push + " pi@" + ip_addr + ":~/cs244b/" + file_to_push
                os.system(command)

sys.exit(main(sys.argv))