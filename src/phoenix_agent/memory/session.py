"""Short-term memory: Redis session state with 24-hour TTL."""

from __future__ import annotations

import json
import logging
from typing import Optional

import redis

from phoenix_agent.config import PhoenixConfig
from phoenix_agent.models import (
    IterationData,
    RefactoringGoal,
    ReviewPayload,
    SessionState,
    SessionStatus,
)

logger = logging.getLogger(__name__)

SESSION_PREFIX = "phoenix:session"


class SessionMemory:
    def __init__(self, config: PhoenixConfig) -> None:
        self._ttl = config.redis.session_ttl
        try:
            self._client = redis.from_url(config.redis.url, decode_responses=True)
            self._client.ping()
            logger.info("Connected to Redis")
        except redis.ConnectionError:
            logger.warning("Redis unavailable - falling back to in-memory store")
            self._client = None
            self._fallback: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _set(self, key: str, value: str, ttl: Optional[int] = None) -> None:
        ttl = ttl or self._ttl
        if self._client:
            self._client.setex(key, ttl, value)
        else:
            self._fallback[key] = value

    def _get(self, key: str) -> Optional[str]:
        if self._client:
            return self._client.get(key)
        return self._fallback.get(key)

    def _delete(self, key: str) -> None:
        if self._client:
            self._client.delete(key)
        else:
            self._fallback.pop(key, None)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_session(self, goal: RefactoringGoal, target_path: str) -> SessionState:
        session = SessionState(goal=goal, target_path=target_path)
        key = f"{SESSION_PREFIX}:{session.session_id}"
        self._set(key, session.model_dump_json())
        logger.info(f"Created session {session.session_id}")
        return session

    def get_session(self, session_id: str) -> Optional[SessionState]:
        raw = self._get(f"{SESSION_PREFIX}:{session_id}")
        if raw:
            return SessionState.model_validate_json(raw)
        return None

    def update_session(self, session: SessionState) -> None:
        session.updated_at = session.updated_at.__class__.utcnow()
        key = f"{SESSION_PREFIX}:{session.session_id}"
        self._set(key, session.model_dump_json())

    def write_iteration(self, session_id: str, data: IterationData) -> None:
        key = f"{SESSION_PREFIX}:{session_id}:iter:{data.iteration}"
        self._set(key, data.model_dump_json())

    def get_iteration(self, session_id: str, iteration: int) -> Optional[IterationData]:
        raw = self._get(f"{SESSION_PREFIX}:{session_id}:iter:{iteration}")
        if raw:
            return IterationData.model_validate_json(raw)
        return None

    def get_all_iterations(self, session_id: str) -> list[IterationData]:
        iterations = []
        i = 1
        while True:
            data = self.get_iteration(session_id, i)
            if data is None:
                break
            iterations.append(data)
            i += 1
        return iterations

    # ------------------------------------------------------------------
    # Review payloads (for human-in-the-loop approval)
    # ------------------------------------------------------------------

    def store_review(self, session_id: str, payload: ReviewPayload) -> None:
        """Store the review payload so reconnecting clients can fetch it."""
        key = f"phoenix:review:{session_id}"
        self._set(key, payload.model_dump_json())

    def get_review(self, session_id: str) -> Optional[ReviewPayload]:
        """Retrieve the stored review payload."""
        raw = self._get(f"phoenix:review:{session_id}")
        if raw:
            return ReviewPayload.model_validate_json(raw)
        return None

    def delete_session(self, session_id: str) -> None:
        self._delete(f"{SESSION_PREFIX}:{session_id}")
        # Also clean up iteration keys
        i = 1
        while True:
            key = f"{SESSION_PREFIX}:{session_id}:iter:{i}"
            raw = self._get(key)
            if raw is None:
                break
            self._delete(key)
            i += 1
