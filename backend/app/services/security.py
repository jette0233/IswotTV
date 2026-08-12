import base64
import hashlib
import os
import time
from datetime import datetime, timedelta
from functools import wraps

import bcrypt
import jwt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from flask import current_app, g, jsonify, request

from app.models.models import User


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("ascii")


def verify_password(password: str, stored_hash: str | None) -> tuple[bool, bool]:
    if not stored_hash:
        return False, False
    if stored_hash.startswith("$2"):
        return bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("ascii")), False
    legacy = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return legacy == stored_hash, legacy == stored_hash


def make_access_token(user: User, expires_seconds: int = 900) -> str:
    now = int(time.time())
    payload = {"sub": str(user.id), "role": "admin" if user.is_admin else "user", "iat": now, "exp": now + expires_seconds, "type": "access"}
    return jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm="HS256")


def decode_access_token(token: str) -> dict:
    payload = jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=["HS256"])
    if payload.get("type") not in {None, "access"}:
        raise jwt.InvalidTokenError("wrong token type")
    return payload


def _bearer_token() -> str:
    value = request.headers.get("Authorization", "")
    return value[7:].strip() if value.startswith("Bearer ") else ""


def require_user(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            payload = decode_access_token(_bearer_token())
            user = User.query.get(int(payload["sub"]))
        except (KeyError, ValueError, jwt.PyJWTError):
            user = None
        if not user:
            return jsonify({"code": 401, "msg": "未登录或Token已过期"}), 401
        g.current_user = user
        return func(*args, **kwargs)

    return wrapper


class CredentialCipher:
    prefix = "enc:v1:"

    @staticmethod
    def _key() -> bytes:
        configured = current_app.config.get("CREDENTIAL_ENCRYPTION_KEY", "")
        if configured:
            try:
                key = base64.urlsafe_b64decode(configured + "=" * (-len(configured) % 4))
            except ValueError as exc:
                raise RuntimeError("CREDENTIAL_ENCRYPTION_KEY must be URL-safe base64") from exc
            if len(key) != 32:
                raise RuntimeError("CREDENTIAL_ENCRYPTION_KEY must decode to 32 bytes")
            return key
        if current_app.config.get("ENV") in {"production", "prod"}:
            raise RuntimeError("CREDENTIAL_ENCRYPTION_KEY is required")
        return hashlib.sha256(current_app.config["SECRET_KEY"].encode("utf-8")).digest()

    @classmethod
    def encrypt(cls, value: str) -> str:
        nonce = os.urandom(12)
        encrypted = AESGCM(cls._key()).encrypt(nonce, value.encode("utf-8"), None)
        return cls.prefix + base64.urlsafe_b64encode(nonce + encrypted).decode("ascii")

    @classmethod
    def decrypt(cls, value: str | None) -> str | None:
        if not value or not value.startswith(cls.prefix):
            return value
        raw = base64.urlsafe_b64decode(value[len(cls.prefix):].encode("ascii"))
        return AESGCM(cls._key()).decrypt(raw[:12], raw[12:], None).decode("utf-8")


def new_refresh_expiry() -> datetime:
    return datetime.utcnow() + timedelta(days=30)
