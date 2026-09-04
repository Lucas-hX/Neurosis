import asyncio
import logging

from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool


class Telemetry:
    def __init__(self, settings):
        self.queue = asyncio.Queue(maxsize=settings.queue_size)
        self.dropped = 0
        self.pool = AsyncConnectionPool(settings.database_url, open=False, min_size=1, max_size=1,
                                        timeout=1, kwargs={'options': '-c statement_timeout=1000'})

    def enqueue(self, event):
        try:
            self.queue.put_nowait(event)
        except asyncio.QueueFull:
            self.dropped += 1
            if self.dropped == 1 or self.dropped % 100 == 0:
                logging.warning('telemetry_dropped=%d', self.dropped)

    async def run(self):
        while True:
            event = await self.queue.get()
            try:
                async with self.pool.connection() as conn:
                    await conn.execute('''INSERT INTO research.requests
                      (request_id,created_at,cluster,route,method,status,latency_ms,request_bytes,
                       response_bytes,user_agent_claim,referer_origin,cf_ray,country,events)
                      VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                      tuple(event[k] for k in ('request_id','created_at','cluster','route','method','status',
                            'latency_ms','request_bytes','response_bytes','user_agent_claim','referer_origin',
                            'cf_ray','country')) + (Jsonb(event['events']),))
            except Exception:
                self.dropped += 1
                logging.warning('telemetry_write_failed dropped=%d', self.dropped)
            finally:
                self.queue.task_done()
