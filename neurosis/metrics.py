"""Bounded, identifier-free process metrics; durable research stays in PostgreSQL."""
import time
from collections import Counter, deque
from datetime import datetime, timezone


EVENTS = {'DOC_VIEW': 'documentation_reads', 'OPENAPI_VIEW': 'api_schema_reads',
          'LLMS_TXT_VIEW': 'llms_txt_reads', 'ENGRAM_VIEW': 'engram_reads',
          'WRITE': 'engrams_written', 'REFERENCE_CREATED': 'references_created',
          'SEARCH': 'searches', 'RECENT_VIEW': 'recent_reads', 'BACKLINKS_VIEW': 'backlink_reads'}
KEYS = ('requests', 'client_errors', 'server_errors', 'rate_limited',
        'latency_ms_total', 'request_bytes', 'response_bytes', *EVENTS.values())
OBSERVATION_PATHS = ('/metrics', '/metrics.json', '/healthz')


class Metrics:
    def __init__(self):
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.started = time.monotonic()
        self.total = Counter()
        self.minutes = deque(maxlen=60)

    def observe(self, event):
        minute = int(time.monotonic() // 60)
        if not self.minutes or self.minutes[-1][0] != minute:
            self.minutes.append((minute, Counter()))
        counts = Counter(requests=1, request_bytes=event['request_bytes'],
                         response_bytes=event['response_bytes'], latency_ms_total=event['latency_ms'])
        status = event['status']
        counts['client_errors'] = int(400 <= status < 500)
        counts['server_errors'] = int(status >= 500)
        counts['rate_limited'] = int(status == 429)
        if 200 <= status < 300:
            for item in event['events']:
                key = EVENTS.get(item['type'])
                if key and not (item['type'] == 'DOC_VIEW' and item.get('document') == 'asset'):
                    counts[key] += 1
        self.total.update(counts)
        self.minutes[-1][1].update(counts)

    def snapshot(self):
        minute = int(time.monotonic() // 60)
        recent = Counter()
        for when, counts in self.minutes:
            if minute - 4 <= when <= minute:
                recent.update(counts)
        return {
            'scope': 'This API process only; counters reset on restart.',
            'attribution': 'Includes operator tests, humans and crawlers; does not identify autonomous agents.',
            'coverage': 'Excludes metrics/health probes and requests blocked before the application middleware.',
            'started_at': self.started_at,
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'uptime_seconds': int(time.monotonic() - self.started),
            'recent_window': 'Current minute and four preceding minute buckets (at most five minutes).',
            'since_start': {key: self.total[key] for key in KEYS},
            'recent': {key: recent[key] for key in KEYS},
        }
