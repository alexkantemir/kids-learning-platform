from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.router import api_router
from app.core.config import settings
from app.db.session import engine
from app.db.base import Base

# Idempotent column migrations (IF NOT EXISTS)
_V11_MIGRATIONS = [
    "ALTER TABLE lesson_steps ADD COLUMN IF NOT EXISTS step_subtype VARCHAR(32)",
    "ALTER TABLE lesson_steps ADD COLUMN IF NOT EXISTS feedback_correct TEXT",
    "ALTER TABLE lesson_steps ADD COLUMN IF NOT EXISTS feedback_wrong TEXT",
    "ALTER TABLE lesson_steps ADD COLUMN IF NOT EXISTS hint TEXT",
    "ALTER TABLE lesson_steps ADD COLUMN IF NOT EXISTS step_data JSONB",
]

_V12_MIGRATIONS = [
    # enum must be in its own statement (cannot use new value in same txn)
    "ALTER TYPE lessonstatus ADD VALUE IF NOT EXISTS 'needs_review'",
]

_V12B_MIGRATIONS = [
    # lessons: validator fields
    "ALTER TABLE lessons ADD COLUMN IF NOT EXISTS validation_errors JSONB",
    "ALTER TABLE lessons ADD COLUMN IF NOT EXISTS generation_attempts INTEGER DEFAULT 1",
    # ai_requests: per-attempt tracking
    "ALTER TABLE ai_requests ADD COLUMN IF NOT EXISTS attempt_number INTEGER DEFAULT 1",
    "ALTER TABLE ai_requests ADD COLUMN IF NOT EXISTS validation_result JSONB",
    "ALTER TABLE ai_requests ADD COLUMN IF NOT EXISTS auto_fixed_log JSONB",
    # index for needs_review queue (requires needs_review enum value committed first)
    "CREATE INDEX IF NOT EXISTS idx_lessons_needs_review ON lessons (status) WHERE status = 'needs_review'",
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            for stmt in _V11_MIGRATIONS + _V12_MIGRATIONS:
                try:
                    await conn.execute(text(stmt))
                except Exception:
                    pass
    except Exception:
        pass
    # V12B runs in a separate transaction so the new enum value is visible
    try:
        async with engine.begin() as conn:
            for stmt in _V12B_MIGRATIONS:
                try:
                    await conn.execute(text(stmt))
                except Exception:
                    pass
    except Exception:
        pass
    yield


app = FastAPI(
    title="Kids Learning Platform API",
    version="0.2.0",
    docs_url=None if settings.ENVIRONMENT == "production" else "/api/docs",
    redoc_url=None if settings.ENVIRONMENT == "production" else "/api/redoc",
    openapi_url=None if settings.ENVIRONMENT == "production" else "/api/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://kids.it-kant.ru", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "kids-platform-api", "version": "0.2.0"}
