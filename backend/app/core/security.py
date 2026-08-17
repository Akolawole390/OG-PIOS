import hashlib
import hmac
from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings

settings = get_settings()
password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])


def password_fingerprint(hashed_password: str) -> str:
    """A short, non-reversible fingerprint of a password hash — embedded in password-reset
    tokens so that consuming a reset token (which changes the hash) automatically invalidates
    it, and any reset issued before an intervening password change also stops working, with no
    token-storage table needed. Keyed on `secret_key` so rotating it invalidates every
    outstanding reset/verification token as a free side effect."""
    return hmac.new(settings.secret_key.encode(), hashed_password.encode(), hashlib.sha256).hexdigest()[:16]


class TokenPurposeError(Exception):
    """Raised when a purpose-scoped token (reset/verify) decodes fine but was issued for a
    different purpose than the endpoint consuming it expects."""


def create_purpose_token(subject: str, purpose: str, expires_minutes: int, **extra: str) -> str:
    """Stateless, single-purpose JWT for password reset / email verification — reuses the same
    signing machinery as `create_access_token` but is never accepted by `get_current_user`
    (no `purpose` claim there), and vice versa: `decode_purpose_token` rejects a login token."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    payload = {"sub": subject, "purpose": purpose, "exp": expire, **extra}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_purpose_token(token: str, expected_purpose: str) -> dict:
    payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    if payload.get("purpose") != expected_purpose:
        raise TokenPurposeError("Unexpected token purpose")
    return payload
