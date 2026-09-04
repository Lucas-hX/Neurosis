#!/usr/bin/env python3
"""ExecStartPre launch blocker: runs under the SAME systemd sandbox as daemon."""
import socket

for family in (socket.AF_INET, socket.AF_INET6, socket.AF_PACKET):
    for kind in (socket.SOCK_STREAM, socket.SOCK_DGRAM):
        try:
            sock = socket.socket(family, kind)
        except OSError:
            continue
        sock.close()
        raise SystemExit(f'FAIL: network socket creation permitted: {family}/{kind}')
with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM):
    pass
print('PASS: Internet/packet socket creation denied; Unix sockets available')
