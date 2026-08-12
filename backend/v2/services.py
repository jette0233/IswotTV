from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from v2.db import Course, CourseMember, OutboxEvent, SignActivity, SignTask
from v2.schemas import ProducerEventRequest
from v2.settings import get_settings


async def upsert_activity_and_tasks(session: AsyncSession, course: Course, event: ProducerEventRequest) -> tuple[SignActivity, bool, int]:
    now = datetime.utcnow()
    existing_id = await session.scalar(select(SignActivity.id).where(SignActivity.course_id == course.id, SignActivity.external_active_id == event.external_active_id))
    created = existing_id is None
    insert = mysql_insert(SignActivity).values(
        course_id=course.id, external_active_id=event.external_active_id, current_enc=event.enc,
        latitude=event.latitude, longitude=event.longitude, status="active",
        expires_at=now + timedelta(seconds=get_settings().mq_ttl_seconds), created_at=now, updated_at=now,
    )
    await session.execute(insert.on_duplicate_key_update(current_enc=event.enc, latitude=event.latitude, longitude=event.longitude, updated_at=now))
    activity = await session.scalar(select(SignActivity).where(SignActivity.course_id == course.id, SignActivity.external_active_id == event.external_active_id).with_for_update())

    created_tasks = 0
    if created:
        member_ids = (await session.scalars(select(CourseMember.user_id).where(CourseMember.course_id == course.id))).all()
        for user_id in member_ids:
            statement = mysql_insert(SignTask).values(activity_id=activity.id, user_id=user_id, status="pending", attempt_count=0, created_at=now, updated_at=now)
            result = await session.execute(statement.prefix_with("IGNORE"))
            if result.rowcount:
                created_tasks += 1
                session.add(OutboxEvent(event_type="sign_task.created", aggregate_id=str(activity.id), payload={"activity_id": activity.id, "user_id": user_id}, available_at=now, attempts=0, created_at=now))
    await session.commit()
    await session.refresh(activity)
    return activity, created, created_tasks


def classify_sign_result(text: str) -> tuple[str, str, bool]:
    normalized = text.strip()
    lower = normalized.lower()
    if "success" in lower or "已签到" in normalized or "签到过了" in normalized:
        return "success", "SIGNED", False
    if "validate" in lower or "滑块" in normalized:
        return "manual_required", "CAPTCHA_REQUIRED", False
    if "请登录" in normalized or "login" in lower:
        return "manual_required", "COOKIE_EXPIRED", False
    if "活动不存在" in normalized or "已结束" in normalized:
        return "expired", "ACTIVITY_EXPIRED", False
    return "retry", "UPSTREAM_FAILURE", True


RETRY_DELAYS = (5, 15, 45, 120)


def retry_delay(attempt_count: int) -> int | None:
    return RETRY_DELAYS[attempt_count - 1] if 1 <= attempt_count <= len(RETRY_DELAYS) else None
