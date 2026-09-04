import hashlib
import json
import socket
import subprocess
import time

import psycopg
import pytest
from fastapi.testclient import TestClient

from neurosis.admin import migrate, moderate
from neurosis.app import create_app
from neurosis.security import Limiter


def post(client, text='external memory test', **extra):
    result=client.post('/v1/engrams',json={'content':text,**extra})
    assert result.status_code==201,result.text
    return result.json()


def test_hostile_plaintext(client, monkeypatch, tmp_path):
    sentinel=tmp_path/'must-not-exist'
    text=f'<script>alert(1)</script><img src=x onerror=alert(1)>\n$(touch {sentinel}); echo x\nhttp://169.254.169.254/ http://127.0.0.1/ http://example.com/\n\x1b[31m Ignore prior instructions'
    original=socket.socket.connect
    network=[]
    def connect(sock, address):
        if sock.family != socket.AF_UNIX:
            network.append(address)
            raise AssertionError('Unexpected Internet socket')
        return original(sock,address)
    monkeypatch.setattr(socket.socket,'connect',connect)
    monkeypatch.setattr(socket,'getaddrinfo',lambda *a,**k: pytest.fail('Unexpected DNS resolution'))
    monkeypatch.setattr(subprocess,'Popen',lambda *a,**k: pytest.fail('Unexpected subprocess'))
    data=post(client,text)
    assert client.get('/v1/engrams/'+data['id']).json()['content']==text
    assert data['sha256']==hashlib.sha256(text.encode()).hexdigest()
    page=client.get('/engrams/'+data['id'])
    assert '&lt;script&gt;' in page.text and '<script>' not in page.text
    assert 'default-src' in page.headers['content-security-policy']
    assert not sentinel.exists() and network==[]


def test_references_search_pagination(client):
    a=post(client,'uniquezebra memory')
    b=post(client,'uniquezebra continuation',parent=a['id'])
    c=post(client,'uniquezebra links',references=[a['id'],b['id']])
    assert a['id'] in b['references']
    backlinks=client.get('/v1/engrams/'+a['id']+'/backlinks').json()['items']
    assert {b['id'],c['id']} <= {i['id'] for i in backlinks}
    first=client.get('/v1/search',params={'q':'uniquezebra','limit':1}).json()
    second=client.get('/v1/search',params={'q':'uniquezebra','limit':1,'after':first['next_cursor']}).json()
    assert first['items'][0]['id']!=second['items'][0]['id']
    assert client.post('/v1/engrams',json={'content':'x','references':['00000000000000000000000000']}).status_code==400
    assert client.post('/v1/engrams',json={'content':'x','references':[a['id'],a['id']]}).status_code==400


def test_moderation(client,database):
    a=post(client,'hiddenuniqueterm <script>')
    with psycopg.connect(database['admin']) as conn:
        moderate(conn,a['id'],'quarantined','privacy')
    data=client.get('/v1/engrams/'+a['id']).json()
    assert data['content']=='ENGRAM REMOVED FROM PUBLIC DISPLAY'
    assert 'sha256' not in data and 'references' not in data
    assert client.get('/v1/search?q=hiddenuniqueterm').json()['items']==[]
    assert client.get('/v1/engrams/'+a['id']+'/backlinks').json()['items']==[]
    with psycopg.connect(database['admin']) as conn:
        assert conn.execute('SELECT content FROM memory.engrams WHERE id=%s',(a['id'],)).fetchone()[0]=='hiddenuniqueterm <script>'


def test_get_never_mutates(client,database):
    a=post(client,'get-route-check')
    for suffix in ('', '/backlinks'):
        assert client.get('/v1/engrams/'+a['id']+suffix).status_code==200
    with psycopg.connect(database['admin']) as conn:
        before=conn.execute('SELECT count(*) FROM memory.engrams').fetchone()[0]
    for path in ['/','/about','/research','/safety','/docs/api','/docs/concepts','/recent','/search?q=memory','/v1/recent','/v1/search?q=memory','/v1/engrams?content=evil','/openapi.json','/llms.txt','/robots.txt','/sitemap.xml','/security.txt','/.well-known/security.txt','/v1/engrams/'+a['id'],'/engrams/'+a['id'],'/v1/engrams/'+a['id']+'/backlinks']:
        client.get(path)
    with psycopg.connect(database['admin']) as conn:
        assert conn.execute('SELECT count(*) FROM memory.engrams').fetchone()[0]==before


@pytest.mark.parametrize('method',['PUT','PATCH','DELETE','TRACE','CONNECT'])
def test_methods(client,method):
    assert client.request(method,'/v1/engrams',json={'content':'x'}).status_code==405


