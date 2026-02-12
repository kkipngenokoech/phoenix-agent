"""Tool 3: Git Operations Manager - version control operations for refactoring."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Optional

from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError

from phoenix_agent.models import GitOperation, GitOperationResult
from phoenix_agent.tools.base import BaseTool, ToolCategory, ToolResult

logger = logging.getLogger(__name__)


class GitOperationsTool(BaseTool):
    name = "git_ops"
    description = "Perform Git operations: create branches, commit, create PRs, diff."
    category = ToolCategory.VCS
    parameters_schema = {
        "required": ["operation", "repository_path"],
        "properties": {
            "operation": {"type": "string"},
            "repository_path": {"type": "string"},
            "parameters": {"type": "object", "default": {}},
        },
    }

    def execute(
        self,
        operation: str,
        repository_path: str,
        parameters: Optional[dict] = None,
        **kwargs,
    ) -> ToolResult:
        parameters = parameters or {}
        repo_path = Path(repository_path)

        try:
            repo = Repo(str(repo_path))
        except InvalidGitRepositoryError:
            return ToolResult(
                success=False,
                error=f"Not a git repository: {repository_path}",
            )

        op = GitOperation(operation)
        handler = {
            GitOperation.CREATE_BRANCH: self._create_branch,
            GitOperation.COMMIT: self._commit,
            GitOperation.CREATE_PR: self._create_pr,
            GitOperation.DIFF: self._diff,
            GitOperation.RESET: self._reset,
        }.get(op)

        if not handler:
            return ToolResult(success=False, error=f"Unsupported operation: {operation}")

        try:
            result = handler(repo, parameters)
            return ToolResult(
                success=result.status == "success",
                output=result.model_dump(),
                error=result.error.get("message") if result.error else None,
            )
        except Exception as e:
            logger.error(f"Git operation failed: {e}")
            return ToolResult(success=False, error=str(e))

    # ------------------------------------------------------------------
    # Operations
    # ------------------------------------------------------------------

    def _create_branch(self, repo: Repo, params: dict) -> GitOperationResult:
        branch_name = params.get("branch_name", "")
        base_branch = params.get("base_branch", "main")

        if not branch_name:
            return GitOperationResult(
                status="failed",
                operation="create_branch",
                error={"code": "missing_param", "message": "branch_name required"},
            )

        # Check if branch already exists
        if branch_name in [b.name for b in repo.branches]:
            # Switch to existing branch
            repo.git.checkout(branch_name)
            return GitOperationResult(
                status="success",
                operation="create_branch",
                result={
                    "branch_name": branch_name,
                    "commit_hash": repo.head.commit.hexsha,
                    "note": "Branch already existed, switched to it",
                },
            )

        # Create and checkout new branch
        try:
            base = repo.branches[base_branch] if base_branch in [b.name for b in repo.branches] else repo.head
            repo.git.checkout("-b", branch_name, str(base))
        except GitCommandError as e:
            return GitOperationResult(
                status="failed",
                operation="create_branch",
                error={"code": "git_error", "message": str(e)},
            )

        return GitOperationResult(
            status="success",
            operation="create_branch",
            result={
                "branch_name": branch_name,
                "commit_hash": repo.head.commit.hexsha,
            },
        )

    def _commit(self, repo: Repo, params: dict) -> GitOperationResult:
        files = params.get("files", [])
        message = params.get("commit_message", "Phoenix refactoring")
        author_info = params.get("author", {})

        if not files:
            # Check if there are staged or unstaged changes
            if not repo.is_dirty(untracked_files=True):
                return GitOperationResult(
                    status="failed",
                    operation="commit",
                    error={"code": "nothing_to_commit", "message": "No changes to commit"},
                )
            # Stage all modified files
            repo.git.add("-A")
        else:
            for f in files:
                repo.git.add(f)

        try:
            commit = repo.index.commit(message)
        except Exception as e:
            return GitOperationResult(
                status="failed",
                operation="commit",
                error={"code": "commit_failed", "message": str(e)},
            )

        stats = commit.stats.total
        return GitOperationResult(
            status="success",
            operation="commit",
            result={
                "commit_hash": commit.hexsha,
                "files_changed": stats.get("files", 0),
                "insertions": stats.get("insertions", 0),
                "deletions": stats.get("deletions", 0),
            },
        )

    def _create_pr(self, repo: Repo, params: dict) -> GitOperationResult:
        title = params.get("title", "Phoenix Refactoring")
        description = params.get("description", "")
        source_branch = params.get("source_branch", repo.active_branch.name)
        target_branch = params.get("target_branch", "main")
        labels = params.get("labels", [])

        # Skip entirely if no remote configured (e.g. pasted code temp repos)
        if not repo.remotes:
            return GitOperationResult(
                status="failed",
                operation="create_pr",
                error={"code": "no_remote", "message": "No git remote configured — skipping push and PR"},
            )

        # Push the branch first
        try:
            repo.git.push("--set-upstream", "origin", source_branch)
        except GitCommandError as e:
            logger.warning(f"Push failed (may not have remote): {e}")

        # Create PR via gh CLI
        cmd = [
            "gh", "pr", "create",
            "--title", title,
            "--body", description,
            "--base", target_branch,
            "--head", source_branch,
        ]
        for label in labels:
            cmd.extend(["--label", label])

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=str(repo.working_dir))
            if proc.returncode == 0:
                pr_url = proc.stdout.strip()
                return GitOperationResult(
                    status="success",
                    operation="create_pr",
                    result={
                        "pr_url": pr_url,
                        "pr_number": self._extract_pr_number(pr_url),
                    },
                )
            else:
                return GitOperationResult(
                    status="failed",
                    operation="create_pr",
                    error={"code": "pr_creation_failed", "message": proc.stderr.strip()},
                )
        except FileNotFoundError:
            return GitOperationResult(
                status="failed",
                operation="create_pr",
                error={"code": "gh_not_found", "message": "GitHub CLI (gh) not installed"},
            )
        except subprocess.TimeoutExpired:
            return GitOperationResult(
                status="failed",
                operation="create_pr",
                error={"code": "timeout", "message": "PR creation timed out"},
            )

    def _diff(self, repo: Repo, params: dict) -> GitOperationResult:
        target = params.get("target_branch", "main")
        try:
            diff_output = repo.git.diff(target, "--stat")
            full_diff = repo.git.diff(target)
            return GitOperationResult(
                status="success",
                operation="diff",
                result={
                    "stat": diff_output,
                    "full_diff": full_diff[:10000],  # Limit size
                    "files_changed": len(diff_output.splitlines()) - 1 if diff_output else 0,
                },
            )
        except GitCommandError as e:
            return GitOperationResult(
                status="failed",
                operation="diff",
                error={"code": "diff_failed", "message": str(e)},
            )

    def _reset(self, repo: Repo, params: dict) -> GitOperationResult:
        target = params.get("target", "HEAD")
        mode = params.get("mode", "hard")
        try:
            repo.git.reset(f"--{mode}", target)
            return GitOperationResult(
                status="success",
                operation="reset",
                result={"target": target, "mode": mode, "commit_hash": repo.head.commit.hexsha},
            )
        except GitCommandError as e:
            return GitOperationResult(
                status="failed",
                operation="reset",
                error={"code": "reset_failed", "message": str(e)},
            )

    @staticmethod
    def _extract_pr_number(url: str) -> int:
        try:
            return int(url.rstrip("/").split("/")[-1])
        except (ValueError, IndexError):
            return 0
