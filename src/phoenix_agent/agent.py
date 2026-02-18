"""Phoenix Agent - main 7-phase control loop.

Implements the closed-loop architecture:
OBSERVE → REASON → PLAN → DECIDE → ACT → VERIFY → UPDATE

Now delegates to a crew-style multi-agent system (LeadAgent) for parallel
execution of independent coding tasks.
"""

from __future__ import annotations

import difflib
import logging
import time
from pathlib import Path
from typing import Any, Callable, Optional

from phoenix_agent.api import agent_registry
from phoenix_agent.config import PhoenixConfig
from phoenix_agent.crew.lead_agent import LeadAgent
from phoenix_agent.input_resolver import apply_staged_changes, get_resolved
from phoenix_agent.provider import create_llm
from phoenix_agent.memory.history import RefactoringHistory
from phoenix_agent.memory.knowledge_graph import CodebaseGraph
from phoenix_agent.memory.session import SessionMemory
from phoenix_agent.models import (
    AgentPhase,
    Decision,
    FileDiff,
    RefactoringGoal,
    RefactoringPlan,
    ReviewPayload,
    SessionState,
    SessionStatus,
    VerificationReport,
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
from phoenix_agent.tools.test_generator import TestGeneratorTool
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
        self.test_generator = TestGeneratorTool(self.config)

        self.tool_registry = ToolRegistry()
        self.tool_registry.register(self.ast_parser)
        self.tool_registry.register(self.test_runner)
        self.tool_registry.register(self.git_ops)
        self.tool_registry.register(self.test_generator)

        # Memory
        self.session_memory = SessionMemory(self.config)
        self.history = RefactoringHistory(self.config)
        self.graph = CodebaseGraph(self.config)

        # Orchestrator modules (still used by LeadAgent sub-agents)
        self.observer = Observer(self.ast_parser, self.session_memory)
        self.reasoner = Reasoner(self.llm)
        self.planner = Planner(self.llm)
        self.arbiter = Arbiter(self.config)
        self.executor = Executor(self.config, self.tool_registry, self.llm)
        self.verifier = Verifier(self.ast_parser, self.test_runner)
        self.updater = Updater(
            self.config,
            self.session_memory, self.history, self.graph,
            self.git_ops, self.ast_parser,
        )

        # Crew-style LeadAgent
        self.lead_agent = LeadAgent(
            config=self.config,
            observer=self.observer,
            reasoner=self.reasoner,
            planner=self.planner,
            arbiter=self.arbiter,
            verifier=self.verifier,
            tool_registry=self.tool_registry,
            ast_parser=self.ast_parser,
            llm=self.llm,
        )

        logger.info("Phoenix Agent initialized (crew mode)")

    def run(
        self,
        request: str,
        target_path: str,
        on_phase: Optional[Callable[..., Any]] = None,
        session_id: Optional[str] = None,
    ) -> dict:
        """
        Main entry point. Runs the full refactoring loop.

        Args:
            request: Developer's refactoring request
            target_path: Path to the project/directory to refactor
            on_phase: Optional callback for streaming progress.
            session_id: Optional existing session ID to resume.

        Returns:
            dict with status, session_id, and details
        """
        target = Path(target_path).resolve()
        if not target.exists():
            return {"status": "failed", "reason": f"Target path not found: {target_path}"}

        self._emit = on_phase or (lambda *a, **kw: None)
        self.lead_agent.set_emit(self._emit)
        start_time = time.time()

        if session_id:
            session = self.session_memory.get_session(session_id)
            if not session:
                return {"status": "failed", "reason": f"Session not found: {session_id}"}
        else:
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
            self._emit("iteration_start", iteration=iteration, data={"max": max_iterations})

            try:
                result = self._run_iteration(
                    session, iteration, request, str(target), start_time
                )
                if result is not None:
                    logger.info(f"Emitting completed event (status={result.get('status')})")
                    self._emit("completed", data=result, iteration=iteration)
                    logger.info("Agent run complete — returning")
                    return result
            except Exception as e:
                logger.error(f"Iteration {iteration} failed: {e}", exc_info=True)
                self._emit("error", message=str(e), iteration=iteration)
                session.retry_count += 1
                if session.retry_count >= max_retries:
                    result = self.updater.finalize_failure(
                        session, f"Max retries exceeded: {e}", start_time
                    )
                    self._emit("completed", data=result, iteration=iteration)
                    return result

        # Timeout
        session.status = SessionStatus.TIMEOUT
        result = self.updater.finalize_failure(
            session, f"Max iterations ({max_iterations}) reached", start_time
        )
        self._emit("completed", data=result, iteration=iteration)
        return result

    def _run_iteration(
        self,
        session: SessionState,
        iteration: int,
        request: str,
        target_path: str,
        start_time: float,
    ) -> dict | None:
        """Run one complete iteration using the crew-style multi-agent system."""

        emit = self._emit

        # ---- 1 & 2. ANALYZE + STRATEGIZE (via LeadAgent) ----
        session.current_phase = AgentPhase.OBSERVE
        (
            observation, analysis, plan, decision, _, _
        ) = self.lead_agent.run_iteration(session, iteration, request, target_path)

        if observation is None:
            logger.warning("Analysis failed - skipping iteration")
            return None

        session.current_phase = AgentPhase.REASON
        if analysis is None or not analysis.approach:
            logger.warning("Reasoning produced no approach - skipping iteration")
            return None

        session.current_phase = AgentPhase.PLAN
        session.last_test_failure = None  # Clear after use by planner
        if plan is None or not plan.steps:
            logger.warning("Planning produced no steps - skipping iteration")
            return None

        session.current_phase = AgentPhase.DECIDE
        if decision is None:
            return None

        # ---- 3. HUMAN APPROVAL GATE (stays in PhoenixAgent) ----
        if decision.requires_human and iteration == 1:
            session.status = SessionStatus.AWAITING_APPROVAL
            self.session_memory.update_session(session)
            logger.info("DECIDE: High risk — waiting for human approval")

            emit("approval_requested", data={
                "risk_score": decision.risk_score.total_score,
                "reason": decision.reason,
                "plan_steps": len(plan.steps),
                "files_affected": len(analysis.files_to_modify),
            }, iteration=iteration)

            pubsub = agent_registry.register_review(session.session_id)
            verdict = None
            try:
                verdict = agent_registry.await_verdict(
                    pubsub, timeout=self.config.agent.review_timeout
                )
            finally:
                agent_registry.cleanup(pubsub)

            if not verdict or not verdict.approved:
                reason = "Approval timed out" if not verdict else "Rejected by user"
                if verdict and verdict.comment:
                    reason += f": {verdict.comment}"
                logger.info(f"Approval result: {reason}")
                session.status = SessionStatus.REJECTED
                self.session_memory.update_session(session)
                return self.updater.finalize_failure(session, reason, start_time)

            logger.info("Plan approved by user — proceeding to ACT")
            decision.approved = True
            session.status = SessionStatus.ACTIVE
            self.session_memory.update_session(session)

        if decision.requires_human and iteration > 1:
            logger.info(f"DECIDE: Auto-approving retry iteration {iteration}")
            decision.approved = True

        if not decision.approved:
            return self.updater.finalize_failure(
                session, f"Decision not approved: {decision.reason}", start_time
            )

        # ---- 4. ACT (parallel CoderAgents via LeadAgent) ----
        session.current_phase = AgentPhase.ACT
        step_results = self.lead_agent.execute_coding_tasks(plan, target_path, iteration)

        # Check for critical failures — rollback and retry instead of hard-fail
        critical = [r for r in step_results if r.get("critical")]
        if critical:
            logger.error(f"Critical failure in step {critical[0]['step_id']} — rolling back to retry")
            self.git_ops.execute(
                operation="reset",
                repository_path=target_path,
                parameters={"target": "HEAD", "mode": "hard"},
            )
            session.retry_count += 1
            if session.retry_count >= self.config.agent.max_retries:
                return self.updater.finalize_failure(
                    session,
                    f"Critical failure in step {critical[0]['step_id']}: {critical[0].get('error')}",
                    start_time,
                )
            logger.info(f"Retry {session.retry_count}/{self.config.agent.max_retries}")
            return None  # Continue to next iteration

        # ---- 5. VERIFY (via LeadAgent → TesterAgent) ----
        session.current_phase = AgentPhase.VERIFY
        report = self.lead_agent.run_verification(
            step_results, decision, target_path, observation.file_metrics, iteration,
        )

        # ---- 6. UPDATE ----
        session.current_phase = AgentPhase.UPDATE
        self.updater.update(
            session, iteration, observation, analysis,
            plan, decision, step_results, report,
        )
        emit("phase_update", phase="UPDATE", iteration=iteration)

        if report.tests_passed and report.improved:
            # Build diff review and wait for user approval
            review = self._build_review_payload(
                session, step_results, report, plan, decision,
            )
            self.session_memory.store_review(session.session_id, review)

            session.status = SessionStatus.AWAITING_REVIEW
            self.session_memory.update_session(session)
            emit("review_requested", data=review, iteration=iteration)

            # Block thread until user approves or rejects
            pubsub = agent_registry.register_review(session.session_id)
            logger.info("Waiting for user review approval...")
            verdict = None
            try:
                verdict = agent_registry.await_verdict(
                    pubsub, timeout=self.config.agent.review_timeout
                )
            finally:
                agent_registry.cleanup(pubsub)

            if not verdict or not verdict.approved:
                reason = "Review timed out" if not verdict else "Rejected by reviewer"
                if verdict and verdict.comment:
                    reason += f": {verdict.comment}"
                logger.info(f"Review result: {reason}")
                self.git_ops.execute(
                    operation="reset",
                    repository_path=target_path,
                    parameters={"target": "HEAD", "mode": "hard"},
                )
                session.status = SessionStatus.REJECTED
                self.session_memory.update_session(session)
                return self.updater.finalize_failure(session, reason, start_time)

            logger.info("Review approved — applying staged changes")

            # Copy changed files from staging dir back to the original project
            # (only for local_path — pasted code has no real original directory)
            resolved = get_resolved(session.session_id)
            if resolved and resolved.is_temporary and resolved.original_source:
                from phoenix_agent.input_resolver import InputType
                if resolved.input_type == InputType.LOCAL_PATH:
                    changed_files = [
                        r["target_file"]
                        for r in step_results
                        if r.get("action") == "modify_code" and r.get("success")
                    ]
                    applied = apply_staged_changes(resolved, changed_files)
                    logger.info(f"Applied {len(applied)} files to {resolved.original_source}")
                else:
                    logger.info(f"Pasted code — skipping apply (files returned via API)")

            session.status = SessionStatus.ACTIVE
            logger.info("Calling finalize_success...")
            result = self.updater.finalize_success(session, report, start_time, step_results)
            logger.info("finalize_success complete — returning result")
            return result

        elif not report.tests_passed:
            logger.warning("Tests failed after refactoring")
            session.last_test_failure = report.test_result
            # Pass failure details to LeadAgent for next iteration
            if report.test_result and report.test_result.failures:
                self.lead_agent.set_test_failures([
                    {"test_name": f.test_name, "test_file": f.test_file, "error_message": f.error_message}
                    for f in report.test_result.failures
                ])
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
            SessionStatus.AWAITING_REVIEW,
        ):
            return True
        if iteration >= max_iterations:
            return True
        return False

    def _build_review_payload(
        self,
        session: SessionState,
        step_results: list[dict],
        report: VerificationReport,
        plan: RefactoringPlan,
        decision: Decision,
    ) -> ReviewPayload:
        """Build the diff review package from execution results."""
        file_diffs: list[FileDiff] = []

        for result in step_results:
            if result.get("action") != "modify_code" or not result.get("success"):
                continue

            file_path = result["target_file"]
            original = (result.get("metadata") or {}).get("original_content", "")
            target = Path(file_path)
            modified = target.read_text() if target.exists() else ""

            rel_path = file_path
            try:
                rel_path = str(Path(file_path).relative_to(session.target_path))
            except ValueError:
                pass

            diff_lines = list(difflib.unified_diff(
                original.splitlines(keepends=True),
                modified.splitlines(keepends=True),
                fromfile=f"a/{rel_path}",
                tofile=f"b/{rel_path}",
            ))
            unified = "".join(diff_lines)

            added = sum(1 for l in diff_lines if l.startswith("+") and not l.startswith("+++"))
            removed = sum(1 for l in diff_lines if l.startswith("-") and not l.startswith("---"))

            file_diffs.append(FileDiff(
                file_path=file_path,
                relative_path=rel_path,
                original_content=original,
                modified_content=modified,
                unified_diff=unified,
                lines_added=added,
                lines_removed=removed,
            ))

        plan_summary = "; ".join(
            s.description for s in plan.steps if s.action == "modify_code"
        )

        return ReviewPayload(
            session_id=session.session_id,
            files=file_diffs,
            test_result=report.test_result,
            coverage_pct=report.coverage_pct,
            complexity_before=report.complexity_before,
            complexity_after=report.complexity_after,
            risk_score=decision.risk_score.total_score,
            plan_summary=plan_summary,
        )

    def close(self) -> None:
        """Clean up resources."""
        self.history.close()
        self.graph.close()
