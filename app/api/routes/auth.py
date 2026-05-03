from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.core.security import create_access_token
from app.models.user import AuthResponse, UserResponse

router = APIRouter(prefix="/api/auth", tags=["Auth"])

# ─── Google tokeninfo endpoint ────────────────────────────────────────────────
_GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"

# ─── Shared 401 ───────────────────────────────────────────────────────────────
_INVALID_TOKEN = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid Google token",
)
_EXPIRED_TOKEN = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Google token expired",
)
_AUTH_UNAVAILABLE = HTTPException(
    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    detail="Auth service unavailable",
)


# ─── Request schema ───────────────────────────────────────────────────────────

class GoogleAuthRequest(BaseModel):
    id_token: str


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def _verify_google_token(id_token: str) -> dict:
    """
    Calls Google tokeninfo API to verify the id_token.

    Returns the decoded Google payload on success.
    Raises:
      401 — invalid or expired token
      503 — network timeout or Google API unreachable
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                _GOOGLE_TOKENINFO_URL,
                params={"id_token": id_token},
            )
    except httpx.TimeoutException:
        raise _AUTH_UNAVAILABLE
    except httpx.RequestError:
        raise _AUTH_UNAVAILABLE

    if response.status_code != 200:
        data = response.json()
        # Google returns {"error": "invalid_token", "error_description": "Token expired: ..."}
        error = data.get("error", "")
        if "expir" in data.get("error_description", "").lower():
            raise _EXPIRED_TOKEN
        raise _INVALID_TOKEN

    payload = response.json()

    # Verify the token was issued for our app (prevents token substitution attacks)
    if settings.GOOGLE_CLIENT_ID:
        audience = payload.get("aud", "")
        if audience != settings.GOOGLE_CLIENT_ID:
            raise _INVALID_TOKEN

    return payload


async def _find_or_create_user(db, google_payload: dict) -> dict:
    """
    Upserts a user by google_id.
    - Existing user → update last_login + updated_at, return doc
    - New user      → insert full document, return doc
    """
    google_id = google_payload["sub"]
    email     = google_payload.get("email", "")
    name      = google_payload.get("name", "")
    avatar    = google_payload.get("picture")
    now       = datetime.now(timezone.utc)

    existing = await db.users.find_one({"google_id": google_id})

    if existing:
        await db.users.update_one(
            {"google_id": google_id},
            {"$set": {"last_login": now, "updated_at": now}},
        )
        existing["last_login"] = now
        existing["updated_at"] = now
        return existing

    # New user — insert and return
    doc = {
        "google_id":  google_id,
        "email":      email,
        "name":       name,
        "avatar":     avatar,
        "created_at": now,
        "updated_at": now,
        "last_login": now,
    }
    result = await db.users.insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


async def _ensure_indexes(db) -> None:
    """Creates unique indexes on google_id and email (idempotent)."""
    await db.users.create_index("google_id", unique=True)
    await db.users.create_index("email",     unique=True)


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.post(
    "/google",
    response_model=AuthResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate with Google ID token",
)
async def google_auth(payload: GoogleAuthRequest, request: Request):
    """
    Receives a Google ID token from the mobile app, verifies it with Google,
    finds or creates the user in MongoDB, and returns our own JWT.

    Steps:
      1. Verify id_token → Google tokeninfo API
      2. Extract google_id, email, name, avatar
      3. Find or create user in MongoDB
      4. Issue our own JWT (never store the Google token)
      5. Return JWT + user object
    """
    db = request.app.state.db

    # Ensure indexes exist (fast no-op after first run)
    await _ensure_indexes(db)

    # Step 1 & 2 — verify with Google
    google_payload = await _verify_google_token(payload.id_token)

    # Step 3 — find or create user
    user = await _find_or_create_user(db, google_payload)

    # Step 4 — issue our JWT (Google token is discarded here, never persisted)
    token = create_access_token(
        user_id=str(user["_id"]),
        email=user["email"],
    )

    # Step 5 — return
    return AuthResponse(
        access_token=token,
        user=UserResponse.from_doc(user),
    )


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current authenticated user",
)
async def get_me(current_user: dict = Depends(get_current_user)):
    """
    Returns the authenticated user's profile.
    Requires a valid Bearer JWT in the Authorization header.
    """
    return UserResponse.from_doc(current_user)
