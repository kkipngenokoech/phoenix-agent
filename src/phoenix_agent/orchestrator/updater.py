"""UPDATE phase - write results to memory, create branches/PRs on success."""

from __future__ import annotations

import logging
import time
from datetime import datetime

from phoenix_agent.config import PhoenixConfig
from phoenix_agent.models import (
    AgentPhase,
    ASTAnalysisResult,
    IterationData,
    ObservationResult,
    ReasoningAnalysis,
    RefactoringPlan,
    RefactoringRecord,
    SessionState,
    SessionStatus,
    VerificationReport,
    Decision,
)
from phoenix_agent.memory.session import SessionMemory
from phoenix_agent.memory.history import RefactoringHistory
from phoenix_agent.memory.knowledge_graph import CodebaseGraph
from phoenix_agent.tools.git_ops import GitOperationsTool
from phoenix_agent.tools.ast_parser import ASTParserTool

logger = logging.getLogger(__name__)


class Updater:
    def __init__(
        self,
        config: PhoenixConfig,
        session_memory: SessionMemory,
        history: RefactoringHistory,
        graph: CodebaseGraph,
        git_ops: GitOperationsTool,
        ast_parser: ASTParserTool,
    ) -> None:
        self.config = config
        self._session = session_memory
        self._history = history
        self._graph = graph
        self._git_ops = git_ops
        self._ast_parser = ast_parser

    def update(
        self,
        session: SessionState,
        iteration: int,
        observation: ObservationResult,
        analysis: ReasoningAnalysis,
        plan: RefactoringPlan,
        decision: Decision,
        step_results: list[dict],
        report: VerificationReport,
    ) -> None:
        """Write all phase data to short-term memory (Redis)."""
        logger.info(f"UPDATE: writing iteration {iteration} to memory")

        iter_data = IterationData(
            iteration=iteration,
            phase=AgentPhase.UPDATE,
            observation=observation.model_dump(),
            reasoning=analysis.model_dump(),
            plan=plan.model_dump(),
            decision=decision.model_dump(),
            tool_results=step_results,
            verification=report.model_dump(),
        )
        self._session.write_iteration(session.session_id, iter_data)

        # Update session state
        session.iteration_count = iteration
        session.current_phase = AgentPhase.UPDATE
        self._session.update_session(session)

    def finalize_success(
        self,
        session: SessionState,
        report: VerificationReport,
        start_time: float,
        step_results: list[dict] | None = None,
    ) -> dict:
        """On success: create branch, commit, PR, write to long-term memory."""
        logger.info("UPDATE: finalizing successful refactoring")

        repo_path = session.target_path
        branch_name = f"phoenix/refactor-{session.session_id}"

        if not self.config.agent.skip_git_operations:
            # 1. Create branch
            try:
                branch_result = self._git_ops.execute(
                    operation="create_branch",
                    repository_path=repo_path,
                    parameters={"branch_name": branch_name, "base_branch": "main"},
                )
                if branch_result.success:
                    session.branch_name = branch_name
                logger.info(f"UPDATE: branch create → {branch_result.success}")
            except Exception as e:
                logger.warning(f"UPDATE: branch creation failed: {e}")

            # 2. Commit changes
            try:
                commit_msg = (
                    f"refactor: {session.goal.description}\n\n"
                    f"Session: {session.session_id}\n"
                    f"Complexity: {report.complexity_before} → {report.complexity_after}\n"
                    f"Tests: {'passing' if report.tests_passed else 'failing'}"
                )
                commit_result = self._git_ops.execute(
                    operation="commit",
                    repository_path=repo_path,
                    parameters={"commit_message": commit_msg},
                )
                logger.info(f"UPDATE: commit → {commit_result.success}")
            except Exception as e:
                logger.warning(f"UPDATE: commit failed: {e}")

            # 3. Create PR (skipped automatically for repos without a remote)
            try:
                pr_description = self._build_pr_description(session, report)
                pr_result = self._git_ops.execute(
                    operation="create_pr",
                    repository_path=repo_path,
                    parameters={
                        "title": f"Refactor: {session.goal.description[:60]}",
                        "description": pr_description,
                        "source_branch": branch_name,
                        "target_branch": "main",
                        "labels": ["refactoring", "phoenix-agent"],
                    },
                )
                if pr_result.success and pr_result.output:
                    session.pr_url = pr_result.output.get("result", {}).get("pr_url")
                logger.info(f"UPDATE: PR create → {pr_result.success} (url={session.pr_url})")
            except Exception as e:
                logger.warning(f"UPDATE: PR creation failed: {e}")
        else:
            logger.info("UPDATE: skipping git operations as configured")

        # 4. Write to long-term memory (PostgreSQL)
        duration = time.time() - start_time

        # Read refactored files so the frontend can display them
        refactored_files = self._read_refactored_files(
            repo_path, list(report.complexity_after.keys())
        )

        # Extract original file contents from step_results metadata
        original_files: dict[str, str] = {}
        if step_results:
            for r in step_results:
                if r.get("action") == "modify_code" and r.get("success"):
                    orig = (r.get("metadata") or {}).get("original_content", "")
                    if orig:
                        file_path = r["target_file"]
                        try:
                            from pathlib import Path
                            rel = str(Path(file_path).relative_to(repo_path))
                        except (ValueError, TypeError):
                            rel = file_path.split("/")[-1] if "/" in file_path else file_path
                        original_files[rel] = orig

        try:
            record = RefactoringRecord(
                session_id=session.session_id,
                files_modified=list(report.complexity_after.keys()),
                risk_score=0.0,
                metrics_before=report.complexity_before,
                metrics_after=report.complexity_after,
                pr_url=session.pr_url,
                outcome="success",
                duration_seconds=duration,
                original_files=original_files,
                refactored_files=refactored_files,
            )
            self._history.record_refactoring(record)
            logger.info("UPDATE: history record written")
        except Exception as e:
            logger.warning(f"UPDATE: history write failed: {e}")

        # 5. Update knowledge graph (Neo4j)
        try:
            modified_files = list(report.complexity_after.keys())
            if modified_files:
                ast_result = self._ast_parser.execute(file_paths=modified_files)
                if ast_result.success:
                    analysis = ASTAnalysisResult.model_validate(ast_result.output)
                    self._graph.update_from_analysis(analysis)
            logger.info("UPDATE: knowledge graph updated")
        except Exception as e:
            logger.warning(f"UPDATE: knowledge graph update failed: {e}")

        # 6. Update session status
        session.status = SessionStatus.COMPLETED
        self._session.update_session(session)

        logger.info(f"UPDATE: refactoring complete. PR: {session.pr_url}")

        return {
            "status": "success",
            "session_id": session.session_id,
            "branch": branch_name,
            "pr_url": session.pr_url,
            "duration_seconds": duration,
            "metrics_before": report.complexity_before,
            "metrics_after": report.complexity_after,
            "original_files": original_files,
            "refactored_files": refactored_files,
        }

    def finalize_failure(
        self,
        session: SessionState,
        reason: str,
        start_time: float,
    ) -> dict:
        """On failure: record outcome, update session."""
        logger.info(f"UPDATE: recording failure - {reason}")

        duration = time.time() - start_time
        record = RefactoringRecord(
            session_id=session.session_id,
            outcome="failed",
            duration_seconds=duration,
        )
        self._history.record_refactoring(record)

        session.status = SessionStatus.FAILED
        session.error_message = reason
        self._session.update_session(session)

        return {
            "status": "failed",
            "session_id": session.session_id,
            "reason": reason,
            "duration_seconds": duration,
        }

    def _build_pr_description(self, session: SessionState, report: VerificationReport) -> str:
        lines = [
            "## Phoenix Automated Refactoring",
            "",
            f"**Goal:** {session.goal.description}",
            "",
            "### Metrics",
            "| File | Before | After | Change |",
            "|------|--------|-------|--------|",
        ]

        all_files = set(report.complexity_before.keys()) | set(report.complexity_after.keys())
        for f in sorted(all_files):
            before = report.complexity_before.get(f, 0)
            after = report.complexity_after.get(f, 0)
            delta = after - before
            sign = "+" if delta > 0 else ""
            short_name = f.split("/")[-1]
            lines.append(f"| {short_name} | {before} | {after} | {sign}{delta} |")

        lines.extend([
            "",
            f"### Test Results",
            f"- Status: {'PASSED' if report.tests_passed else 'FAILED'}",
            f"- Coverage: {report.coverage_pct:.1f}%",
            "",
            f"---",
            f"*Generated by Phoenix Agent (session: {session.session_id})*",
        ])

        return "\n".join(lines)

    @staticmethod
    def _read_refactored_files(repo_path: str, modified_files: list[str]) -> dict[str, str]:
        """Read specified files from the target directory for the result payload."""
        from pathlib import Path

        files: dict[str, str] = {}
        root = Path(repo_path)
        for file_path in modified_files:
            try:
                p = Path(file_path)
                # Ensure the path is within the project root for security
                if not p.is_absolute():
                    p = root / p
                
                # Check if file exists before reading
                if p.exists() and p.is_relative_to(root):
                    rel = str(p.relative_to(root))
                    content = p.read_text()
                    files[rel] = content
            except Exception:
                pass
        return files
