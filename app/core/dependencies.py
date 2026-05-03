from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from bson import ObjectId

from app.core.security import decode_access_token

# Tells FastAPI/Swagger where the token comes from.
# tokenUrl is unused (no password login) but required by the scheme.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/google", auto_error=True)

_CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    request: Request,
    token: str = Depends(oauth2_scheme),
) -> dict:
    """
    FastAPI dependency — decodes the Bearer JWT and returns the user document.

    Raises 401 if:
      - Token is missing, malformed, or has an invalid signature
      - Token is expired
      - sub (user_id) in token is not a valid ObjectId
      - User no longer exists in MongoDB
    """
    try:
        payload = decode_access_token(token)
        user_id: str = payload.get("sub")
        if not user_id:
            raise _CREDENTIALS_EXCEPTION
    except JWTError:
        raise _CREDENTIALS_EXCEPTION

    if not ObjectId.is_valid(user_id):
        raise _CREDENTIALS_EXCEPTION

    db   = request.app.state.db
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if user is None:
        raise _CREDENTIALS_EXCEPTION

    return user
