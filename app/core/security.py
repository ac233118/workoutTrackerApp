from datetime import datetime, timezone, timedelta
from jose import jwt, JWTError

from app.core.config import settings


def create_access_token(user_id: str, email: str) -> str:
    """
    Creates a signed JWT containing user_id and email.
    Expires in JWT_EXPIRE_DAYS days (default 30).
    """
    expire = datetime.now(timezone.utc) + timedelta(days=settings.JWT_EXPIRE_DAYS)
    payload = {
        "sub":   user_id,
        "email": email,
        "exp":   expire,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """
    Decodes and validates a JWT.
    Raises jose.JWTError on invalid signature, expiry, or malformed token.
    Caller is responsible for catching JWTError and raising HTTP 401.
    """
    return jwt.decode(
        token,
        settings.JWT_SECRET,
        algorithms=[settings.JWT_ALGORITHM],
    )
