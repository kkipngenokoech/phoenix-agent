"""WebSocket connection manager for streaming phase events."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections per session."""

    def __init__(self) -> None:
        self._connections: dict[str, list[WebSocket]] = {}
        self._queues: dict[str, asyncio.Queue] = {}
        self._drain_tasks: dict[str, asyncio.Task] = {}

    async def connect(self, session_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        if session_id not in self._connections:
            self._connections[session_id] = []
        self._connections[session_id].append(websocket)
        logger.info(f"WebSocket connected for session {session_id}")

        # Start a single drain task per session (first connection triggers it)
        if session_id not in self._drain_tasks or self._drain_tasks[session_id].done():
            self._drain_tasks[session_id] = asyncio.create_task(
                self._drain_queue(session_id)
            )

    def disconnect(self, session_id: str, websocket: WebSocket) -> None:
        if session_id in self._connections:
            self._connections[session_id] = [
                ws for ws in self._connections[session_id] if ws != websocket
            ]
            if not self._connections[session_id]:
                del self._connections[session_id]
        logger.info(f"WebSocket disconnected for session {session_id}")

    async def _drain_queue(self, session_id: str) -> None:
        """Single loop that drains the event queue and broadcasts to all connections."""
        queue = self.get_queue(session_id)
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    # Send heartbeat to keep connections alive
                    await self._broadcast(session_id, {"type": "heartbeat"})
                    continue

                if event is None:
                    # Agent finished — stop draining (the agent already
                    # emitted a "completed" event with the result data)
                    break

                await self._broadcast(session_id, event)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Drain loop error for {session_id}: {e}")
        finally:
            self._drain_tasks.pop(session_id, None)
            self._queues.pop(session_id, None)

    async def _broadcast(self, session_id: str, event: dict) -> None:
        """Send event to all connections for a session."""
        connections = self._connections.get(session_id, [])
        dead: list[WebSocket] = []
        for ws in connections:
            try:
                await ws.send_json(event)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(session_id, ws)

    async def send_event(self, session_id: str, event: dict) -> None:
        """Send event to all connections for a session (legacy alias)."""
        await self._broadcast(session_id, event)

    def get_queue(self, session_id: str) -> asyncio.Queue:
        """Get or create an event queue for a session."""
        if session_id not in self._queues:
            self._queues[session_id] = asyncio.Queue()
        return self._queues[session_id]

    def remove_queue(self, session_id: str) -> None:
        self._queues.pop(session_id, None)


# Global singleton
manager = ConnectionManager()


def make_phase_callback(session_id: str, loop: asyncio.AbstractEventLoop):
    """Create a sync callback that pushes events into the async queue.

    The agent runs in a thread, so we use loop.call_soon_threadsafe to
    bridge sync→async.
    """
    queue = manager.get_queue(session_id)

    def callback(event_type: str, phase: str | None = None,
                 data: Any = None, iteration: int = 0, **kwargs):
        event = {
            "type": event_type,
            "session_id": session_id,
            "iteration": iteration,
            "phase": phase,
            "data": _serialize(data),
        }
        if kwargs.get("message"):
            event["message"] = kwargs["message"]
        loop.call_soon_threadsafe(queue.put_nowait, event)

    return callback


def _serialize(obj: Any) -> Any:
    """Best-effort JSON-safe serialization."""
    if obj is None:
        return None
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialize(v) for v in obj]
    try:
        json.dumps(obj)
        return obj
    except (TypeError, ValueError):
        return str(obj)
