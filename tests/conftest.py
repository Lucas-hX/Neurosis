import os
import pathlib
import shutil
import subprocess
import tempfile

import psycopg
import pytest
from fastapi.testclient import TestClient

from neurosis.admin import migrate
from neurosis.app import create_app
from neurosis.config import Settings


@pytest.fixture(scope='session')
def database():
    bindir = subprocess.check_output(['pg_config','--bindir'],text=True).strip()
    root=pathlib.Path(tempfile.mkdtemp(prefix='neurosis-test-'))
    data, sock = root/'data', root/'socket'
    sock.mkdir()
    subprocess.run([bindir+'/initdb','-D',str(data),'-U','postgres','--auth=trust','--encoding=UTF8','--locale=C.UTF-8'],check=True,stdout=subprocess.DEVNULL)
    options=f"-k {sock} -p 55439 -c listen_addresses=''"
    def start():
        subprocess.run([bindir+'/pg_ctl','-D',str(data),'-l',str(root/'postgres.log'),'-o',options,'-w','start'],check=True,stdout=subprocess.DEVNULL)
    def stop():
        subprocess.run([bindir+'/pg_ctl','-D',str(data),'-m','fast','-w','stop'],check=True,stdout=subprocess.DEVNULL)
    start()
    admin=f'host={sock} port=55439 dbname=postgres user=postgres'
    with psycopg.connect(admin,autocommit=True) as conn:
        conn.execute('CREATE DATABASE neurosis')
        conn.execute('CREATE ROLE "neurosis-api" LOGIN')
    admin=admin.replace('dbname=postgres','dbname=neurosis')
    with psycopg.connect(admin) as conn:
        migrate(conn)
        conn.execute('REVOKE ALL ON DATABASE neurosis FROM PUBLIC')
        conn.execute('GRANT CONNECT ON DATABASE neurosis TO "neurosis-api"')
        conn.execute('GRANT USAGE ON SCHEMA memory,research TO "neurosis-api"')
        conn.execute('GRANT SELECT ON memory.engrams,memory.engram_references TO "neurosis-api"')
        conn.execute('GRANT INSERT(id,content,sha256,parent_id),UPDATE(id) ON memory.engrams TO "neurosis-api"')
        conn.execute('GRANT INSERT(source_id,target_id) ON memory.engram_references TO "neurosis-api"')
        conn.execute('GRANT INSERT ON research.requests TO "neurosis-api"')
    yield {'admin':admin,'app':admin.replace('user=postgres','user=neurosis-api'), 'start':start,'stop':stop,'bindir':bindir,'root':root}
    stop()
    shutil.rmtree(root)


@pytest.fixture
def settings(database):
    return Settings(database_url=database['app'],key='test-key-'*8,trust_cloudflare=False,
                    write=1000,search=1000,global_write=5000,global_search=5000,
                    global_requests=10000,read=5000,recent=5000,docs=5000)


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as client:
        yield client
