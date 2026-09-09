#!/usr/bin/env python3
"""Read-only external acceptance check for the public research surface."""
import json
import urllib.request
import xml.etree.ElementTree as ET

BASE = 'https://neurosis.io'
AGENT = 'NEUROSIS-Operator-Acceptance/1.0'


def read(path, agent=AGENT):
    request = urllib.request.Request(BASE+path, headers={'User-Agent':agent})
    with urllib.request.urlopen(request,timeout=15) as response:
        assert response.status==200, (path,response.status)
        return response.read().decode(), response.headers


for path in ('/','/about','/research','/safety','/docs/api','/docs/concepts','/lab','/experiments','/experiments/exp-001'):
    body,headers=read(path)
    assert '<h1>' in body and '<link rel="canonical"' in body, path
    assert 'noindex' not in headers.get('X-Robots-Tag',''),path
    assert 'text/markdown' in headers.get('Link',''),path
    assert '<script' not in body.lower(),path
    assert 'href="/favicon.svg"' in body, path
    if path == '/':
        assert '<title>NEUROSIS — Persistent State and Agent Populations</title>' in body
        assert '<meta name="description" content="NEUROSIS is an open research project studying persistent state, information propagation, provenance, and emergent security behavior in autonomous agent populations.">' in body
    mirror='/index.md' if path=='/' else path+'.md'
    text,md_headers=read(mirror)
    assert text.startswith('# ') and 'text/markdown' in md_headers['Content-Type'],mirror
    assert 'canonical' in md_headers['Link'],mirror
    print('PASS trusted HTML and Markdown:',path)
body,headers=read('/favicon.svg')
assert 'image/svg+xml' in headers['Content-Type']
assert ET.fromstring(body).tag == '{http://www.w3.org/2000/svg}svg'
assert "img-src 'self'" in headers['Content-Security-Policy']
body,_=read('/robots.txt')
assert 'Allow: /' in body and BASE+'/sitemap.xml' in body
body,_=read('/sitemap.xml')
urls=[e.text for e in ET.fromstring(body).iter('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')]
assert len(urls)==9 and all('/engrams/' not in u for u in urls)
body,_=read('/llms.txt')
assert '/docs/api.md' in body and '/openapi.json' in body
body,_=read('/openapi.json')
assert len(json.loads(body)['paths'])==5
for path in ('/v1/recent','/v1/search?q=memory','/recent','/search?q=memory'):
    _,headers=read(path)
    assert 'noindex' in headers['X-Robots-Tag']
    assert 'no-store' in headers['Cache-Control']
for path in ('/security.txt','/.well-known/security.txt'):
    body,_=read(path)
    assert 'Contact: ' in body and 'Expires: ' in body
for claim in ('OAI-SearchBot/1.0','Googlebot/2.1','bingbot/2.0'):
    read('/docs/api',claim+' '+AGENT)
print('PASS discovery files, API schema, memory noindex, and crawler-UA accessibility')
print('Crawler-UA probes are operator tests, not verified crawler identities.')
for path in ('/metrics', '/metrics.json'):
    body, headers = read(path)
    assert 'noindex' in headers['X-Robots-Tag']
    assert 'no-store' in headers['Cache-Control']
    assert '<script' not in body.lower()
    assert AGENT not in body
snapshot = json.loads(body)
assert snapshot['since_start']['recent_reads'] >= 2
assert 'counters reset on restart' in snapshot['scope']
assert set(snapshot['telemetry']) == {'queued', 'dropped_since_start'}
print('PASS public aggregate metrics and activity counters')
