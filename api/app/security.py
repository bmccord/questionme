"""Candidate tokens and the single admin session.

The candidate link is a capability URL: possession of the token is the
credential. That is the right trade for a no-accounts form, but it only works
if the token is unguessable, so it comes from `secrets`, never from the
database. MariaDB's UUID() is version 1 - timestamp plus MAC address - and
consecutive calls differ only in the low timestamp digits, which would let one
candidate enumerate every other link.
"""
import hmac
import secrets
import time

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import HTTPException, Request, status
from itsdangerous import BadSignature, URLSafeTimedSerializer

from .config import settings

TOKEN_BYTES = 32
SESSION_COOKIE = "qm_admin"
SESSION_MAX_AGE = 60 * 60 * 12

_hasher = PasswordHasher()
_serializer = URLSafeTimedSerializer(settings.session_secret or secrets.token_hex(32),
                                     salt="qm-admin-session")

# Crude in-process throttle. One admin, one box - a table would be overkill.
_attempts: dict[str, list[float]] = {}
MAX_ATTEMPTS, WINDOW = 5, 300


def new_candidate_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def check_admin(username: str, password: str, client: str) -> bool:
    now = time.time()
    recent = [t for t in _attempts.get(client, []) if now - t < WINDOW]
    if len(recent) >= MAX_ATTEMPTS:
        _attempts[client] = recent
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            "too many attempts, wait a few minutes")
    ok = hmac.compare_digest(username, settings.admin_user)
    try:
        _hasher.verify(settings.admin_password_hash, password)
    except (VerifyMismatchError, Exception):
        ok = False
    if not ok:
        _attempts[client] = recent + [now]
    else:
        _attempts.pop(client, None)
    return ok


def issue_session() -> str:
    return _serializer.dumps({"u": settings.admin_user})


def require_admin(request: Request) -> str:
    raw = request.cookies.get(SESSION_COOKIE)
    if not raw:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not signed in")
    try:
        data = _serializer.loads(raw, max_age=SESSION_MAX_AGE)
    except BadSignature:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "session expired")
    return data["u"]
