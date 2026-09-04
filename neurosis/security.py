import asyncio
import hashlib
import hmac
import ipaddress
import json
import math
import time
import uuid
from collections import OrderedDict
from datetime import datetime, timezone
from urllib.parse import urlsplit

from starlette.responses import JSONResponse
from .metrics import OBSERVATION_PATHS


class Limiter:
    """Bounded token buckets. One API worker only; no eviction bypass."""
    def __init__(self, capacity):
        self.capacity = capacity
        self.buckets = OrderedDict()

    def take(self, key, rate, now=None):
        now = time.monotonic() if now is None else now
        while self.buckets and next(iter(self.buckets.values()))[1] < now - 120:
            self.buckets.popitem(last=False)
        old = self.buckets.pop(key, None)
        if old is None and len(self.buckets) >= self.capacity:
            return 60
        tokens, last = old or (float(rate), now)
        tokens = min(rate, tokens + (now-last)*rate/60)
        wait = max(0, math.ceil((1-tokens)*60/rate))
        self.buckets[key] = (tokens if wait else tokens-1, now)
        return wait


def clean(value, limit=512):
    # Metadata is hostile too. No terminal control bytes in stored claims.
    return ''.join(c for c in value[:limit] if c.isprintable())


def digest(key, value):
    return hmac.new(key.encode(), value.encode(), hashlib.sha256).hexdigest()


