"""Registry for pending review approvals across agent sessions.

Bridges the REST API layer (async) and the agent thread (sync) using
Redis Pub/Sub. The agent blocks on a message from a Redis channel,
and the API endpoint publishes to that channel to unblock it.
"""
from __future__ import annotations

import json
import logging
import time

import redis

from phoenix_agent.config import PhoenixConfig
from phoenix_agent.models import ReviewVerdict

logger = logging.getLogger(__name__)

# Share a single Redis client instance
_config = PhoenixConfig.from_env()
_redis_client = redis.from_url(_config.redis.url, decode_responses=True)


def get_channel_name(session_id: str) -> str:
    """Get the Redis channel name for a given session."""
    return f"phoenix:review:{session_id}"


def register_review(session_id: str) -> redis.client.PubSub:
    """
    Create and register a Redis PubSub subscriber for a session awaiting review.
    """
    channel = get_channel_name(session_id)
    pubsub = _redis_client.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe(channel)
    logger.info(f"Subscribed to Redis channel: {channel}")
    return pubsub


def submit_verdict(session_id: str, verdict: ReviewVerdict) -> bool:
    """Submit a review verdict by publishing it to Redis."""
    channel = get_channel_name(session_id)
    message = verdict.model_dump_json()
    try:
        logger.info(f"Publishing verdict to {channel}: {message}")
        _redis_client.publish(channel, message)
        return True
    except redis.exceptions.RedisError as e:
        logger.error(f"Failed to publish to Redis channel {channel}: {e}")
        return False


def await_verdict(
    pubsub: redis.client.PubSub, timeout: int | None = None
) -> ReviewVerdict | None:
    """
    Wait for a verdict from the pubsub channel.
    Handles message parsing and returns a ReviewVerdict object.
    This function now polls Redis until a message is received or timeout occurs.
    """
    start_time = time.time()
    while True:
        # Check for overall timeout
        if timeout is not None:
            elapsed = time.time() - start_time
            if elapsed >= timeout:
                logger.warning(f"Timed out after {elapsed:.2f}s waiting for review verdict.")
                return None

        # Poll Redis with a short timeout to remain responsive
        try:
            message = pubsub.get_message(timeout=1.0)
        except redis.exceptions.RedisError as e:
            logger.error(f"Redis error while awaiting verdict: {e}")
            return None

        if message is None:
            continue  # No message, loop again

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


def cleanup(pubsub: redis.client.PubSub) -> None:
    """Unsubscribe and close the pubsub connection."""
    if pubsub:
        try:
            pubsub.unsubscribe()
            pubsub.close()
            logger.info("Cleaned up Redis pubsub connection.")
        except Exception as e:
            logger.error(f"Error during pubsub cleanup: {e}")
