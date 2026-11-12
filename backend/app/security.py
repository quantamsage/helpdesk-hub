"""Password hashing (Argon2) and JWT access tokens."""
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()  # Argon2id with the library's recommended settings
_DUMMY_HASH = _hasher.hash("not-a-real-password")
_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def waste_time_like_a_real_check(password: str) -> None:
    """Used when the email doesn't exist, so a login for an unknown email takes
    as long as a wrong password. Otherwise response time reveals which emails exist."""
    verify_password(password, _DUMMY_HASH)


def create_access_token(user_id: UUID, secret: str, minutes: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "iat": now, "exp": now + timedelta(minutes=minutes)}
    return jwt.encode(payload, secret, algorithm=_ALGORITHM)


def read_access_token(token: str, secret: str) -> UUID | None:
    """Return the user id from a valid token, or None if it's invalid or expired."""
    try:
        payload = jwt.decode(
            token, secret, algorithms=[_ALGORITHM], options={"require": ["exp", "sub"]}
        )
        return UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError):
        return None
