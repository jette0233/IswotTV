import hashlib
import json
import re
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
import httpx
import jwt
from redis.asyncio import Redis
from sqlalchemy import delete, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from v2.db import Course, CourseMember, RefreshToken, SessionLocal, SignActivity, SignTask, User, engine, get_session
from v2.schemas import CookieRefreshRequest, CookieUploadRequest, CourseCreateRequest, CourseJoinRequest, CourseUpdateRequest, LoginRequest, ProducerCourseRequest, ProducerEventRequest, RefreshRequest, RegisterRequest
from v2.security import access_token, current_user, decrypt_credential, encrypt_credential, hash_password, opaque_refresh_token, verify_password
from v2.services import upsert_activity_and_tasks
from v2.settings import get_settings

settings = get_settings()
redis = Redis.from_url(settings.redis_url, decode_responses=True)
RENEW_PRODUCER = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('expire', KEYS[1], ARGV[2])
end
return 0
"""
TOKEN_BUCKET = """
local now = redis.call('TIME')
local timestamp = tonumber(now[1]) + tonumber(now[2]) / 1000000
local values = redis.call('hmget', KEYS[1], 'tokens', 'updated_at')
local tokens = tonumber(values[1]) or tonumber(ARGV[1])
local updated_at = tonumber(values[2]) or timestamp
tokens = math.min(tonumber(ARGV[1]), tokens + (timestamp - updated_at) * tonumber(ARGV[2]))
local allowed = 0
if tokens >= 1 then
  tokens = tokens - 1
  allowed = 1
