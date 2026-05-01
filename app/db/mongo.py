from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from fastapi import Request
import certifi
import ssl
from app.core.config import settings

def _make_ssl_context() -> ssl.SSLContext:
    """Build an SSL context that trusts the certifi CA bundle explicitly."""
    ctx = ssl.create_default_context(cafile=certifi.where())
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED
    return ctx


def create_mongo_client() -> AsyncIOMotorClient:
    if settings.IS_ATLAS:
        return AsyncIOMotorClient(
            settings.MONGO_URL,
            tls=True,
            tlsCAFile=certifi.where(),
        )
    return AsyncIOMotorClient(settings.MONGO_URL)


def get_db(request: Request) -> AsyncIOMotorDatabase:
    """FastAPI dependency — injects the database into route handlers."""
    return request.app.state.db