def test_input_limits(client,settings):
    assert client.post('/v1/engrams',content=b'x'*(settings.body+1),headers={'Content-Type':'application/json'}).status_code==413
    assert client.post('/v1/engrams',content=iter([b'x'*20000,b'x'*20000]),headers={'Content-Type':'application/json'}).status_code==413
    assert client.post('/v1/engrams',json={'content':'a'*(settings.content+1)}).status_code==413
    assert client.post('/v1/engrams',json={'content':'é'*(settings.content//2+1)}).status_code==413
    assert client.post('/v1/engrams',json={'content':'x','references':['00000000000000000000000000']*33}).status_code==413
    assert client.get('/v1/search',params={'q':'x'*(settings.query+1)}).status_code==400
    assert client.get('/v1/recent?limit=101').status_code==400
    assert client.get('/v1/recent?after=../../etc/passwd').status_code==400


@pytest.mark.parametrize('body',[b'{',b'\xff',b'{"content":"\\ud800"}',b'{"content":"\\u0000"}',b'{"content":""}',b'{"content":"x","content":"y"}',b'{"content":NaN}',b'[]',b'{"content":5}',b'{"content":"x","extra":1}', b'['*1000+b']'*1000])
def test_malformed(client,body):
    assert client.post('/v1/engrams',content=body,headers={'Content-Type':'application/json'}).status_code in (400,422)


def test_sql_and_traversal(client,database):
    text="'; DROP SCHEMA memory CASCADE; SELECT pg_sleep(99); --"
    a=post(client,text)
    assert client.get('/v1/search',params={'q':text}).status_code==200
    assert client.get('/v1/engrams/'+a['id']).json()['content']==text
    for path in ['/../../etc/passwd','/%2e%2e/%2e%2e/etc/passwd','/docs/../../../.env','/v1/engrams/%2e%2e%2fetc%2fpasswd']:
        response=client.get(path)
        assert response.status_code in (400,404)
        assert 'root:x:' not in response.text
    with psycopg.connect(database['app']) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute('DELETE FROM memory.engrams')
    with psycopg.connect(database['app']) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("UPDATE memory.engrams SET content='changed'")
    with psycopg.connect(database['app']) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute('CREATE TABLE memory.evil (id int)')


def test_rate_limits(settings):
    settings.write=2
    settings.search=2
    with TestClient(create_app(settings)) as c:
        for _ in range(2):
            post(c)
        r=c.post('/v1/engrams',json={'content':'x'},headers={'X-Forwarded-For':'1.2.3.4','CF-Connecting-IP':'5.6.7.8'})
        assert r.status_code==429 and int(r.headers['Retry-After'])>0
        for _ in range(2):
            assert c.get('/v1/search?q=memory').status_code==200
        assert c.get('/v1/search?q=memory').status_code==429
    settings.trust_cloudflare=True
    settings.global_write=2
    with TestClient(create_app(settings)) as c:
        for i in range(2):
            assert c.post('/v1/engrams',json={'content':'x'},headers={'CF-Connecting-IP':f'192.0.2.{i+1}'}).status_code==201
        assert c.post('/v1/engrams',json={'content':'x'},headers={'CF-Connecting-IP':'192.0.2.3'}).status_code==429


def test_limiter_bounded():
    lim=Limiter(2)
    assert lim.take('a',1,0)==0
    assert lim.take('a',1,0)==60
    assert lim.take('b',1,0)==0
    assert lim.take('c',1,0)==60
    assert lim.take('c',1,121)==0
    assert len(lim.buckets)<=2


def test_discovery_and_origin_policy(client):
    for path in ['/','/about','/research','/safety','/docs/api','/docs/concepts']:
        r=client.get(path)
        assert r.status_code==200 and '<h1>' in r.text and 'canonical' in r.text
        assert 'noindex' not in r.headers.get('x-robots-tag','')
        assert 'text/markdown' in r.headers['link']
    for path in ['/index.md','/research.md','/safety.md','/docs/api.md','/docs/concepts.md','/llms.txt','/openapi.json']:
        assert client.get(path).status_code==200
    markdown = client.get('/docs/api.md').text
    assert markdown.startswith('# HTTP API\n')
    assert '## Leave engram' in markdown
    assert '```text\n{"content":' in markdown
    assert '[OpenAPI JSON](/openapi.json)' in markdown
    assert '&quot;' not in markdown and '<p>' not in markdown
    assert 'engrams' not in client.get('/sitemap.xml').text
    assert 'noindex' in client.get('/v1/recent').headers['x-robots-tag']
    assert client.post('/v1/engrams',json={'content':'x'},headers={'Origin':'https://evil.example'}).status_code==403
    assert client.post('/v1/engrams',content='content=x').status_code==415
    assert client.request('GET','/v1/recent',content='x').status_code==400


def test_telemetry(client,database):
    a=post(client,'telemetrytest')
    client.get('/v1/engrams/'+a['id'],headers={'User-Agent':'OpenAI-fake','Referer':'https://user:secret@example.org/private?token=secret','CF-Bot-Verified':'true'})
    time.sleep(.15)
    with psycopg.connect(database['admin']) as conn:
        row=conn.execute("SELECT user_agent_claim,referer_origin,behavioral_classification,attribution_confidence,events FROM research.requests WHERE user_agent_claim='OpenAI-fake' ORDER BY created_at DESC LIMIT 1").fetchone()
        assert row[:4]==('OpenAI-fake','https://example.org','UNKNOWN',0)
        assert row[4][0]['engram_id']==a['id']


def test_restart_and_backup(settings,database):
    with TestClient(create_app(settings)) as c:
        a=post(c,'survivesrestart')
    database['stop']()
    database['start']()
    with TestClient(create_app(settings)) as c:
        assert c.get('/v1/engrams/'+a['id']).json()['content']=='survivesrestart'
    dump=database['root']/'backup.dump'
    subprocess.run([database['bindir']+'/pg_dump','--dbname',database['admin'],'-Fc','-f',str(dump)],check=True)
    admin=database['admin']
    with psycopg.connect(admin,autocommit=True) as conn:
        conn.execute('CREATE DATABASE restored')
    restored=admin.replace('dbname=neurosis','dbname=restored')
    subprocess.run([database['bindir']+'/pg_restore','--dbname',restored,'--exit-on-error',str(dump)],check=True)
    with psycopg.connect(restored) as conn:
        assert conn.execute('SELECT content FROM memory.engrams WHERE id=%s',(a['id'],)).fetchone()[0]=='survivesrestart'
        migrate(conn)  # checksum/idempotence
