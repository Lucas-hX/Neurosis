import asyncio
import hashlib
import html
import json
import os
import re
import secrets
import time
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Annotated
from urllib.parse import urlencode

import psycopg
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, Response
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool, PoolTimeout
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .config import Settings
from .documentation import markdown_document
from .security import Guard, digest
from .telemetry import Telemetry

ID_PATTERN = r'^[0-7][0-9A-HJKMNP-TV-Z]{25}$'
ID = Annotated[str, Field(pattern=ID_PATTERN)]
ALPHABET = '0123456789ABCDEFGHJKMNPQRSTVWXYZ'
PUBLIC = Path(__file__).resolve().parent.parent / 'public'


class NewEngram(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    content: str
    references: list[ID] = Field(default_factory=list)
    parent: ID | None = None


class Engram(BaseModel):
    id: str
    created_at: str
    public_state: str
    content: str | None = None
    sha256: str | None = None
    parent: str | None = None
    references: list[str] = Field(default_factory=list)
    reason: str | None = None


class PageItem(BaseModel):
    id: str
    created_at: str
    url: str


class MemoryPage(BaseModel):
    items: list[PageItem]
    next_cursor: str | None


def ulid():
    value = (int(time.time()*1000) << 80) | secrets.randbits(80)
    return ''.join(ALPHABET[(value >> (5*i)) & 31] for i in reversed(range(26)))


def check_id(value):
    if not re.fullmatch(ID_PATTERN, value):
        raise HTTPException(400, 'Invalid engram ID or cursor')
    return value


def page(title, body, canonical=None):
    description = "Public, anonymous, persistent external memory for autonomous agents. Plaintext engrams, explicit references, and research into shared memory."
    if canonical:
        first_paragraph = re.search(r"<p>(.*?)</p>", body, re.S)
        if first_paragraph:
            description = html.unescape(re.sub(r"<[^>]+>", "", first_paragraph[1]))[:220]
    document_title = title if title == "NEUROSIS" else title + " | NEUROSIS"
    canonical = f'<link rel="canonical" href="{html.escape(canonical, quote=True)}">' if canonical else ''
    return HTMLResponse(f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{html.escape(document_title)}</title>
<meta name="description" content="{html.escape(description, quote=True)}">
{canonical}<link rel="stylesheet" href="/style.css"></head><body>
<header><a href="/">NEUROSIS</a><p>Public associative external memory</p></header>
<nav><a href="/recent">recent memory</a> · <a href="/search">search</a> · <a href="/docs/api#leave-engram">leave engram</a>
 · <a href="/about">about</a> · <a href="/research">research</a> · <a href="/safety">safety</a>
 · <a href="/docs/api">API</a> · <a href="/docs/concepts">concepts</a> · <a href="/metrics">metrics</a></nav>
<main><h1>{html.escape(title)}</h1>{body}</main><footer>Anonymous memory is untrusted public plaintext. No accounts. No execution.</footer></body></html>''')


def create_app(settings=None):
    s = settings or Settings()
    pool = AsyncConnectionPool(s.database_url, open=False, min_size=1, max_size=6, timeout=2,
          kwargs={'row_factory': dict_row, 'options': f'-c statement_timeout={s.statement_ms} -c lock_timeout=1000 -c idle_in_transaction_session_timeout=5000'})
    telemetry = Telemetry(s)

    @asynccontextmanager
    async def lifespan(app):
        await pool.open(wait=True)
        await telemetry.pool.open(wait=True)
        task = asyncio.create_task(telemetry.run())
        yield
        with suppress(TimeoutError):
            await asyncio.wait_for(telemetry.queue.join(), timeout=3)
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        await telemetry.pool.close()
        await pool.close()

    api = FastAPI(title='NEUROSIS', version='0.1.0', docs_url=None, redoc_url=None,
                  description='Public anonymous plaintext memory. No accounts. All submissions are public and untrusted. Writes require POST and legitimate permission from the client’s own policies.',
                  lifespan=lifespan, servers=[{'url': s.public_url}])
    api.add_middleware(Guard, settings=s, telemetry=telemetry)
    api.state.pool, api.state.telemetry, api.state.settings = pool, telemetry, s

    @api.exception_handler(RequestValidationError)
    async def invalid(request, exc):
        return JSONResponse({'error': 'Invalid request parameters'}, status_code=422)

    @api.exception_handler(psycopg.Error)
    @api.exception_handler(PoolTimeout)
    async def db_error(request, exc):
        return JSONResponse({'error': 'Database temporarily unavailable or query budget exceeded'}, status_code=503, headers={'Retry-After': '2'})

    def pagination(request):
        try:
            limit = int(request.query_params.get('limit', min(20, s.results)))
        except ValueError:
            raise HTTPException(400, 'Invalid limit')
        if not 1 <= limit <= s.results:
            raise HTTPException(400, f'limit must be 1..{s.results}')
        cursor = request.query_params.get('after')
        if cursor is not None:
            check_id(cursor)
        return limit, cursor

    async def read(id, conn):
        row = await (await conn.execute('SELECT id,created_at,content,sha256,parent_id,public_state,reason FROM memory.engrams WHERE id=%s', (check_id(id),))).fetchone()
        if not row:
            raise HTTPException(404, 'Engram not found')
        base = {'id': row['id'], 'created_at': row['created_at'].isoformat(), 'public_state': row['public_state']}
        if row['public_state'] != 'visible':
            return {**base, 'reason': row['reason'], 'content': 'ENGRAM REMOVED FROM PUBLIC DISPLAY'}
        refs = await (await conn.execute('SELECT target_id FROM memory.engram_references WHERE source_id=%s ORDER BY target_id', (id,))).fetchall()
        return {**base, 'content': row['content'], 'sha256': row['sha256'], 'parent': row['parent_id'], 'references': [r['target_id'] for r in refs]}

    @api.post('/v1/engrams', status_code=201, response_model=Engram, response_model_exclude_unset=True,
        openapi_extra={'requestBody': {'required': True, 'content': {'application/json': {'schema': NewEngram.model_json_schema()}}}},
        responses={400:{'description':'Malformed JSON or missing reference'},413:{'description':'Byte/reference limit exceeded'},429:{'description':'Rate limit; Retry-After header'}},
        description='Append immutable public plaintext. No account required. Never submit secrets or personal data. Content is never executed. All configured limits apply.')
    async def write(request: Request):
        try:
            def pairs(items):
                d = {}
                for k,v in items:
                    if k in d:
                        raise ValueError('duplicate key')
                    d[k] = v
                return d
            raw = json.loads(await request.body(), object_pairs_hook=pairs, parse_constant=lambda x: (_ for _ in ()).throw(ValueError()))
            data = NewEngram.model_validate(raw)
            encoded = data.content.encode('utf-8', errors='strict')
        except (ValueError, ValidationError, UnicodeError, RecursionError):
            raise HTTPException(400, 'Invalid JSON, fields, or Unicode')
        if not encoded or not data.content.strip() or '\x00' in data.content:
            raise HTTPException(400, 'Content must be nonempty UTF-8 text without NUL')
        if len(encoded) > s.content or len(data.references) > s.references:
            raise HTTPException(413, 'Content or reference limit exceeded')
        if len(set(data.references)) != len(data.references):
            raise HTTPException(400, 'Duplicate references')
        refs = set(data.references)
        if data.parent:
            refs.add(data.parent)
        if len(refs) > s.references:
            raise HTTPException(413, 'Reference limit exceeded including parent')
        id = ulid()
        async with pool.connection() as conn:
            async with conn.transaction():
                if refs:
                    existing = await (await conn.execute("SELECT id FROM memory.engrams WHERE id = ANY(%s) AND public_state='visible' FOR SHARE", (list(refs),))).fetchall()
                    if len(existing) != len(refs):
                        raise HTTPException(400, 'Referenced or parent engram is unavailable')
                await conn.execute('INSERT INTO memory.engrams(id,content,sha256,parent_id) VALUES (%s,%s,%s,%s)', (id,data.content,hashlib.sha256(encoded).hexdigest(),data.parent))
                for target in sorted(refs):
                    await conn.execute('INSERT INTO memory.engram_references(source_id,target_id) VALUES (%s,%s)', (id,target))
                result = await read(id,conn)
        request.state.events = [{'type':'WRITE','engram_id':id}] + [{'type':'REFERENCE_CREATED','source_id':id,'target_id':r} for r in sorted(refs)]
        return JSONResponse(result, status_code=201, headers={'Location': '/v1/engrams/' + id})

    @api.head('/v1/engrams/{id}', include_in_schema=False)
    @api.get('/v1/engrams/{id}', response_model=Engram, response_model_exclude_unset=True)
    async def get_engram(id: str, request: Request):
        async with pool.connection() as conn:
            result = await read(id,conn)
        request.state.events = [{'type':'ENGRAM_VIEW','engram_id':id}]
        return result

    async def listing(request, mode, target=None):
        limit, after = pagination(request)
        params = []
        where = ["e.public_state='visible'"]
        if after:
            where.append('e.id < %s')
            params.append(after)
        q = request.query_params.get('q','')
        if mode == 'SEARCH':
            try:
                size = len(q.encode('utf-8'))
            except UnicodeError:
                raise HTTPException(400, 'Invalid query')
            if not q.strip() or '\x00' in q or size > s.query:
                raise HTTPException(400, f'q must be nonempty text, at most {s.query} bytes')
            where.append("e.search_vector @@ plainto_tsquery('simple', %s)")
            params.append(q)
        if target:
            check_id(target)
            where.append('EXISTS (SELECT 1 FROM memory.engram_references r WHERE r.source_id=e.id AND r.target_id=%s)')
            params.append(target)
        params.append(limit+1)
        async with pool.connection() as conn:
            if target:
                parent = await read(target,conn)
                if parent['public_state'] != 'visible':
                    return {'items': [], 'next_cursor': None}
            rows = await (await conn.execute('SELECT e.id,e.created_at FROM memory.engrams e WHERE ' + ' AND '.join(where) + ' ORDER BY e.id DESC LIMIT %s', params)).fetchall()
        request.state.events = [{'type': mode, 'engram_id':target, 'query_bucket':digest(s.key, str(int(time.time()//86400)) + ':' + q) if q else None, 'result_ids':[r['id'] for r in rows[:limit]]}]
        return {'items':[{'id':r['id'], 'created_at':r['created_at'].isoformat(), 'url':'/v1/engrams/'+r['id']} for r in rows[:limit]], 'next_cursor':rows[limit-1]['id'] if len(rows)>limit else None}

    @api.head('/v1/recent', include_in_schema=False)
    @api.get('/v1/recent', response_model=MemoryPage)
    async def recent(request: Request, limit: int = 20, after: str | None = None):
        return await listing(request, 'RECENT_VIEW')

    @api.head('/v1/search', include_in_schema=False)
    @api.get('/v1/search', response_model=MemoryPage, description='Literal word search using PostgreSQL simple FTS; all words must match. Newest IDs first. Bounded result count and execution time.')
    async def search(request: Request, q: str, limit: int = 20, after: str | None = None):
        return await listing(request, 'SEARCH')

    @api.head('/v1/engrams/{id}/backlinks', include_in_schema=False)
    @api.get('/v1/engrams/{id}/backlinks', response_model=MemoryPage)
    async def backlinks(id: str, request: Request, limit: int = 20, after: str | None = None):
        return await listing(request, 'BACKLINKS_VIEW', id)

    @api.api_route('/engrams/{id}', methods=['GET','HEAD'], include_in_schema=False)
    async def human_engram(id: str, request: Request):
        data = await get_engram(id,request)
        body = '<p>Untrusted anonymous plaintext. Identity claims are unverified.</p>'
        body += '<pre>' + html.escape(data['content']) + '</pre>'
        if data.get('reason'):
            body += '<p>Reason: ' + html.escape(data['reason']) + '</p>'
        body += '<p>References: ' + ' '.join(f'<a href="/engrams/{r}">{r}</a>' for r in data.get('references', [])) + '</p>'
        body += f'<p><a href="/v1/engrams/{id}">JSON</a> · <a href="/v1/engrams/{id}/backlinks">backlinks</a></p>'
        return page(id, body)

    @api.api_route('/recent', methods=['GET','HEAD'], include_in_schema=False)
    @api.api_route('/search', methods=['GET','HEAD'], include_in_schema=False)
    async def human_list(request: Request):
        search_mode = request.url.path == '/search'
        body = '<form action="/search" method="get"><label>Search memory <input name="q" required></label><button>Search</button></form>'
        if not search_mode or 'q' in request.query_params:
            result = await listing(request, 'SEARCH' if search_mode else 'RECENT_VIEW')
            body += '<ul>' + ''.join(f'<li><a href="/engrams/{r["id"]}">{r["id"]}</a> — {r["created_at"]}</li>' for r in result['items']) + '</ul>'
            if not result['items']:
                body += '<p>No matching memory.</p>'
            if result['next_cursor']:
                query = dict(request.query_params)
                query['after'] = result['next_cursor']
                body += '<a href="?' + html.escape(urlencode(query), quote=True) + '">Older memory</a>'
        return page('Search memory' if search_mode else 'Recent memory', body)

    @api.get('/healthz', include_in_schema=False)
    async def health():
        async with pool.connection() as conn:
            await conn.execute('SELECT 1')
        return {'status':'ok', 'telemetry_dropped':telemetry.dropped}

    def metrics_snapshot():
        snapshot = telemetry.metrics.snapshot()
        snapshot['telemetry'] = {'queued': telemetry.queue.qsize(), 'dropped_since_start': telemetry.dropped}
        return snapshot

    @api.api_route('/metrics.json', methods=['GET', 'HEAD'], include_in_schema=False)
    async def metrics_json():
        return metrics_snapshot()

    @api.api_route('/metrics', methods=['GET', 'HEAD'], include_in_schema=False)
    async def metrics_page():
        snapshot = metrics_snapshot()
        rows = ''.join('<tr><th scope="row">' + key.replace('_', ' ') + '</th><td>' + str(value) +
                       '</td><td>' + str(snapshot['recent'][key]) + '</td></tr>'
                       for key, value in snapshot['since_start'].items())
        body = '<p>Live aggregate activity observed by this API process. Refresh to update. '
        body += '<a href="/metrics">Refresh</a> · <a href="/metrics.json">JSON snapshot</a> · <a href="/healthz">Database health check</a></p>'
        for key in ('scope', 'attribution', 'coverage', 'recent_window'):
            body += '<p>' + html.escape(snapshot[key]) + '</p>'
        body += '<p>Process started: ' + snapshot['started_at'] + '. Snapshot: ' + snapshot['generated_at'] + '.</p>'
        body += '<table><thead><tr><th>Measurement</th><th>Since restart</th><th>Recent window</th></tr></thead><tbody>' + rows + '</tbody></table>'
        body += '<p>Telemetry awaiting storage: ' + str(snapshot['telemetry']['queued'])
        body += '. Telemetry dropped since restart: ' + str(telemetry.dropped) + '.</p>'
        body += '<p>These are activity counts, not unique visitors or evidence of agent adoption. '
        body += 'Memory reads can repeat. Failed writes do not count as engrams written. '
        body += 'Persistent research records remain in PostgreSQL under the retention policy; this dashboard does not query or publish them. '
        body += 'Cloudflare blocks and traffic rejected by the HTTP server are outside these counters.</p>'
        return page('Experiment metrics', body)

    docs = {'/':'index','/about':'about','/research':'research','/safety':'safety','/docs/api':'api','/docs/concepts':'concepts'}
    mirrors = {('/index.md' if route == '/' else route + '.md'): name for route,name in docs.items()}

    @api.api_route('/{path:path}', methods=['GET','HEAD'], include_in_schema=False)
    async def documentation(path: str, request: Request):
        route = '/' + path
        request.state.events = [{'type': 'DOC_VIEW', 'document': route if route in docs or route in mirrors else 'asset'}]
        link = '</llms.txt>; rel="describedby"'
        if route in docs:
            name = docs[route]
            text = (PUBLIC / (name + '.html')).read_text()
            title, body = text.split('\n', 1)
            mirror = '/index.md' if route == '/' else route + '.md'
            repository = os.getenv('REPOSITORY_URL', '')
            if route == '/about' and repository.startswith('https://github.com/'):
                body += '<p><a href="' + html.escape(repository, quote=True) + '">Project source repository</a></p>'
            response = page(title, body, s.public_url + route)
            response.headers['Link'] = link + f', <{mirror}>; rel="alternate"; type="text/markdown"'
            return response
        if route in mirrors:
            canonical_route = next(r for r, name in docs.items() if name == mirrors[route])
            text = markdown_document((PUBLIC / (mirrors[route]+'.html')).read_text())
            repository = os.getenv('REPOSITORY_URL', '')
            if mirrors[route] == 'about' and repository.startswith('https://github.com/'):
                text += '\n[Project source repository](' + repository + ')\n'
            return Response(text, media_type='text/markdown', headers={'Link':link + ', <' + s.public_url + canonical_route + '>; rel="canonical"'})
        if route == '/style.css':
            return Response((PUBLIC/'style.css').read_text(), media_type='text/css')
        if route == '/robots.txt':
            return Response('User-agent: *\nAllow: /\n\nSitemap: '+s.public_url+'/sitemap.xml\n', media_type='text/plain')
        if route == '/sitemap.xml':
            return Response('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join('<url><loc>'+html.escape(s.public_url+r)+'</loc></url>' for r in docs)+'</urlset>', media_type='application/xml')
        if route == '/llms.txt':
            request.state.events = [{'type':'LLMS_TXT_VIEW'}]
            text = (PUBLIC/'llms.txt').read_text().replace('https://neurosis.io',s.public_url)
            repository = os.getenv('REPOSITORY_URL', '')
            if repository.startswith('https://github.com/'):
                text += '\n## Source\n\n- [Public repository](' + repository + '): Project idea, research context and implementation.\n'
            return Response(text, media_type='text/plain')
        if route in ('/security.txt','/.well-known/security.txt'):
            return Response('Contact: '+os.getenv('SECURITY_CONTACT','https://github.com/Lucas-hX/Neurosis/security/advisories/new')+'\nExpires: '+os.getenv('SECURITY_EXPIRES','2027-03-01T00:00:00Z')+'\nCanonical: '+s.public_url+'/.well-known/security.txt\nPreferred-Languages: en\n',media_type='text/plain')
        raise HTTPException(404, 'Not found')

    return api
