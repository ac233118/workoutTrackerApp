from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.mongo import create_mongo_client
from app.db.seed import seed_templates
from app.api.router import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── startup ──────────────────────────────────────────────
    app.state.client = create_mongo_client()
    app.state.db     = app.state.client[settings.DB_NAME]
    yield
    # ── shutdown ─────────────────────────────────────────────
    app.state.client.close()


app = FastAPI(
    title="Workout Tracker API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
