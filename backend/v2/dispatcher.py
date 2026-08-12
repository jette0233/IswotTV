import asyncio
import json
import os
from datetime import datetime

from redis.asyncio import Redis
from sqlalchemy import select

from v2.db import OutboxEvent, SessionLocal
from v2.settings import get_settings
from prometheus_client import Gauge, start_http_server
from sqlalchemy import func
from v2.db import SignTask

STREAM = "sign:tasks"
QUEUE_DEPTH = Gauge("sign_queue_depth", "Signing stream length")
PENDING = Gauge("sign_queue_pending", "Pending signing messages")
OLDEST = Gauge("sign_oldest_pending_seconds", "Age of the oldest unfinished signing task")


class Dispatcher:
    def __init__(self):
        self.settings = get_settings()
        self.redis = Redis.from_url(self.settings.redis_url, decode_responses=True)
        self.name = os.getenv("DISPATCHER_NAME", "dispatcher-1")

    async def publish_batch(self) -> int:
        now = datetime.utcnow()
        async with SessionLocal() as session:
            async with session.begin():
                events = (await session.scalars(
                    select(OutboxEvent)
                    .where(OutboxEvent.published_at.is_(None), OutboxEvent.available_at <= now)
                    .order_by(OutboxEvent.id)
                    .limit(100)
                    .with_for_update(skip_locked=True)
                )).all()
                published = 0
                for event in events:
                    try:
                        values = {"event_id": str(event.id), "event_type": event.event_type, **{k: str(v) for k, v in event.payload.items()}}
                        await self.redis.xadd(STREAM, values, maxlen=10000, approximate=True)
                        event.published_at = now
                        event.attempts += 1
                        event.last_error = None
                        published += 1
                    except Exception as exc:
                        event.attempts += 1
                        event.last_error = str(exc)[:1000]
            return published

    async def heartbeat(self):
        await self.redis.set(f"dispatcher:heartbeat:{self.name}", datetime.utcnow().isoformat(), ex=20)
        QUEUE_DEPTH.set(await self.redis.xlen(STREAM))
        try:
            groups = await self.redis.xinfo_groups(STREAM)
            group = next((item for item in groups if item.get("name") == "sign-workers"), None)
            PENDING.set(group.get("pending", 0) if group else 0)
        except Exception:
            PENDING.set(0)
        async with SessionLocal() as session:
            oldest = await session.scalar(select(func.min(SignTask.created_at)).where(SignTask.status.in_(["pending", "retry", "processing"])))
            OLDEST.set(max(0, (datetime.utcnow() - oldest).total_seconds()) if oldest else 0)

    async def run(self):
        start_http_server(int(os.getenv("DISPATCHER_METRICS_PORT", "9103")))
        try:
            while True:
                await self.heartbeat()
                published = await self.publish_batch()
                await asyncio.sleep(0.2 if published else 1)
        finally:
            await self.redis.close()


if __name__ == "__main__":
    asyncio.run(Dispatcher().run())
