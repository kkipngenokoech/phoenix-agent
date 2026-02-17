"""Task and result types for crew sub-agents."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TaskType(str, Enum):
    ANALYZE = "analyze"      # OBSERVE + REASON
    STRATEGIZE = "strategize"  # PLAN + DECIDE
    CODE = "code"            # modify_code / parse_code
    TEST = "test"            # VERIFY


@dataclass
class Task:
    task_type: TaskType
    payload: dict[str, Any] = field(default_factory=dict)
    task_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])


@dataclass
class TaskResult:
    task_id: str
    task_type: TaskType
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
