#!/usr/bin/env python3
"""External origin-port check, with an optional reachable SSH control."""
import argparse
import errno
import ipaddress
import socket

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('hosts',nargs='+')
parser.add_argument('--control-port',type=int)
args=parser.parse_args()
for host in args.hosts:
    ipaddress.ip_address(host)
    if args.control_port:
        with socket.create_connection((host,args.control_port),timeout=5):
            print('PASS origin reachable on SSH control port')
    for port in (80,443,5355,5432,5433,8000,8080,20241):
        try:
            s=socket.create_connection((host,port),timeout=2)
        except OSError as error:
            if error.errno in (errno.ENETUNREACH,errno.EAFNOSUPPORT):
                raise SystemExit('INCONCLUSIVE: runner cannot route to origin address family')
            print(f'PASS origin port {port} unreachable')
            continue
        s.close()
        raise SystemExit(f'FAIL origin port {port} is reachable')
