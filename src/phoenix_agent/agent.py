"""Phoenix Agent - main 7-phase control loop.

Implements the closed-loop architecture:
OBSERVE → REASON → PLAN → DECIDE → ACT → VERIFY → UPDATE
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from phoenix_agent.config import PhoenixConfig
from phoenix_agent.llm.provider import create_llm
from phoenix_agent.memory.history import RefactoringHistory
from phoenix_agent.memory.knowledge_graph import CodebaseGraph
from phoenix_agent.memory.session import SessionMemory
from phoenix_agent.models import (
    AgentPhase,
    RefactoringGoal,
    SessionState,
    SessionStatus,
)
from phoenix_agent.orchestrator.arbiter import Arbiter
from phoenix_agent.orchestrator.executor import Executor
from phoenix_agent.orchestrator.observer import Observer
from phoenix_agent.orchestrator.planner import Planner
from phoenix_agent.orchestrator.reasoner import Reasoner
from phoenix_agent.orchestrator.updater import Updater
from phoenix_agent.orchestrator.verifier import Verifier
from phoenix_agent.tools.ast_parser import ASTParserTool
from phoenix_agent.tools.git_ops import GitOperationsTool
from phoenix_agent.tools.registry import ToolRegistry
from phoenix_agent.tools.test_runner import TestRunnerTool

logger = logging.getLogger(__name__)


class PhoenixAgent:
    """Main agentic refactoring system implementing the 7-phase control loop."""

    def __init__(self, config: PhoenixConfig | None = None) -> None:
        self.config = config or PhoenixConfig.from_env()

        # LLM
        logger.info("Initializing LLM...")
        self.llm = create_llm(self.config)

        # Tools
        self.ast_parser = ASTParserTool()
        self.test_runner = TestRunnerTool()
        self.git_ops = GitOperationsTool()

        self.tool_registry = ToolRegistry()
        self.tool_registry.register(self.ast_parser)
        self.tool_registry.register(self.test_runner)
        self.tool_registry.register(self.git_ops)

        # Memory
        self.session_memory = SessionMemory(self.config)
        self.history = RefactoringHistory(self.config)
        self.graph = CodebaseGraph(self.config)

        # Orchestrator modules
        self.observer = Observer(self.ast_parser, self.session_memory)
        self.reasoner = Reasoner(self.llm)
        self.planner = Planner(self.llm)
        self.arbiter = Arbiter(self.config)
        self.executor = Executor(self.config, self.tool_registry)
        self.verifier = Verifier(self.ast_parser, self.test_runner)
        self.updater = Updater(
            self.session_memory, self.history, self.graph,
            self.git_ops, self.ast_parser,
        )

        logger.info("Phoenix Agent initialized")

    def run(self, request: str, target_path: str) -> dict:
        """
        Main entry point. Runs the full refactoring loop.

        Args:
            request: Developer's refactoring request (e.g., "Refactor UserService to follow SRP")
            target_path: Path to the project/directory to refactor

        Returns:
            dict with status, session_id, and details
        """
        target = Path(target_path).resolve()
        if not target.exists():
            return {"status": "failed", "reason": f"Target path not found: {target_path}"}

        start_time = time.time()

        # Create session
        goal = RefactoringGoal(
            description=request,
            target_files=[],  # Will be populated during OBSERVE
        )
        session = self.session_memory.create_session(goal, str(target))
        logger.info(f"Session {session.session_id}: {request}")

        max_iterations = self.config.agent.max_iterations
        max_retries = self.config.agent.max_retries
        iteration = 0

        while not self._should_terminate(session, iteration, max_iterations):
            iteration += 1
            logger.info(f"\n{'='*60}")
            logger.info(f"ITERATION {iteration}/{max_iterations}")
            logger.info(f"{'='*60}")

            try:
                result = self._run_iteration(
                    session, iteration, request, str(target), start_time
                )
                if result is not None:
                    # Iteration produced a final result
                    return result
            except Exception as e:
                logger.error(f"Iteration {iteration} failed: {e}", exc_info=True)
                session.retry_count += 1
                if session.retry_count >= max_retries:
                    return self.updater.finalize_failure(
                        session, f"Max retries exceeded: {e}", start_time
                    )

        # Timeout
        session.status = SessionStatus.TIMEOUT
        return self.updater.finalize_failure(
            session, f"Max iterations ({max_iterations}) reached", start_time
        )

    def _run_iteration(
        self,
        session: SessionState,
        iteration: int,
        request: str,
        target_path: str,
        start_time: float,
    ) -> dict | None:
        """Run one complete iteration of the 7-phase loop. Returns result dict or None to continue."""

        # ---- 1. OBSERVE ----
        session.current_phase = AgentPhase.OBSERVE
        observation = self.observer.observe(session.session_id, target_path)
        if not observation.complete:
            logger.warning("Observation incomplete - skipping iteration")
            return None

        # ---- 2. REASON ----
        session.current_phase = AgentPhase.REASON
        analysis = self.reasoner.reason(observation, request)
        if not analysis.approach:
            logger.warning("Reasoning produced no approach - skipping iteration")
            return None

        # ---- 3. PLAN ----
        session.current_phase = AgentPhase.PLAN
        plan = self.planner.plan(analysis, observation)
        if not plan.steps:
            logger.warning("Planning produced no steps - skipping iteration")
            return None

        # ---- 4. DECIDE ----
        session.current_phase = AgentPhase.DECIDE
        test_coverage = 0.0
        if observation.existing_test_results and observation.existing_test_results.coverage:
            test_coverage = observation.existing_test_results.coverage.overall_percentage

        decision = self.arbiter.decide(plan, analysis, test_coverage)

        if decision.requires_human:
            session.status = SessionStatus.AWAITING_APPROVAL
            self.session_memory.update_session(session)
            logger.info("DECIDE: Requires human approval - pausing")
            return {
                "status": "awaiting_approval",
                "session_id": session.session_id,
                "risk_score": decision.risk_score.total_score,
                "reason": decision.reason,
                "plan_steps": len(plan.steps),
                "files_affected": len(analysis.files_to_modify),
            }

        if not decision.approved:
            return self.updater.finalize_failure(
                session, f"Decision not approved: {decision.reason}", start_time
            )

        # ---- 5. ACT ----
        session.current_phase = AgentPhase.ACT
        step_results = self.executor.execute(plan, decision.tool_mapping, target_path)

        # Check for critical failures
        critical = [r for r in step_results if r.get("critical")]
        if critical:
            logger.error("Critical failure during execution")
            # Rollback: git reset
            self.git_ops.execute(
                operation="reset",
                repository_path=target_path,
                parameters={"target": "HEAD", "mode": "hard"},
            )
            return self.updater.finalize_failure(
                session,
                f"Critical failure in step {critical[0]['step_id']}: {critical[0].get('error')}",
                start_time,
            )

        # ---- 6. VERIFY ----
        session.current_phase = AgentPhase.VERIFY
        report = self.verifier.verify(
            step_results, decision.validation_level,
            target_path, observation.file_metrics,
        )

        # ---- 7. UPDATE ----
        session.current_phase = AgentPhase.UPDATE
        self.updater.update(
            session, iteration, observation, analysis,
            plan, decision, step_results, report,
        )

        if report.tests_passed and report.improved:
            # Success!
            return self.updater.finalize_success(session, report, start_time)

        elif not report.tests_passed:
            logger.warning("Tests failed after refactoring")
            # Rollback and retry
            self.git_ops.execute(
                operation="reset",
                repository_path=target_path,
                parameters={"target": "HEAD", "mode": "hard"},
            )
            session.retry_count += 1
            if session.retry_count >= self.config.agent.max_retries:
                return self.updater.finalize_failure(
                    session, "Tests failed after max retries", start_time
                )
            logger.info(f"Retry {session.retry_count}/{self.config.agent.max_retries}")
            return None  # Continue to next iteration

        elif not report.improved:
            logger.warning("Metrics did not improve - attempting different approach")
            return None  # Continue to next iteration

        return None

    def _should_terminate(
        self, session: SessionState, iteration: int, max_iterations: int
    ) -> bool:
        if session.status in (
            SessionStatus.COMPLETED,
            SessionStatus.FAILED,
            SessionStatus.REJECTED,
            SessionStatus.AWAITING_APPROVAL,
        ):
            return True
        if iteration >= max_iterations:
            return True
        return False

    def close(self) -> None:
        """Clean up resources."""
        self.history.close()
        self.graph.close()
