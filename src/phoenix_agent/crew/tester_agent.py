"""TesterAgent - wraps the VERIFY phase."""

from __future__ import annotations

from typing import Any

from phoenix_agent.crew.base_agent import SubAgent
from phoenix_agent.crew.task import Task, TaskResult, TaskType
from phoenix_agent.models import FileMetrics, ValidationLevel
from phoenix_agent.orchestrator.verifier import Verifier


class TesterAgent(SubAgent):
    name = "tester"

    def __init__(self, verifier: Verifier, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._verifier = verifier

    def execute(self, task: Task) -> TaskResult:
        """Run VERIFY phase: tests + metrics comparison."""
        step_results: list[dict] = task.payload["step_results"]
        validation_level: ValidationLevel = task.payload["validation_level"]
        project_path: str = task.payload["project_path"]
        metrics_before: list[FileMetrics] = task.payload["metrics_before"]
        iteration = task.payload.get("iteration", 1)

        self._log.info("VERIFY: running tests and comparing metrics")
        report = self._verifier.verify(
            step_results, validation_level, project_path, metrics_before,
        )
        self.emit_event("phase_update", phase="VERIFY", data=report, iteration=iteration)

        return TaskResult(
            task_id=task.task_id,
            task_type=TaskType.TEST,
            success=report.tests_passed and report.improved,
            data={"report": report},
        )
