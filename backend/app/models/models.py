from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nickname = db.Column(db.String(64), nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=True)  # 方案1: 加密存密码
    cookie_manual = db.Column(db.Text, nullable=True)  # 方案2: 手动抓的Cookie
    cookie_expire_at = db.Column(db.DateTime, nullable=True)
    cookie_source = db.Column(db.String(10), default="auto")  # "auto" / "manual"
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    courses = db.relationship("CourseMember", back_populates="user")
    refresh_tokens = db.relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")


class Course(db.Model):
    __tablename__ = "courses"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    course_id = db.Column(db.String(64), unique=True, nullable=False)
    course_name = db.Column(db.String(128), nullable=True)
    address = db.Column(db.String(256), nullable=True)
    default_latitude = db.Column(db.String(20), nullable=True)
    default_longitude = db.Column(db.String(20), nullable=True)
    weekdays = db.Column(db.String(10), default="1,2,3,4,5")
    teacher_name = db.Column(db.String(64), nullable=True)
    creator_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    has_captcha = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    members = db.relationship("CourseMember", back_populates="course", cascade="all, delete-orphan")
    creator = db.relationship("User")


class CourseMember(db.Model):
    __tablename__ = "course_members"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    joined_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship("User", back_populates="courses")
    course = db.relationship("Course", back_populates="members")

    __table_args__ = (db.UniqueConstraint("user_id", "course_id", name="uk_user_course"),)


class SignLog(db.Model):
    __tablename__ = "sign_logs"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    active_id = db.Column(db.String(64), nullable=True)
    enc = db.Column(db.String(128), nullable=True)
    status = db.Column(db.String(20), default="pending")  # success / fail / expired / pending
    message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship("User")
    course = db.relationship("Course")


class RefreshToken(db.Model):
    __tablename__ = "refresh_tokens"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = db.Column(db.String(64), unique=True, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    revoked_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    user = db.relationship("User", back_populates="refresh_tokens")


class SignActivity(db.Model):
    __tablename__ = "sign_activities"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    external_active_id = db.Column(db.String(64), nullable=False)
    current_enc = db.Column(db.String(128), nullable=False)
    latitude = db.Column(db.String(20), nullable=True)
    longitude = db.Column(db.String(20), nullable=True)
    status = db.Column(db.String(24), nullable=False, default="active", index=True)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    course = db.relationship("Course")
    tasks = db.relationship("SignTask", back_populates="activity", cascade="all, delete-orphan")
    __table_args__ = (db.UniqueConstraint("course_id", "external_active_id", name="uk_activity_course_external"),)


class SignTask(db.Model):
    __tablename__ = "sign_tasks"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    activity_id = db.Column(db.Integer, db.ForeignKey("sign_activities.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status = db.Column(db.String(24), nullable=False, default="pending", index=True)
    attempt_count = db.Column(db.Integer, nullable=False, default=0)
    lease_owner = db.Column(db.String(128), nullable=True)
    lease_expires_at = db.Column(db.DateTime, nullable=True, index=True)
    next_attempt_at = db.Column(db.DateTime, nullable=True, index=True)
    error_code = db.Column(db.String(64), nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    result_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)

    activity = db.relationship("SignActivity", back_populates="tasks")
    user = db.relationship("User")
    __table_args__ = (db.UniqueConstraint("activity_id", "user_id", name="uk_task_activity_user"),)


class OutboxEvent(db.Model):
    __tablename__ = "outbox_events"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    event_type = db.Column(db.String(64), nullable=False, index=True)
    aggregate_id = db.Column(db.String(64), nullable=False)
    payload = db.Column(db.JSON, nullable=False)
    available_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    published_at = db.Column(db.DateTime, nullable=True, index=True)
    attempts = db.Column(db.Integer, nullable=False, default=0)
    last_error = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
