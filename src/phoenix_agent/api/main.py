"""FastAPI application entry point for Phoenix Agent."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from phoenix_agent.api.routes import init_shared_state, router, ws_router
from phoenix_agent.config import PhoenixConfig
from phoenix_agent.memory.history import RefactoringHistory
from phoenix_agent.memory.session import SessionMemory

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle — initialize shared resources."""
    config = PhoenixConfig.from_env()

    log_level = getattr(logging, config.log_level.upper(), logging.INFO)
    logging.basicConfig(level=log_level, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    session_memory = SessionMemory(config)
    history = RefactoringHistory(config)

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(ws_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "phoenix-agent"}
