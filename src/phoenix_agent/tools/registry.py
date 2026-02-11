"""Tool registry - manages available tools and their execution."""

from __future__ import annotations

import logging
from typing import Optional

from phoenix_agent.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}
        self._execution_history: list[dict] = []

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name}")

    def get(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)

    def list_tools(self) -> list[dict]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "category": t.category.value,
            }
            for t in self._tools.values()
        ]

    def execute(self, tool_name: str, **kwargs) -> ToolResult:
        tool = self._tools.get(tool_name)
        if not tool:
            return ToolResult(success=False, error=f"Unknown tool: {tool_name}")

        logger.info(f"Executing tool: {tool_name}")
        result = tool.timed_execute(**kwargs)

        self._execution_history.append({
            "tool": tool_name,
            "success": result.success,
            "execution_time_ms": result.execution_time_ms,
            "error": result.error,
        })

        return result

    def get_tool_descriptions(self) -> str:
        lines = []
        for t in self._tools.values():
            lines.append(f"- {t.name}: {t.description}")
        return "\n".join(lines)

    @property
    def execution_history(self) -> list[dict]:
        return self._execution_history
