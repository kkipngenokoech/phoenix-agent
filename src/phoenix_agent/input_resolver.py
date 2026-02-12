"""Input resolver — normalize any input source to a local directory path."""

from __future__ import annotations

import enum
import logging
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class InputType(str, enum.Enum):
    LOCAL_PATH = "local_path"
    PASTED_CODE = "pasted_code"
    GITHUB_URL = "github_url"


class InputResolutionError(Exception):
    """Raised when input cannot be resolved to a valid local directory."""


class ResolvedInput:
    """Result of resolving an input source to a local directory."""

    def __init__(
        self,
        resolved_path: str,
        input_type: InputType,
        is_temporary: bool,
        original_source: str,
        temp_dir: Optional[str] = None,
    ):
        self.resolved_path = resolved_path
        self.input_type = input_type
        self.is_temporary = is_temporary
        self.original_source = original_source
        self.temp_dir = temp_dir

    def cleanup(self) -> None:
        """Remove temporary directory if this was a temp input."""
        if self.is_temporary and self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)
            logger.info(f"Cleaned up temp dir: {self.temp_dir}")


# ---------------------------------------------------------------------------
# Session registry for tracking temp dirs
# ---------------------------------------------------------------------------

_active_temps: dict[str, ResolvedInput] = {}


def register_temp(session_id: str, resolved: ResolvedInput) -> None:
    _active_temps[session_id] = resolved


def cleanup_session(session_id: str) -> None:
    resolved = _active_temps.pop(session_id, None)
    if resolved:
        resolved.cleanup()


# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------


def resolve_input(
    input_type: str,
    target_path: Optional[str] = None,
    pasted_code: Optional[str] = None,
    pasted_files: Optional[dict[str, str]] = None,
    github_url: Optional[str] = None,
) -> ResolvedInput:
    """Normalize any input source to a ResolvedInput with a local directory path."""
    it = InputType(input_type)

    if it == InputType.LOCAL_PATH:
        return _resolve_local_path(target_path)
    elif it == InputType.PASTED_CODE:
        return _resolve_pasted_code(pasted_code, pasted_files)
    elif it == InputType.GITHUB_URL:
        return _resolve_github_url(github_url)
    else:
        raise InputResolutionError(f"Unknown input type: {input_type}")


# ---------------------------------------------------------------------------
# Local path
# ---------------------------------------------------------------------------


def _resolve_local_path(target_path: Optional[str]) -> ResolvedInput:
    if not target_path:
        raise InputResolutionError("target_path is required for local_path input type")

    resolved = Path(target_path).resolve()
    if not resolved.exists():
        raise InputResolutionError(f"Path not found: {target_path}")
    if not resolved.is_dir():
        raise InputResolutionError(f"Path is not a directory: {target_path}")

    return ResolvedInput(
        resolved_path=str(resolved),
        input_type=InputType.LOCAL_PATH,
        is_temporary=False,
        original_source=target_path,
    )


# ---------------------------------------------------------------------------
# Pasted code
# ---------------------------------------------------------------------------


def _resolve_pasted_code(
    pasted_code: Optional[str],
    pasted_files: Optional[dict[str, str]],
) -> ResolvedInput:
    if not pasted_code and not pasted_files:
        raise InputResolutionError(
            "Either pasted_code or pasted_files is required for pasted_code input type"
        )

    temp_dir = tempfile.mkdtemp(prefix="phoenix_paste_")
    project_dir = os.path.join(temp_dir, "project")
    os.makedirs(project_dir)

    if pasted_files:
        for filename, content in pasted_files.items():
            safe_name = os.path.basename(filename)
            if not safe_name:
                safe_name = "untitled.py"
            filepath = os.path.join(project_dir, safe_name)
            with open(filepath, "w") as f:
                f.write(content)
    elif pasted_code:
        filepath = os.path.join(project_dir, "main.py")
        with open(filepath, "w") as f:
            f.write(pasted_code)

    # Initialize git repo so git tools don't crash
    git_env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Phoenix",
        "GIT_AUTHOR_EMAIL": "phoenix@agent",
        "GIT_COMMITTER_NAME": "Phoenix",
        "GIT_COMMITTER_EMAIL": "phoenix@agent",
    }
    subprocess.run(["git", "init"], cwd=project_dir, capture_output=True, timeout=10)
    subprocess.run(["git", "add", "."], cwd=project_dir, capture_output=True, timeout=10)
    subprocess.run(
        ["git", "commit", "-m", "Initial paste"],
        cwd=project_dir, capture_output=True, timeout=10, env=git_env,
    )

    return ResolvedInput(
        resolved_path=project_dir,
        input_type=InputType.PASTED_CODE,
        is_temporary=True,
        original_source="<pasted code>",
        temp_dir=temp_dir,
    )


# ---------------------------------------------------------------------------
# GitHub URL
# ---------------------------------------------------------------------------

# Matches:
#   https://github.com/owner/repo
#   https://github.com/owner/repo/tree/branch/path
#   https://github.com/owner/repo/blob/branch/file.py
_GITHUB_REPO_RE = re.compile(
    r"https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)"
    r"(?:/(?P<type>tree|blob)/(?P<ref>[^/]+)(?:/(?P<path>.+))?)?"
)


def _resolve_github_url(github_url: Optional[str]) -> ResolvedInput:
    if not github_url:
        raise InputResolutionError("github_url is required for github_url input type")

    match = _GITHUB_REPO_RE.match(github_url.strip())
    if not match:
        raise InputResolutionError(
            f"Invalid GitHub URL: {github_url}. "
            "Expected: https://github.com/owner/repo"
        )

    owner = match.group("owner")
    repo = match.group("repo")
    url_type = match.group("type")
    ref = match.group("ref") or "HEAD"
    sub_path = match.group("path")

    temp_dir = tempfile.mkdtemp(prefix="phoenix_gh_")
    clone_dir = os.path.join(temp_dir, repo)

    clone_url = f"https://github.com/{owner}/{repo}.git"
    clone_cmd = ["git", "clone", "--depth", "1"]
    if ref != "HEAD":
        clone_cmd.extend(["--branch", ref])
    clone_cmd.extend([clone_url, clone_dir])

    try:
        proc = subprocess.run(
            clone_cmd, capture_output=True, text=True, timeout=120,
        )
        if proc.returncode != 0:
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise InputResolutionError(f"git clone failed: {proc.stderr.strip()}")
    except subprocess.TimeoutExpired:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise InputResolutionError("git clone timed out (120s limit)")

    # If a sub-path was specified (tree URL), point to that directory
    resolved_path = clone_dir
    if sub_path and url_type == "tree":
        sub_full = os.path.join(clone_dir, sub_path)
        if os.path.isdir(sub_full):
            resolved_path = sub_full

    return ResolvedInput(
        resolved_path=resolved_path,
        input_type=InputType.GITHUB_URL,
        is_temporary=True,
        original_source=github_url,
        temp_dir=temp_dir,
    )
