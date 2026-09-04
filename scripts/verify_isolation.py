#!/usr/bin/env python3
"""Root-run launch blocker. Uses real running services, never mocks or skips."""
import argparse
import json
import os
import pathlib
import subprocess
import sys
import time


def run(args):
    result = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if result.returncode:
        raise SystemExit('FAIL: ' + result.stdout.strip())
    return result.stdout.strip()


def require(condition, message):
    if not condition:
        raise SystemExit('FAIL: '+message)
    print('PASS: '+message)


def properties(unit):
    return dict(line.split('=',1) for line in run(['systemctl','show',unit]).splitlines() if '=' in line)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--origin-only',action='store_true')
    args=parser.parse_args()
    require(os.geteuid()==0, 'running as root')
    host_ns=os.readlink('/proc/1/ns/net')
    for unit in ('neurosis-api.service','neurosis-postgresql.service'):
        props=properties(unit)
        require(props['ActiveState']=='active',unit+' active')
        pid=int(props['MainPID'])
        require(pid>0 and os.readlink(f'/proc/{pid}/ns/net')!=host_ns, unit+' in private network namespace')
        require(props.get('PrivateNetwork')=='yes',unit+' PrivateNetwork=yes')
        require(props.get('RestrictAddressFamilies')=='AF_UNIX',unit+' AF_UNIX only')
        require('neurosis-network-probe.py' in props.get('ExecStartPre','') and 'status=0' in props['ExecStartPre'],unit+' sandbox socket-creation probe passed')
        listeners=run(['nsenter','-t',str(pid),'-n','ss','-H','-lnt'])
        require(not listeners,unit+' has zero TCP listeners')
        # nsenter does not inherit seccomp. This independently tests namespace isolation.
        code='''import socket
for host,port in [('1.1.1.1',443),('169.254.169.254',80),('127.0.0.1',22),('127.0.0.1',5432),('2606:4700:4700::1111',443)]:
 try:
  s=socket.create_connection((host,port),timeout=1)
 except OSError:
  continue
 s.close()
 raise SystemExit('Unexpected connection to '+host)
try:
 socket.getaddrinfo('example.com',443)
except OSError:
 pass
else:
 raise SystemExit('Public DNS unexpectedly resolves')
'''
        run(['nsenter','-t',str(pid),'-n','-m','/usr/bin/python3','-c',code])
        require(True,unit+' cannot reach Internet, metadata, host services or public DNS')
        # Mount sandbox must hide host resolver/Docker/systemd sockets.
        for target in ('/run/docker.sock','/run/systemd/private','/run/dbus/system_bus_socket','/etc/neurosis-tunnel/tunnel.json'):
            result=subprocess.run(['nsenter','-t',str(pid),'-m','test','-e',target],capture_output=True)
            require(result.returncode==1,unit+' cannot see '+target)
    for _ in range(20):
        result=subprocess.run(['runuser','-u','neurosis-tunnel','--','curl','--fail','--silent','--unix-socket','/run/neurosis-api/api.sock','http://localhost/healthz'],capture_output=True,text=True)
        if result.returncode==0:
            break
        time.sleep(1)
    require(result.returncode==0,'tunnel Unix user reaches healthy API socket')
    require(json.loads(result.stdout)['status']=='ok','API reaches PostgreSQL inside isolation')
    # Configuration catches unintended origin listeners even if firewall would mask them.
    host_listeners=run(['ss','-H','-lnt'])
    for line in host_listeners.splitlines():
        endpoint=line.split()[3]
        port=endpoint.rsplit(':',1)[-1]
        if port in ('5432','5433','8000','8080','80','443'):
            require(endpoint.startswith(('127.0.0.1:','[::1]:')), 'no public origin/database listener: '+endpoint)
    if not args.origin_only:
        props=properties('neurosis-cloudflared.service')
        require(props['ActiveState']=='active','cloudflared service active')
        require(os.readlink('/proc/'+props['MainPID']+'/ns/net')==host_ns,'cloudflared retains host egress namespace')
        # A healthy live tunnel and public GET prove end-to-end ingress. No memory writes.
        for attempt in range(30):
            result=subprocess.run(['curl','--fail','--silent','--max-time','5','https://neurosis.io/healthz'],capture_output=True,text=True)
            if result.returncode==0 and '"status":"ok"' in result.stdout:
                break
            time.sleep(1)
        require(result.returncode==0 and '"status":"ok"' in result.stdout,'public Cloudflare path reaches the isolated backend')
    print('Isolation checks passed. Also run the remote port check from another machine.')


if __name__=='__main__':
    main()
