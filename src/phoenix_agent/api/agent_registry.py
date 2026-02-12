"""Registry for pending review approvals across agent sessions.

Bridges the REST API layer (async) and the agent thread (sync) using
threading.Event objects. The agent blocks on event.wait(), and the API
endpoint calls submit_verdict() to unblock it.
"""

from __future__ import annotations

import threading
from typing import Optional

from phoenix_agent.models import ReviewVerdict

_approval_events: dict[str, threading.Event] = {}
_approval_verdicts: dict[str, ReviewVerdict] = {}
_lock = threading.Lock()


def register_review(session_id: str) -> threading.Event:
    """Create and register a threading.Event for a session awaiting review."""
    event = threading.Event()
    with _lock:
        _approval_events[session_id] = event
    return event


def submit_verdict(session_id: str, verdict: ReviewVerdict) -> bool:
    """Submit a review verdict. Returns False if no pending review exists."""
    with _lock:
        event = _approval_events.get(session_id)
        if not event:
            return False
        _approval_verdicts[session_id] = verdict
        event.set()
    return True


def get_verdict(session_id: str) -> Optional[ReviewVerdict]:
    """Retrieve and remove the verdict for a session."""
    with _lock:
        return _approval_verdicts.pop(session_id, None)


def cleanup(session_id: str) -> None:
    """Remove all state for a session."""
    with _lock:
        _approval_events.pop(session_id, None)
        _approval_verdicts.pop(session_id, None)
