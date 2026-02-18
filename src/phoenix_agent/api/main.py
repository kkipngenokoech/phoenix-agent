"""FastAPI application entry point for Phoenix Agent."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from phoenix_agent.api.routes import init_shared_state, router, ws_router
from phoenix_agent.config import PhoenixConfig
from phoenix_agent.memory.history import RefactoringHistory
from phoenix_agent.memory.session import SessionMemory

logger = logging.getLogger(__name__)

_MIGRATIONS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "migrations"


def _run_migrations(history: RefactoringHistory) -> None:
    """Apply SQL migrations on startup if the DB connection is available."""
    conn = history._conn
    if not conn:
        return
    if not _MIGRATIONS_DIR.is_dir():
        logger.info("No migrations directory found — skipping auto-migrate")
        return
    for sql_file in sorted(_MIGRATIONS_DIR.glob("*.sql")):
        try:
            sql = sql_file.read_text()
            with conn.cursor() as cur:
                cur.execute(sql)
            logger.info(f"Migration applied: {sql_file.name}")
        except Exception as e:
            logger.warning(f"Migration {sql_file.name} skipped: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle — initialize shared resources."""
    config = PhoenixConfig.from_env()

    log_level = getattr(logging, config.log_level.upper(), logging.INFO)
    logging.basicConfig(level=log_level, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    session_memory = SessionMemory(config)
    history = RefactoringHistory(config)

    _run_migrations(history)
    init_shared_state(config, session_memory, history)
    logger.info("Phoenix API started")

    yield

    history.close()
    logger.info("Phoenix API shut down")


app = FastAPI(
    title="Phoenix Agent API",
    description="Agentic code refactoring with real-time streaming",
    version="0.2.0",
    lifespan=lifespan,
)

_cors_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
# Add production frontend URL if set
_extra_origin = os.getenv("CORS_ORIGIN")
if _extra_origin:
    _cors_origins.append(_extra_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(ws_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "phoenix-agent"}
