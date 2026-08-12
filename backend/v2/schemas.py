from datetime import datetime

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    phone: str = Field(min_length=3, max_length=20)
    password: str = Field(min_length=8, max_length=128)
    nickname: str | None = Field(default=None, max_length=64)


class LoginRequest(BaseModel):
    phone: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class CookieUploadRequest(BaseModel):
    cookie: str = Field(min_length=10, max_length=16384)


class CookieRefreshRequest(BaseModel):
    phone: str
    password: str


class CourseCreateRequest(BaseModel):
    course_id: str = Field(min_length=1, max_length=64)
    course_name: str | None = Field(default=None, max_length=128)
    teacher_name: str | None = Field(default=None, max_length=64)
    address: str | None = Field(default=None, max_length=256)
    weekdays: str = "1,2,3,4,5"
    default_latitude: str | None = None
    default_longitude: str | None = None


class CourseJoinRequest(BaseModel):
    course_id: str


class CourseUpdateRequest(BaseModel):
    course_name: str | None = Field(default=None, max_length=128)
    teacher_name: str | None = Field(default=None, max_length=64)
    address: str | None = Field(default=None, max_length=256)
    weekdays: str | None = None
    default_latitude: str | None = None
    default_longitude: str | None = None


class ProducerCourseRequest(BaseModel):
    course_id: int


class ProducerEventRequest(ProducerCourseRequest):
    external_active_id: str = Field(min_length=1, max_length=64)
    enc: str = Field(min_length=1, max_length=128)
    source_course_id: str = Field(min_length=1, max_length=64)
    latitude: str | None = None
    longitude: str | None = None
    observed_at: datetime | None = None
