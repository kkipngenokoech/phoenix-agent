"""StrategistAgent - wraps PLAN + DECIDE phases."""

from __future__ import annotations

from typing import Any, Optional

from phoenix_agent.crew.base_agent import SubAgent
from phoenix_agent.crew.task import Task, TaskResult, TaskType
from phoenix_agent.models import ObservationResult, ReasoningAnalysis, TestResult
from phoenix_agent.orchestrator.arbiter import Arbiter
from phoenix_agent.orchestrator.planner import Planner


class StrategistAgent(SubAgent):
    name = "strategist"

    def __init__(self, planner: Planner, arbiter: Arbiter, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._planner = planner
        self._arbiter = arbiter

    def execute(self, task: Task) -> TaskResult:
        """Run PLAN then DECIDE, returning plan + decision."""
        observation: ObservationResult = task.payload["observation"]
        analysis: ReasoningAnalysis = task.payload["analysis"]
        last_test_failure: Optional[TestResult] = task.payload.get("last_test_failure")
        project_path: str = task.payload.get("project_path", "")
        iteration = task.payload.get("iteration", 1)

        # PLAN
        self._log.info("PLAN: generating refactoring steps")
        plan = self._planner.plan(analysis, observation, last_test_failure, project_path)
        self.emit_event("phase_update", phase="PLAN", data=plan, iteration=iteration)

        if not plan.steps:
            return TaskResult(
                task_id=task.task_id,
                task_type=TaskType.STRATEGIZE,
                success=False,
                error="Planning produced no steps",
            )

        # DECIDE
        self._log.info("DECIDE: calculating risk")
        test_coverage = 0.0
        if observation.existing_test_results and observation.existing_test_results.coverage:
            test_coverage = observation.existing_test_results.coverage.overall_percentage

        decision = self._arbiter.decide(plan, analysis, test_coverage)
        self.emit_event("phase_update", phase="DECIDE", data=decision, iteration=iteration)

        return TaskResult(
            task_id=task.task_id,
            task_type=TaskType.STRATEGIZE,
            success=True,
            data={"plan": plan, "decision": decision},
        )
