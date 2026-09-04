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


for path in ('/','/about','/research','/safety','/docs/api','/docs/concepts'):
    body,headers=read(path)
    assert '<h1>' in body and '<link rel="canonical"' in body, path
    assert 'noindex' not in headers.get('X-Robots-Tag',''),path
    assert 'text/markdown' in headers.get('Link',''),path
    assert '<script' not in body.lower(),path
    mirror='/index.md' if path=='/' else path+'.md'
    text,md_headers=read(mirror)
    assert text.startswith('# ') and 'text/markdown' in md_headers['Content-Type'],mirror
    assert 'canonical' in md_headers['Link'],mirror
    print('PASS trusted HTML and Markdown:',path)
body,_=read('/robots.txt')
assert 'Allow: /' in body and BASE+'/sitemap.xml' in body
body,_=read('/sitemap.xml')
urls=[e.text for e in ET.fromstring(body).iter('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')]
assert len(urls)==6 and all('/engrams/' not in u for u in urls)
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