class Guard:
    def __init__(self, app, settings, telemetry):
        self.app, self.s, self.telemetry = app, settings, telemetry
        self.local = Limiter(settings.sources)
        self.global_limits = Limiter(10)

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        started = time.monotonic()
        request_id = str(uuid.uuid4())
        headers = {k.decode('latin1'): v.decode('latin1') for k,v in scope['headers']}
        path, method = scope['path'], scope['method']
        state = scope.setdefault('state', {})
        state['events'] = [{'type': 'OPENAPI_VIEW'}] if scope['path'] == '/openapi.json' else []
        state['request_id'] = request_id
        source = scope.get('client') or ('unknown', 0)
        source = source[0]
        if self.s.trust_cloudflare:
            source = headers.get('cf-connecting-ip', 'unknown')
        try:
            address = ipaddress.ip_address(source)
            # IPv6 /64 prevents cheap address rotation within one client subnet.
            source = str(ipaddress.ip_network(f'{address}/64', strict=False)) if address.version == 6 else str(address)
        except ValueError:
            source = 'unknown'
        bucket = digest(self.s.key, 'rate:' + source)
        day = datetime.now(timezone.utc).date().isoformat()
        cluster = digest(self.s.key, 'research:' + day + ':' + source)
        kind = 'docs'
        if method == 'POST':
            kind = 'write'
        elif path in ('/v1/search', '/search'):
            kind = 'search'
        elif path in ('/v1/recent', '/recent'):
            kind = 'recent'
        elif path.startswith(('/v1/', '/engrams/')):
            kind = 'read'
        total, status, response_bytes = 0, 500, 0

        async def wrapped_send(message):
            nonlocal status, response_bytes
            if message['type'] == 'http.response.start':
                status = message['status']
                hs = list(message.get('headers', []))
                hs += [(b'x-request-id', request_id.encode()),
                       (b'x-content-type-options', b'nosniff'),
                       (b'referrer-policy', b'no-referrer'),
                       (b'permissions-policy', b'camera=(), microphone=(), geolocation=()'),
                       (b'content-security-policy', b"default-src 'none'; img-src 'self'; style-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")]
                if path.startswith(('/v1/', '/engrams/')) or path in ('/recent', '/search', *OBSERVATION_PATHS):
                    hs += [(b'x-robots-tag', b'noindex, follow'), (b'cache-control', b'no-store, no-transform')]
                else:
                    hs += [(b'cache-control', b'no-cache, no-transform')]
                message['headers'] = hs
            elif message['type'] == 'http.response.body':
                response_bytes += 0 if method == 'HEAD' else len(message.get('body', b''))
            await send(message)

        async def reject(code, detail, retry=None):
            hs = {'Retry-After': str(retry)} if retry else {}
            if code == 405:
                hs['Allow'] = 'POST' if path == '/v1/engrams' else 'GET, HEAD'
            await JSONResponse({'error': detail}, status_code=code, headers=hs)(scope, receive, wrapped_send)

        try:
            if method not in ('GET','HEAD','POST','OPTIONS'):
                return await reject(405, 'Method not allowed')
            wait = self.global_limits.take('requests', self.s.global_requests)
            if not wait and kind in ('write','search'):
                wait = self.global_limits.take(kind, getattr(self.s, 'global_' + kind))
            if not wait:
                wait = self.local.take((bucket, kind), getattr(self.s, kind))
            if wait:
                return await reject(429, 'Rate limit exceeded', wait)
            if len(scope.get('query_string', b'')) > self.s.query * 4 + 1024:
                return await reject(414, 'Query string too long')
            if len(path) > 2048 or sum(len(k)+len(v) for k,v in scope['headers']) > 16384:
                return await reject(431, 'Headers or path too large')
            if headers.get('content-encoding', 'identity') != 'identity':
                return await reject(415, 'Encoded bodies are not supported')
            try:
                length = int(headers.get('content-length', '0'))
                if length < 0:
                    raise ValueError()
            except ValueError:
                return await reject(400, 'Invalid Content-Length')
            if length > self.s.body:
                return await reject(413, 'Request body too large')
            if method == 'POST':
                if headers.get('content-type', '').split(';')[0].strip().lower() != 'application/json':
                    return await reject(415, 'Use application/json')
                if headers.get('origin') not in (None, self.s.public_url):
                    return await reject(403, 'Cross-origin writes are disabled')
            body = bytearray()
            async with asyncio.timeout(self.s.timeout):
                while True:
                    message = await receive()
                    if message['type'] == 'http.disconnect':
                        return
                    chunk = message.get('body', b'')
                    total += len(chunk)
                    if total > self.s.body:
                        return await reject(413, 'Request body too large')
                    body.extend(chunk)
                    if not message.get('more_body'):
                        break
            if method in ('GET', 'HEAD', 'OPTIONS') and body:
                return await reject(400, 'This method does not accept a body')
            if method == 'POST':
                try:
                    body.decode('utf-8', errors='strict')
                except UnicodeError:
                    return await reject(400, 'Body must be UTF-8')
            sent = False
            async def buffered_receive():
                nonlocal sent
                if not sent:
                    sent = True
                    return {'type': 'http.request', 'body': bytes(body), 'more_body': False}
                return await receive()
            await self.app(scope, buffered_receive, wrapped_send)
        except TimeoutError:
            await reject(408, 'Request body timeout')
        finally:
            try:
                ref = urlsplit(headers.get('referer', ''))
                # Deliberately omit credentials, paths and queries (may contain secrets).
                referer = f'{ref.scheme}://{ref.hostname}' if ref.scheme in ('http','https') and ref.hostname else None
            except ValueError:
                referer = None
            route = getattr(scope.get('route'), 'path', 'UNMATCHED')
            # Do not retain arbitrary attack paths or search text.
            event = {
                'request_id': request_id, 'created_at': datetime.now(timezone.utc),
                'cluster': cluster, 'route': route, 'method': method[:16], 'status': status,
                'latency_ms': int((time.monotonic()-started)*1000),
                'request_bytes': total, 'response_bytes': response_bytes,
                'user_agent_claim': clean(headers.get('user-agent','')),
                'referer_origin': clean(referer or '', 256),
                'cf_ray': clean(headers.get('cf-ray',''),128) if self.s.trust_cloudflare else None,
                'country': clean(headers.get('cf-ipcountry',''),2) if self.s.trust_cloudflare else None,
                # ASN/bot headers are NOT standard authenticated origin headers.
                # Join Cloudflare exports offline by Ray ID; leave these unknown here.
                'events': state['events'],
            }
            if path not in OBSERVATION_PATHS:
                self.telemetry.enqueue(event)
