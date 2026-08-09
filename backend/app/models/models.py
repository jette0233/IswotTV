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

    members = db.relationship("CourseMember", back_populates="course")
    creator = db.relationship("User")


class CourseMember(db.Model):
    __tablename__ = "course_members"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    joined_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship("User", back_populates="courses")
    course = db.relationship("Course", back_populates="members")


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
