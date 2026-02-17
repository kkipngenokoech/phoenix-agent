"""AnalyzerAgent - wraps OBSERVE + REASON phases."""

from __future__ import annotations

from typing import Any

from phoenix_agent.crew.base_agent import SubAgent
from phoenix_agent.crew.task import Task, TaskResult, TaskType
from phoenix_agent.orchestrator.observer import Observer
from phoenix_agent.orchestrator.reasoner import Reasoner


class AnalyzerAgent(SubAgent):
    name = "analyzer"

    def __init__(self, observer: Observer, reasoner: Reasoner, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._observer = observer
        self._reasoner = reasoner

    def execute(self, task: Task) -> TaskResult:
        """Run OBSERVE then REASON, returning observation + analysis."""
        session_id = task.payload["session_id"]
        target_path = task.payload["target_path"]
        request = task.payload["request"]
        iteration = task.payload.get("iteration", 1)

        # OBSERVE
        self._log.info("OBSERVE: gathering codebase state")
        self.emit_event("phase_update", phase="OBSERVE", data={}, iteration=iteration)
        observation = self._observer.observe(session_id, target_path)
        self.emit_event("phase_update", phase="OBSERVE", data=observation, iteration=iteration)

        if not observation.complete:
            return TaskResult(
                task_id=task.task_id,
                task_type=TaskType.ANALYZE,
                success=False,
                error="Observation incomplete",
            )

        # REASON
        self._log.info("REASON: analyzing code")
        analysis = self._reasoner.reason(observation, request)
        self.emit_event("phase_update", phase="REASON", data=analysis, iteration=iteration)

        if not analysis.approach:
            return TaskResult(
                task_id=task.task_id,
                task_type=TaskType.ANALYZE,
                success=False,
                error="Reasoning produced no approach",
            )

        return TaskResult(
            task_id=task.task_id,
            task_type=TaskType.ANALYZE,
            success=True,
            data={"observation": observation, "analysis": analysis},
        )
