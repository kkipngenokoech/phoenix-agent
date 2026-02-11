"""Base tool framework for Phoenix Agent."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class ToolCategory(Enum):
    ANALYSIS = "analysis"
    TESTING = "testing"
    VCS = "vcs"
    UTILITY = "utility"


@dataclass
class ToolResult:
    success: bool
    output: Any = None
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    execution_time_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "metadata": self.metadata,
            "execution_time_ms": self.execution_time_ms,
        }

    def to_string(self) -> str:
        if self.success:
            if isinstance(self.output, dict):
                import json
                return json.dumps(self.output, indent=2, default=str)
            return str(self.output)
        return f"Error: {self.error}"


class BaseTool(ABC):
    name: str = ""
    description: str = ""
    category: ToolCategory = ToolCategory.UTILITY
    parameters_schema: dict = {}

    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        """Execute the tool with given parameters."""
        ...

    def validate_parameters(self, **kwargs) -> tuple[bool, Optional[str]]:
        """Validate input parameters against schema."""
        required = self.parameters_schema.get("required", [])
        for param in required:
            if param not in kwargs:
                return False, f"Missing required parameter: {param}"
        return True, None

    def timed_execute(self, **kwargs) -> ToolResult:
        """Execute with timing."""
        valid, error = self.validate_parameters(**kwargs)
        if not valid:
            return ToolResult(success=False, error=error)
        start = time.time()
        try:
            result = self.execute(**kwargs)
        except Exception as e:
            result = ToolResult(success=False, error=str(e))
        result.execution_time_ms = (time.time() - start) * 1000
        return result
