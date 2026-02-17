"""Base class for all crew sub-agents."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Callable, Optional

from phoenix_agent.crew.task import Task, TaskResult


class SubAgent(ABC):
    """Abstract base for crew sub-agents."""

    name: str = "base"

    def __init__(self, emit: Optional[Callable[..., Any]] = None) -> None:
        self._emit = emit or (lambda *a, **kw: None)
        self._log = logging.getLogger(f"phoenix.crew.{self.name}")

    def emit_event(self, event_type: str, **kwargs: Any) -> None:
        self._emit(event_type, **kwargs)

    @abstractmethod
    def execute(self, task: Task) -> TaskResult:
        ...
