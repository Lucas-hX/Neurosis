import os
from dataclasses import dataclass, field


def number(name, default):
    value = int(os.getenv(name, str(default)))
    if value < 1:
        raise ValueError(f'{name} must be positive')
    return value


@dataclass
class Settings:
    database_url: str = field(default_factory=lambda: os.environ['DATABASE_URL'])
    public_url: str = field(default_factory=lambda: os.getenv('PUBLIC_URL', 'https://neurosis.io').rstrip('/'))
    key: str = field(default_factory=lambda: os.environ['TELEMETRY_KEY'])
    trust_cloudflare: bool = field(default_factory=lambda: os.getenv('TRUST_CLOUDFLARE', 'false') == 'true')
    body: int = field(default_factory=lambda: number('MAX_BODY_BYTES', 32768))
    content: int = field(default_factory=lambda: number('MAX_CONTENT_BYTES', 16384))
    references: int = field(default_factory=lambda: number('MAX_REFERENCES', 32))
    query: int = field(default_factory=lambda: number('MAX_QUERY_BYTES', 1024))
    results: int = field(default_factory=lambda: number('MAX_RESULTS', 100))
    write: int = field(default_factory=lambda: number('WRITE_PER_MINUTE', 10))
    global_write: int = field(default_factory=lambda: number('GLOBAL_WRITE_PER_MINUTE', 100))
    search: int = field(default_factory=lambda: number('SEARCH_PER_MINUTE', 30))
    global_search: int = field(default_factory=lambda: number('GLOBAL_SEARCH_PER_MINUTE', 300))
    read: int = field(default_factory=lambda: number('READ_PER_MINUTE', 300))
    recent: int = field(default_factory=lambda: number('RECENT_PER_MINUTE', 120))
    docs: int = field(default_factory=lambda: number('DOCS_PER_MINUTE', 600))
    global_requests: int = field(default_factory=lambda: number('GLOBAL_REQUEST_PER_MINUTE', 6000))
    sources: int = field(default_factory=lambda: number('LIMITER_MAX_SOURCES', 20000))
    timeout: int = field(default_factory=lambda: number('REQUEST_TIMEOUT_SECONDS', 10))
    statement_ms: int = field(default_factory=lambda: number('DB_STATEMENT_TIMEOUT_MS', 1500))
    queue_size: int = field(default_factory=lambda: number('TELEMETRY_QUEUE_SIZE', 2048))
    retention: int = field(default_factory=lambda: number('TELEMETRY_RETENTION_DAYS', 14))

    def __post_init__(self):
        if len(self.key) < 32 or self.key.startswith('REPLACE'):
            raise ValueError('Set a random TELEMETRY_KEY of at least 32 characters')
        if not self.public_url.startswith('https://'):
            raise ValueError('PUBLIC_URL must use HTTPS')
