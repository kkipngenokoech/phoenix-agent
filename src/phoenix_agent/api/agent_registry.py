"""Registry for pending review approvals across agent sessions.

Bridges the REST API layer (async) and the agent thread (sync).
Uses Redis Pub/Sub when available, falls back to in-process
threading primitives when Redis is not reachable.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any

from phoenix_agent.config import PhoenixConfig
from phoenix_agent.models import ReviewVerdict

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-process fallback: threading.Event + shared dict
# ---------------------------------------------------------------------------
_in_process_lock = threading.Lock()
_in_process_waiters: dict[str, dict[str, Any]] = {}
# Each entry: {"event": threading.Event, "verdict": ReviewVerdict | None}

# ---------------------------------------------------------------------------
# Try to connect to Redis; if it fails, we go in-process only
# ---------------------------------------------------------------------------
_redis_client = None
_use_redis = False

try:
    import redis as _redis_mod

    _config = PhoenixConfig.from_env()
    _client = _redis_mod.from_url(_config.redis.url, decode_responses=True)
    _client.ping()  # Verify connectivity
    _redis_client = _client
    _use_redis = True
    logger.info("agent_registry: Redis available — using Pub/Sub for review gate")
except Exception as e:
    logger.warning(f"agent_registry: Redis not available ({e}) — using in-process fallback")


def get_channel_name(session_id: str) -> str:
    return f"phoenix:review:{session_id}"


# ---------------------------------------------------------------------------
# Public API — transparent Redis / in-process switching
# ---------------------------------------------------------------------------

def register_review(session_id: str) -> Any:
    """Register for review verdicts. Returns an opaque handle."""
    if _use_redis:
        try:
            channel = get_channel_name(session_id)
            pubsub = _redis_client.pubsub(ignore_subscribe_messages=True)
            pubsub.subscribe(channel)
            logger.info(f"Subscribed to Redis channel: {channel}")
            return pubsub
        except Exception as e:
            logger.warning(f"Redis subscribe failed ({e}) — falling back to in-process")

    # In-process fallback
    event = threading.Event()
    with _in_process_lock:
        _in_process_waiters[session_id] = {"event": event, "verdict": None}
    logger.info(f"Registered in-process review waiter for {session_id}")
    return ("in_process", session_id)


def submit_verdict(session_id: str, verdict: ReviewVerdict) -> bool:
    """Submit a review verdict (called from the API layer)."""
    # Try Redis first
    if _use_redis:
        try:
            channel = get_channel_name(session_id)
            message = verdict.model_dump_json()
            logger.info(f"Publishing verdict to {channel}: {message}")
            _redis_client.publish(channel, message)
            # Also set in-process in case the agent fell back
        except Exception as e:
            logger.warning(f"Redis publish failed ({e})")

    # Always update in-process waiter (covers fallback + hybrid)
    with _in_process_lock:
        waiter = _in_process_waiters.get(session_id)
        if waiter:
            waiter["verdict"] = verdict
            waiter["event"].set()
            logger.info(f"In-process verdict set for {session_id}")
            return True

    if _use_redis:
        return True  # Published via Redis even if no in-process waiter
    logger.error(f"No waiter found for session {session_id}")
    return False


def await_verdict(handle: Any, timeout: int | None = None) -> ReviewVerdict | None:
    """Block until a verdict arrives or timeout."""
    # In-process handle
    if isinstance(handle, tuple) and handle[0] == "in_process":
        session_id = handle[1]
        with _in_process_lock:
            waiter = _in_process_waiters.get(session_id)
        if not waiter:
            logger.error(f"No in-process waiter for {session_id}")
            return None
        logger.info(f"Waiting (in-process) for review verdict on {session_id}...")
        signaled = waiter["event"].wait(timeout=timeout)
        if not signaled:
            logger.warning(f"Timed out after {timeout}s waiting for review verdict.")
            return None
        return waiter["verdict"]

    # Redis PubSub handle
    start_time = time.time()
    while True:
        if timeout is not None:
            elapsed = time.time() - start_time
            if elapsed >= timeout:
                logger.warning(f"Timed out after {elapsed:.2f}s waiting for review verdict.")
                return None
        try:
            message = handle.get_message(timeout=1.0)
        except Exception as e:
            logger.error(f"Redis error while awaiting verdict: {e}")
            return None
        if message is None:
            continue
        if message["type"] == "message":
            data = message["data"]
            logger.info(f"Received message: {data}")
            try:
                verdict_data = json.loads(data)
                return ReviewVerdict(**verdict_data)
            except (json.JSONDecodeError, TypeError) as e:
                logger.error(f"Failed to parse verdict message: {e}")
                return None
    return None


def cleanup(handle: Any) -> None:
    """Clean up the review handle."""
    if isinstance(handle, tuple) and handle[0] == "in_process":
        session_id = handle[1]
        with _in_process_lock:
            _in_process_waiters.pop(session_id, None)
        logger.info(f"Cleaned up in-process waiter for {session_id}")
        return

    # Redis PubSub
    if handle:
        try:
            handle.unsubscribe()
            handle.close()
            logger.info("Cleaned up Redis pubsub connection.")
        except Exception as e:
            logger.error(f"Error during pubsub cleanup: {e}")
