from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class UserDocument(BaseModel):
    """Mirrors the shape stored in the MongoDB users collection."""
    google_id:  str
    email:      str
    name:       str
    avatar:     Optional[str] = None
    created_at: datetime
    updated_at: datetime
    last_login: datetime


class UserResponse(BaseModel):
    """Public user shape returned to the mobile app."""
    id:        str
    name:      str
    email:     str
    avatar:    Optional[str] = None
    joined_at: datetime

    @classmethod
    def from_doc(cls, doc: dict) -> "UserResponse":
        return cls(
            id        = str(doc["_id"]),
            name      = doc["name"],
            email     = doc["email"],
            avatar    = doc.get("avatar"),
            joined_at = doc["created_at"],
        )


class AuthResponse(BaseModel):
    """Response shape for POST /api/auth/google."""
    access_token: str
    token_type:   str = "bearer"
    user:         UserResponse