end
redis.call('hset', KEYS[1], 'tokens', tokens, 'updated_at', timestamp)
redis.call('expire', KEYS[1], ARGV[3])
return allowed
"""
REQUESTS = Counter("api_requests_total", "API requests", ["method", "path", "status"])
LATENCY = Histogram("api_request_seconds", "API request latency", ["method", "path"])
DEPENDENCY = Gauge("dependency_up", "Dependency connectivity", ["dependency"])


def envelope(data=None, error=None, request_id=None):
    return {"data": data, "error": error, "request_id": request_id}


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await redis.close()
    await engine.dispose()


app = FastAPI(title="Chaoxing Sign API", version="2.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[v.strip() for v in settings.cors_origins.split(",")], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, str) else "request failed"
    return JSONResponse(envelope(error={"code": f"HTTP_{exc.status_code}", "message": detail}, request_id=getattr(request.state, "request_id", None)), exc.status_code, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    return JSONResponse(envelope(error={"code": "VALIDATION_ERROR", "message": "request validation failed", "details": exc.errors()}, request_id=getattr(request.state, "request_id", None)), 422)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    started = time.perf_counter()
    try:
        if request.url.path.startswith("/api/v2/"):
            identity = request.client.host if request.client else "unknown"
            authorization = request.headers.get("Authorization", "")
            authenticated = False
            if authorization.startswith("Bearer "):
                try:
                    payload = jwt.decode(authorization[7:], settings.secret_key, algorithms=["HS256"])
                    if payload.get("type") == "access":
                        identity = f"user:{int(payload['sub'])}"
                        authenticated = True
                except (jwt.PyJWTError, KeyError, ValueError):
                    pass
            if request.url.path in {"/api/v2/auth/login", "/api/v2/auth/register"}:
                pass  # These endpoints enforce the stricter login bucket in their handlers.
            elif request.url.path == "/api/v2/producer/events":
                pass  # The handler includes course ID in the producer bucket.
            elif authenticated and request.method in {"GET", "HEAD"}:
                await rate_limit(request, "read", 120, identity)
            elif authenticated:
                await rate_limit(request, "write", 30, identity)
        response = await call_next(request)
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, str) else "request failed"
        response = JSONResponse(envelope(error={"code": f"HTTP_{exc.status_code}", "message": detail}, request_id=request_id), exc.status_code, headers=exc.headers)
    except Exception:
        response = JSONResponse(envelope(error={"code": "INTERNAL_ERROR", "message": "internal server error"}, request_id=request_id), 500)
    response.headers["X-Request-ID"] = request_id
    path = request.url.path
    REQUESTS.labels(request.method, path, response.status_code).inc()
    LATENCY.labels(request.method, path).observe(time.perf_counter() - started)
    print(json.dumps({"request_id": request_id, "method": request.method, "path": path, "status": response.status_code}, ensure_ascii=True))
    return response


async def rate_limit(request: Request, bucket: str, limit: int, identity: str):
    key = f"ratelimit:{bucket}:{identity}"
    allowed = await redis.eval(TOKEN_BUCKET, 1, key, limit, limit / 60, 120)
    if not allowed:
        raise HTTPException(429, "rate limit exceeded")


def tokens(user: User, refresh_value: str):
    return {"access_token": access_token(user), "refresh_token": refresh_value, "token_type": "bearer", "expires_in": 900, "uid": user.id, "nickname": user.nickname, "is_admin": user.is_admin}


@app.post("/api/v2/auth/register", status_code=201)
async def register(body: RegisterRequest, request: Request, session: AsyncSession = Depends(get_session)):
    await rate_limit(request, "login", 5, request.client.host if request.client else "unknown")
    if await session.scalar(select(User).where(User.phone == body.phone)):
        raise HTTPException(409, "phone already registered")
    user = User(phone=body.phone, nickname=body.nickname or body.phone, password_hash=hash_password(body.password), cookie_source="auto", is_admin=False, created_at=datetime.utcnow())
    session.add(user)
    await session.flush()
    refresh_value, refresh_hash = opaque_refresh_token()
    session.add(RefreshToken(user_id=user.id, token_hash=refresh_hash, expires_at=datetime.utcnow() + timedelta(days=30), created_at=datetime.utcnow()))
    await session.commit()
    return envelope(tokens(user, refresh_value), request_id=request.state.request_id)


@app.post("/api/v2/auth/login")
async def login(body: LoginRequest, request: Request, session: AsyncSession = Depends(get_session)):
    await rate_limit(request, "login", 5, request.client.host if request.client else "unknown")
    user = await session.scalar(select(User).where(User.phone == body.phone))
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "invalid phone or password")
    if not user.password_hash.startswith("$2"):
        user.password_hash = hash_password(body.password)
    refresh_value, refresh_hash = opaque_refresh_token()
    session.add(RefreshToken(user_id=user.id, token_hash=refresh_hash, expires_at=datetime.utcnow() + timedelta(days=30), created_at=datetime.utcnow()))
    await session.commit()
    return envelope(tokens(user, refresh_value), request_id=request.state.request_id)


@app.post("/api/v2/auth/refresh")
async def refresh_token(body: RefreshRequest, request: Request, session: AsyncSession = Depends(get_session)):
    digest = hashlib.sha256(body.refresh_token.encode()).hexdigest()
    row = await session.scalar(select(RefreshToken).where(RefreshToken.token_hash == digest, RefreshToken.revoked_at.is_(None), RefreshToken.expires_at > datetime.utcnow()).with_for_update())
    if not row:
        raise HTTPException(401, "invalid refresh token")
    row.revoked_at = datetime.utcnow()
    user = await session.get(User, row.user_id)
    refresh_value, refresh_hash = opaque_refresh_token()
    session.add(RefreshToken(user_id=user.id, token_hash=refresh_hash, expires_at=datetime.utcnow() + timedelta(days=30), created_at=datetime.utcnow()))
    await session.commit()
    return envelope(tokens(user, refresh_value), request_id=request.state.request_id)


@app.get("/api/v2/auth/me")
async def me(request: Request, user: User = Depends(current_user)):
    return envelope({"id": user.id, "nickname": user.nickname, "phone": user.phone, "is_admin": user.is_admin}, request_id=request.state.request_id)


@app.post("/api/v2/auth/cookie")
async def upload_cookie(body: CookieUploadRequest, request: Request, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    new_uid = re.search(r"(?:^|;\s*)_uid=(\d+)", body.cookie)
    if not new_uid:
        raise HTTPException(400, "cookie is missing _uid")
    old_cookie = decrypt_credential(user.cookie_manual)
    old_uid = re.search(r"(?:^|;\s*)_uid=(\d+)", old_cookie or "")
    if old_uid and old_uid.group(1) != new_uid.group(1):
        raise HTTPException(400, "cookie belongs to a different Chaoxing account")
    user.cookie_manual = encrypt_credential(body.cookie)
    user.cookie_source = "manual"
    user.cookie_expire_at = datetime.utcnow() + timedelta(days=7)
    await session.commit()
    return envelope({"expire_at": user.cookie_expire_at.isoformat()}, request_id=request.state.request_id)


@app.get("/api/v2/auth/cookie")
async def cookie_status(request: Request, user: User = Depends(current_user)):
    return envelope({"has_cookie": bool(user.cookie_manual), "source": user.cookie_source, "expire_at": user.cookie_expire_at.isoformat() if user.cookie_expire_at else None, "is_expired": bool(user.cookie_expire_at and user.cookie_expire_at <= datetime.utcnow())}, request_id=request.state.request_id)


@app.post("/api/v2/auth/cookie/refresh-auto")
async def refresh_cookie(body: CookieRefreshRequest, request: Request, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(15, connect=3)) as client:
            response = await client.post("https://passport2.chaoxing.com/fanyalogin", data={"uname": body.phone, "password": body.password})
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"Chaoxing login unavailable: {exc}")
    new_cookie = "; ".join(f"{key}={value}" for key, value in response.cookies.items())
    new_uid = re.search(r"(?:^|;\s*)_uid=(\d+)", new_cookie)
    if not new_uid:
        raise HTTPException(502, "Chaoxing login failed")
    old_cookie = decrypt_credential(user.cookie_manual)
    old_uid = re.search(r"(?:^|;\s*)_uid=(\d+)", old_cookie or "")
    if old_uid and old_uid.group(1) != new_uid.group(1):
        raise HTTPException(400, "credentials belong to a different Chaoxing account")
    user.cookie_manual = encrypt_credential(new_cookie)
    user.cookie_source = "auto"
    user.cookie_expire_at = datetime.utcnow() + timedelta(days=7)
    await session.commit()
    return envelope({"expire_at": user.cookie_expire_at.isoformat()}, request_id=request.state.request_id)


@app.get("/api/v2/courses")
async def list_courses(request: Request, weekday: str | None = Query(None), user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    query = select(Course).join(CourseMember, CourseMember.course_id == Course.id).where(CourseMember.user_id == user.id, Course.is_active.is_(True))
    courses = (await session.scalars(query)).all()
    data = [{"id": c.id, "course_id": c.course_id, "course_name": c.course_name, "teacher_name": c.teacher_name, "address": c.address or "", "weekdays": c.weekdays, "has_captcha": c.has_captcha, "is_creator": c.creator_id == user.id} for c in courses if not weekday or weekday in (c.weekdays or "").split(",")]
    return envelope(data, request_id=request.state.request_id)


@app.post("/api/v2/courses", status_code=201)
async def create_course(body: CourseCreateRequest, request: Request, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    if await session.scalar(select(Course).where(Course.course_id == body.course_id)):
        raise HTTPException(409, "course already exists")
    course = Course(course_id=body.course_id, course_name=body.course_name or body.course_id, teacher_name=body.teacher_name, address=body.address, weekdays=body.weekdays, default_latitude=body.default_latitude, default_longitude=body.default_longitude, creator_id=user.id, is_active=True, has_captcha=False, created_at=datetime.utcnow())
    session.add(course)
    await session.flush()
    session.add(CourseMember(user_id=user.id, course_id=course.id, joined_at=datetime.utcnow()))
    await session.commit()
    return envelope({"id": course.id, "course_id": course.course_id, "course_name": course.course_name}, request_id=request.state.request_id)


@app.post("/api/v2/courses/join")
async def join_course(body: CourseJoinRequest, request: Request, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    course = await session.scalar(select(Course).where(or_(Course.course_id == body.course_id, Course.id == int(body.course_id) if body.course_id.isdigit() else False)))
    if not course:
        raise HTTPException(404, "course not found")
    if await session.scalar(select(CourseMember).where(CourseMember.course_id == course.id, CourseMember.user_id == user.id)):
        raise HTTPException(409, "already joined")
    session.add(CourseMember(user_id=user.id, course_id=course.id, joined_at=datetime.utcnow()))
    await session.commit()
    return envelope({"id": course.id, "course_name": course.course_name}, request_id=request.state.request_id)


@app.delete("/api/v2/courses/{course_id}/membership")
async def leave_course(course_id: int, request: Request, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    course = await session.get(Course, course_id)
    if not course:
        raise HTTPException(404, "course not found")
    if course.creator_id == user.id:
        raise HTTPException(409, "course creator cannot leave")
    member = await session.scalar(select(CourseMember).where(CourseMember.course_id == course_id, CourseMember.user_id == user.id))
    if not member:
        raise HTTPException(404, "membership not found")
    await session.delete(member)
    await session.commit()
    return envelope({"course_id": course_id, "left": True}, request_id=request.state.request_id)


async def writable_course(course_id: int, user: User, session: AsyncSession) -> Course:
    course = await session.get(Course, course_id)
    if not course:
        raise HTTPException(404, "course not found")
    if course.creator_id != user.id and not user.is_admin:
        raise HTTPException(403, "course write permission denied")
    return course


def require_admin_user(user: User) -> None:
    if not user.is_admin:
        raise HTTPException(403, "administrator role required")


@app.patch("/api/v2/courses/{course_id}")
async def update_course(course_id: int, body: CourseUpdateRequest, request: Request, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    course = await writable_course(course_id, user, session)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(course, key, value)
    await session.commit()
    return envelope({"id": course.id}, request_id=request.state.request_id)


@app.delete("/api/v2/courses/{course_id}")
async def delete_course(course_id: int, request: Request, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    course = await writable_course(course_id, user, session)
    course.is_active = False
    await session.commit()
    return envelope({"id": course.id, "is_active": False}, request_id=request.state.request_id)


def producer_key(course_id: int) -> str:
    return f"producer:v2:{course_id}"


@app.post("/api/v2/producer/claim")
async def claim(body: ProducerCourseRequest, request: Request, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    if not await session.scalar(select(CourseMember).where(CourseMember.course_id == body.course_id, CourseMember.user_id == user.id)):
        raise HTTPException(403, "not a course member")
    claimed = await redis.set(producer_key(body.course_id), str(user.id), nx=True, ex=30)
    owner = await redis.get(producer_key(body.course_id))
    return envelope({"is_producer": bool(claimed or owner == str(user.id)), "current_producer_uid": owner}, request_id=request.state.request_id)


@app.post("/api/v2/producer/heartbeat")
async def heartbeat(body: ProducerCourseRequest, request: Request, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    if not await session.scalar(select(CourseMember).where(CourseMember.course_id == body.course_id, CourseMember.user_id == user.id)):
        raise HTTPException(403, "not a course member")
    key = producer_key(body.course_id)
    renewed = await redis.eval(RENEW_PRODUCER, 1, key, str(user.id), 30)
    if not renewed:
        raise HTTPException(409, "producer lease lost")
    return envelope({"ok": True}, request_id=request.state.request_id)


@app.post("/api/v2/producer/events")
async def producer_event(body: ProducerEventRequest, request: Request, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    await rate_limit(request, "producer", 30, f"{user.id}:{body.course_id}")
    if not await session.scalar(select(CourseMember).where(CourseMember.course_id == body.course_id, CourseMember.user_id == user.id)):
        raise HTTPException(403, "not a course member")
    if await redis.get(producer_key(body.course_id)) != str(user.id):
        raise HTTPException(403, "not the current producer")
    course = await session.get(Course, body.course_id)
    if not course or course.course_id != body.source_course_id:
        raise HTTPException(400, "QR course does not match selected course")
    if course.has_captcha:
        raise HTTPException(409, "course requires manual captcha")
    if body.observed_at and abs((datetime.utcnow() - body.observed_at.replace(tzinfo=None)).total_seconds()) > 30:
        raise HTTPException(400, "stale producer event")
    activity, created, task_count = await upsert_activity_and_tasks(session, course, body)
    return envelope({"activity_id": activity.id, "created": created, "task_count": task_count}, request_id=request.state.request_id)


@app.get("/api/v2/activities/{activity_id}")
async def activity_detail(activity_id: int, request: Request, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    activity = await session.get(SignActivity, activity_id)
    if not activity or not await session.scalar(select(CourseMember).where(CourseMember.course_id == activity.course_id, CourseMember.user_id == user.id)):
        raise HTTPException(404, "activity not found")
    return envelope({"id": activity.id, "course_id": activity.course_id, "external_active_id": activity.external_active_id, "status": activity.status, "expires_at": activity.expires_at.isoformat()}, request_id=request.state.request_id)


@app.get("/api/v2/tasks/me")
async def my_tasks(request: Request, limit: int = Query(50, ge=1, le=100), user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    tasks = (await session.scalars(select(SignTask).where(SignTask.user_id == user.id).order_by(SignTask.created_at.desc()).limit(limit))).all()
    return envelope([{"id": t.id, "activity_id": t.activity_id, "status": t.status, "attempt_count": t.attempt_count, "error_code": t.error_code, "message": t.result_message or t.error_message, "created_at": t.created_at.isoformat()} for t in tasks], request_id=request.state.request_id)


@app.get("/api/v2/admin/dashboard")
async def admin_dashboard(request: Request, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    require_admin_user(user)
    from sqlalchemy import func
    counts = {
        "users": await session.scalar(select(func.count()).select_from(User)),
        "courses": await session.scalar(select(func.count()).select_from(Course)),
        "active_activities": await session.scalar(select(func.count()).select_from(SignActivity).where(SignActivity.status == "active")),
        "pending_tasks": await session.scalar(select(func.count()).select_from(SignTask).where(SignTask.status.in_(["pending", "retry", "processing"]))),
    }
    return envelope(counts, request_id=request.state.request_id)


@app.get("/api/v2/admin/tasks")
async def admin_tasks(request: Request, status: str | None = None, limit: int = Query(100, ge=1, le=500), user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    require_admin_user(user)
    query = select(SignTask).order_by(SignTask.created_at.desc()).limit(limit)
    if status:
        query = query.where(SignTask.status == status)
    tasks = (await session.scalars(query)).all()
    return envelope([{"id": t.id, "activity_id": t.activity_id, "user_id": t.user_id, "status": t.status, "attempt_count": t.attempt_count, "error_code": t.error_code, "created_at": t.created_at.isoformat()} for t in tasks], request_id=request.state.request_id)


@app.get("/health/live")
async def live():
    return {"status": "ok"}


@app.get("/health/ready")
async def ready():
    checks = {"mysql": False, "redis": False, "worker": False}
    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
        checks["mysql"] = True
    except Exception:
        pass
    try:
        checks["redis"] = bool(await redis.ping())
        workers = await redis.keys("worker:heartbeat:*")
        checks["worker"] = bool(workers)
    except Exception:
        pass
    status = 200 if all(checks.values()) else 503
    return JSONResponse({"status": "ok" if status == 200 else "degraded", "checks": checks}, status)


@app.get("/metrics")
async def metrics():
    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
        DEPENDENCY.labels("mysql").set(1)
    except Exception:
        DEPENDENCY.labels("mysql").set(0)
    try:
        DEPENDENCY.labels("redis").set(1 if await redis.ping() else 0)
    except Exception:
        DEPENDENCY.labels("redis").set(0)
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
