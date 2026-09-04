"""Kernel-level check in a user network namespace; production gate remains separate."""
import socket
import subprocess
import sys


def test_private_network_still_reaches_unix_postgresql(database):
    with socket.socket() as host:
        host.bind(('127.0.0.1',0))
        host.listen()
        port=host.getsockname()[1]
        code='''import socket, sys
import psycopg
with psycopg.connect(sys.argv[1]) as conn:
 assert conn.execute('SELECT 1').fetchone()[0]==1
for address,port in [('127.0.0.1',int(sys.argv[2])),('1.1.1.1',443),('169.254.169.254',80),('2606:4700:4700::1111',443)]:
 try:
  sock=socket.create_connection((address,port),timeout=1)
 except OSError:
  continue
 sock.close()
 raise SystemExit('Unexpected network access: '+address)
'''
        result=subprocess.run(['unshare','-Urn',sys.executable,'-c',code,database['admin'],str(port)],capture_output=True,text=True)
        assert result.returncode==0,result.stderr
