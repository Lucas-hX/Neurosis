"""Local administration. Never imported by the HTTP application."""
import argparse
import hashlib
import os
from pathlib import Path

import psycopg


def migrate(conn):
    with conn.transaction():
        conn.execute('SELECT pg_advisory_xact_lock(817423)')
        conn.execute('CREATE TABLE IF NOT EXISTS public.schema_migrations (name text PRIMARY KEY, sha256 text NOT NULL)')
        for path in sorted(Path(__file__).resolve().parent.parent.joinpath('migrations').glob('*.sql')):
            sql = path.read_text()
            digest = hashlib.sha256(sql.encode()).hexdigest()
            existing = conn.execute('SELECT sha256 FROM public.schema_migrations WHERE name=%s', (path.name,)).fetchone()
            if existing:
                if existing[0] != digest:
                    raise RuntimeError(f'Migration checksum changed: {path.name}')
                continue
            conn.execute(sql)
            conn.execute('INSERT INTO public.schema_migrations VALUES (%s,%s)', (path.name, digest))


def moderate(conn, id, state, reason):
    with conn.transaction():
        row = conn.execute('UPDATE memory.engrams SET public_state=%s, reason=%s WHERE id=%s RETURNING id', (state, reason, id)).fetchone()
        if not row:
            raise ValueError('Unknown engram')
        conn.execute('INSERT INTO memory.moderation_events(engram_id,action,reason) VALUES (%s,%s,%s)', (id,state,reason))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('migrate')
    mod = sub.add_parser('moderate')
    mod.add_argument('id')
    mod.add_argument('state', choices=['visible','quarantined','tombstoned'])
    mod.add_argument('reason', choices=['privacy','spam','safety','legal','other'])
    prune = sub.add_parser('prune')
    prune.add_argument('--days', type=int, default=int(os.getenv('TELEMETRY_RETENTION_DAYS', '14')))
    args = parser.parse_args()
    with psycopg.connect(os.environ['DATABASE_URL']) as conn:
        if args.command == 'migrate':
            migrate(conn)
        elif args.command == 'moderate':
            moderate(conn, args.id, args.state, args.reason)
        else:
            if args.days < 1:
                parser.error('days must be positive')
            # Batches bound each transaction and avoid a long deletion lock.
            while True:
                n = conn.execute("DELETE FROM research.requests WHERE request_id IN (SELECT request_id FROM research.requests WHERE created_at < now() - %s * interval '1 day' LIMIT 5000)", (args.days,)).rowcount
                conn.commit()
                if n < 5000:
                    break


if __name__ == '__main__':
    main()
