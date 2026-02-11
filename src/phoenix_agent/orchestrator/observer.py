"""OBSERVE phase - gather codebase state, metrics, and session context."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from git import Repo
from git.exc import InvalidGitRepositoryError

from phoenix_agent.models import (
    CodebaseSnapshot,
    FileMetrics,
    ObservationResult,
)
from phoenix_agent.tools.ast_parser import ASTParserTool
from phoenix_agent.memory.session import SessionMemory

logger = logging.getLogger(__name__)


class Observer:
    def __init__(self, ast_parser: ASTParserTool, session_memory: SessionMemory) -> None:
        self._ast_parser = ast_parser
        self._session = session_memory

    def observe(self, session_id: str, target_path: str) -> ObservationResult:
        logger.info(f"OBSERVE: gathering state for {target_path}")

        snapshot = self._gather_snapshot(target_path)
        python_files = self._find_python_files(target_path)
        file_metrics = self._gather_metrics(python_files)

        # Fetch session context from previous iterations
        session_context = {}
        iterations = self._session.get_all_iterations(session_id)
        if iterations:
            last = iterations[-1]
            session_context = {
                "previous_iteration": last.iteration,
                "previous_phase": last.phase.value if last.phase else None,
                "has_previous_results": bool(last.tool_results),
            }

        result = ObservationResult(
            snapshot=snapshot,
            file_metrics=file_metrics,
            session_context=session_context,
        )

        logger.info(
            f"OBSERVE complete: {len(python_files)} files, "
            f"branch={snapshot.current_branch}"
        )
        return result

    def _gather_snapshot(self, target_path: str) -> CodebaseSnapshot:
        snapshot = CodebaseSnapshot()
        try:
            # Walk up to find the git repo root
            repo = Repo(target_path, search_parent_directories=True)
            snapshot.current_branch = repo.active_branch.name
            snapshot.commit_hash = repo.head.commit.hexsha
            snapshot.has_uncommitted_changes = repo.is_dirty(untracked_files=True)
            snapshot.git_status = repo.git.status("--short")
        except (InvalidGitRepositoryError, Exception) as e:
            logger.warning(f"Git info unavailable: {e}")

        snapshot.files = self._find_python_files(target_path)
        return snapshot

    def _find_python_files(self, target_path: str) -> list[str]:
        """Find all Python source files in the target, excluding tests and __pycache__."""
        path = Path(target_path)
        files = []
        for py_file in path.rglob("*.py"):
            rel = str(py_file)
            if "__pycache__" in rel or ".git" in rel:
                continue
            files.append(str(py_file))
        return sorted(files)

    def _gather_metrics(self, file_paths: list[str]) -> list[FileMetrics]:
        """Run AST parser on source files to collect metrics."""
        # Filter to non-test source files
        source_files = [f for f in file_paths if "/tests/" not in f and "test_" not in os.path.basename(f)]
        if not source_files:
            return []

        result = self._ast_parser.execute(file_paths=source_files)
        if not result.success:
            logger.warning(f"AST analysis failed: {result.error}")
            return []

        metrics = []
        for pf in result.output.get("parsed_files", []):
            m = pf.get("metrics", {})
            metrics.append(FileMetrics(
                file_path=pf["file_path"],
                lines_of_code=m.get("lines_of_code", 0),
                cyclomatic_complexity=m.get("cyclomatic_complexity", 0),
                function_count=m.get("function_count", 0),
                class_count=m.get("class_count", 0),
                max_nesting_depth=m.get("max_nesting_depth", 0),
            ))
        return metrics
