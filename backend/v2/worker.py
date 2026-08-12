import asyncio
import base64
import json
import os
import re
import socket
import uuid
from datetime import datetime, timedelta

import httpx
from prometheus_client import Counter, Histogram, start_http_server
from redis.asyncio import Redis
from sqlalchemy import and_, or_, select, update

from v2.db import Course, OutboxEvent, SessionLocal, SignActivity, SignTask, User
from v2.security import decrypt_credential
from v2.services import classify_sign_result, retry_delay
from v2.settings import get_settings

STREAM = "sign:tasks"
GROUP = "sign-workers"
DEAD_STREAM = "sign:dead"
RELEASE_LOCK = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('del', KEYS[1])
end
return 0
"""
RESULTS = Counter("sign_results_total", "Signing results", ["status", "error_code"])
UPSTREAM = Histogram("sign_upstream_seconds", "Chaoxing request duration")


class SignWorker:
    def __init__(self):
        self.settings = get_settings()
        self.redis = Redis.from_url(self.settings.redis_url, decode_responses=True)
        self.name = os.getenv("WORKER_NAME", f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:6]}")
        self.semaphore = asyncio.Semaphore(self.settings.worker_concurrency)
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(10, connect=3), limits=httpx.Limits(max_connections=self.settings.worker_concurrency, max_keepalive_connections=10))

    async def ensure_group(self):
        try:
            await self.redis.xgroup_create(STREAM, GROUP, id="0", mkstream=True)
        except Exception as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def heartbeat(self):
        await self.redis.set(f"worker:heartbeat:{self.name}", datetime.utcnow().isoformat(), ex=20)

    async def claim_task(self, activity_id: int, user_id: int) -> tuple[int | None, bool]:
        now = datetime.utcnow()
        lease_until = now + timedelta(seconds=self.settings.worker_lease_seconds)
        async with SessionLocal() as session:
            task = await session.scalar(select(SignTask).where(SignTask.activity_id == activity_id, SignTask.user_id == user_id))
            if not task or task.status in {"success", "manual_required", "expired", "dead"}:
                return None, True
            result = await session.execute(
                update(SignTask)
                .where(
                    SignTask.id == task.id,
                    or_(SignTask.lease_expires_at.is_(None), SignTask.lease_expires_at < now, SignTask.lease_owner == self.name),
                    or_(SignTask.next_attempt_at.is_(None), SignTask.next_attempt_at <= now),
                )
                .values(status="processing", lease_owner=self.name, lease_expires_at=lease_until, attempt_count=SignTask.attempt_count + 1, updated_at=now)
            )
            await session.commit()
            return (task.id, False) if result.rowcount == 1 else (None, False)

    async def sign(self, user: User, activity: SignActivity, course: Course) -> str:
        cookie = decrypt_credential(user.cookie_manual)
        if not cookie or (user.cookie_expire_at and user.cookie_expire_at <= datetime.utcnow()):
            return "COOKIE_EXPIRED"
        uid_match = re.search(r"_uid=(\d+)", cookie)
        name_match = re.search(r'uname="([^"]*)"', cookie)
        fid_match = re.search(r"spaceFid=(\d+)", cookie)
        params = {
            "activeId": activity.external_active_id,
            "enc": activity.current_enc,
            "uid": uid_match.group(1) if uid_match else "",
            "name": name_match.group(1) if name_match else user.phone,
            "fid": fid_match.group(1) if fid_match else "0",
            "deviceCode": base64.b64encode(os.urandom(48)).decode(),
            "clientip": "", "latitude": "-1", "longitude": "-1", "appType": "15",
            "address": course.address or "",
        }
        lat = course.default_latitude or activity.latitude
        lng = course.default_longitude or activity.longitude
        if lat and lng and lat != "-1" and lng != "-1":
            params["location"] = json.dumps({"result": 1, "latitude": lat, "longitude": lng, "address": course.address or "", "mockData": '{"strategy":0,"probability":-1}'}, ensure_ascii=False)
        headers = {"User-Agent": "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 Mobile Safari/537.36", "Cookie": cookie, "Referer": "https://mobilelearn.chaoxing.com/"}
        with UPSTREAM.time():
            response = await self.client.get(self.settings.chaoxing_sign_url, params=params, headers=headers)
        return response.text.strip() if response.status_code == 200 else f"HTTP_{response.status_code}:{response.text[:100]}"

    async def complete(self, task_id: int, raw_result: str) -> bool:
        now = datetime.utcnow()
        status, error_code, retryable = classify_sign_result(raw_result)
        if raw_result == "COOKIE_EXPIRED":
            status, error_code, retryable = "manual_required", "COOKIE_EXPIRED", False
        async with SessionLocal() as session:
            task = await session.get(SignTask, task_id, with_for_update=True)
            if not task or task.lease_owner != self.name:
                return False
            task.lease_owner = None
            task.lease_expires_at = None
            task.updated_at = now
            if status == "success":
                task.status = "success"
                task.result_message = raw_result[:1000]
                task.completed_at = now
            elif status in {"manual_required", "expired"}:
                task.status = status
                task.error_code = error_code
                task.error_message = raw_result[:1000]
                task.completed_at = now
            else:
                delay = retry_delay(task.attempt_count)
                if retryable and delay is not None:
                    task.status = "retry"
                    task.error_code = error_code
                    task.error_message = raw_result[:1000]
                    task.next_attempt_at = now + timedelta(seconds=delay)
                    session.add(OutboxEvent(event_type="sign_task.retry", aggregate_id=str(task.id), payload={"activity_id": task.activity_id, "user_id": task.user_id}, available_at=task.next_attempt_at, attempts=0, created_at=now))
                else:
                    task.status = "dead"
                    task.error_code = error_code
                    task.error_message = raw_result[:1000]
                    task.completed_at = now
                    await self.redis.xadd(DEAD_STREAM, {"task_id": str(task.id), "activity_id": str(task.activity_id), "user_id": str(task.user_id), "error_code": error_code}, maxlen=10000, approximate=True)
            await session.commit()
        RESULTS.labels(status if status != "retry" else "retry", error_code).inc()
        return True

    async def process(self, message_id: str, fields: dict):
        async with self.semaphore:
            user_id = int(fields["user_id"])
            lock_key = f"sign:user-lock:{user_id}"
            lock_token = f"{self.name}:{message_id}:{uuid.uuid4().hex}"
            lock_ttl = max(self.settings.worker_lease_seconds, 15)
            locked = await self.redis.set(lock_key, lock_token, nx=True, ex=lock_ttl)
            if not locked:
                return
            try:
                activity_id = int(fields["activity_id"])
                task_id, safe_to_ack = await self.claim_task(activity_id, user_id)
                if not task_id:
                    if safe_to_ack:
                        await self.redis.xack(STREAM, GROUP, message_id)
                    return
                async with SessionLocal() as session:
                    activity = await session.get(SignActivity, activity_id)
                    user = await session.get(User, user_id)
                    course = await session.get(Course, activity.course_id) if activity else None
                if not activity or not user or not course or activity.expires_at <= datetime.utcnow():
                    result = "活动已结束"
                elif course.has_captcha:
                    result = "validate required"
                else:
                    try:
                        result = await self.sign(user, activity, course)
                    except (httpx.TimeoutException, httpx.NetworkError) as exc:
                        result = f"network error: {exc}"
                completed = await self.complete(task_id, result)
                if completed:
                    await self.redis.xack(STREAM, GROUP, message_id)
            finally:
                await self.redis.eval(RELEASE_LOCK, 1, lock_key, lock_token)

    async def reclaim(self):
        try:
            result = await self.redis.xautoclaim(STREAM, GROUP, self.name, min_idle_time=30000, start_id="0-0", count=50)
            messages = result[1] if len(result) > 1 else []
            await asyncio.gather(*(self.process(message_id, fields) for message_id, fields in messages))
        except Exception as exc:
            print(f"reclaim failed: {exc}")

    async def run(self):
        await self.ensure_group()
        metrics_port = int(os.getenv("WORKER_METRICS_PORT", "9101"))
        start_http_server(metrics_port)
        try:
            while True:
                await self.heartbeat()
                await self.reclaim()
                rows = await self.redis.xreadgroup(GROUP, self.name, {STREAM: ">"}, count=self.settings.worker_concurrency, block=2000)
                jobs = [self.process(mid, fields) for _, messages in rows for mid, fields in messages]
                if jobs:
                    await asyncio.gather(*jobs)
        finally:
            await self.client.aclose()
            await self.redis.close()


if __name__ == "__main__":
    asyncio.run(SignWorker().run())
