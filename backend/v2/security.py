import base64
import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from v2.db import User, get_session
from v2.settings import get_settings

bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    if password_hash.startswith("$2"):
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    return hashlib.sha256(password.encode()).hexdigest() == password_hash


def access_token(user: User, minutes: int = 15) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": str(user.id), "role": "admin" if user.is_admin else "user", "type": "access", "iat": now, "exp": now + timedelta(minutes=minutes)}, get_settings().secret_key, algorithm="HS256")


def opaque_refresh_token() -> tuple[str, str]:
    token = secrets.token_urlsafe(48)
    return token, hashlib.sha256(token.encode()).hexdigest()


async def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), session: AsyncSession = Depends(get_session)) -> User:
    if not credentials:
        raise HTTPException(401, "missing bearer token")
    try:
        payload = jwt.decode(credentials.credentials, get_settings().secret_key, algorithms=["HS256"])
        if payload.get("type") not in {None, "access"}:
            raise ValueError
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(401, "invalid or expired token")
    user = await session.scalar(select(User).where(User.id == user_id))
    if not user:
        raise HTTPException(401, "user no longer exists")
    return user


def _cipher_key() -> bytes:
    settings = get_settings()
    if settings.credential_encryption_key:
        key = base64.urlsafe_b64decode(settings.credential_encryption_key + "=" * (-len(settings.credential_encryption_key) % 4))
        if len(key) != 32:
            raise RuntimeError("CREDENTIAL_ENCRYPTION_KEY must decode to 32 bytes")
        return key
    return hashlib.sha256(settings.secret_key.encode()).digest()


def encrypt_credential(value: str) -> str:
    nonce = os.urandom(12)
    encrypted = AESGCM(_cipher_key()).encrypt(nonce, value.encode(), None)
    return "enc:v1:" + base64.urlsafe_b64encode(nonce + encrypted).decode()


def decrypt_credential(value: str | None) -> str | None:
    if not value or not value.startswith("enc:v1:"):
        return value
    raw = base64.urlsafe_b64decode(value[7:])
    return AESGCM(_cipher_key()).decrypt(raw[:12], raw[12:], None).decode()
