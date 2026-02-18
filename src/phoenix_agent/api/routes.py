"""FastAPI REST and WebSocket endpoints."""

from __future__ import annotations

import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from phoenix_agent.api.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    PhaseEvent,
    RefactorRequest,
    RefactorResponse,
    SessionSummary,
)
from phoenix_agent.api.websocket import make_phase_callback, manager
from phoenix_agent.config import PhoenixConfig
from phoenix_agent.input_resolver import (
    InputResolutionError,
    cleanup_session,
    register_temp,
    resolve_input,
)
from phoenix_agent.memory.history import RefactoringHistory
from phoenix_agent.memory.session import SessionMemory
from phoenix_agent.tools.ast_parser import ASTParserTool
from phoenix_agent.tools.test_runner import TestRunnerTool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")
ws_router = APIRouter()

# Shared state — initialized in main.py lifespan
_config: PhoenixConfig | None = None
_session_memory: SessionMemory | None = None
_history: RefactoringHistory | None = None
_executor = ThreadPoolExecutor(max_workers=2)


def init_shared_state(
    config: PhoenixConfig,
    session_memory: SessionMemory,
    history: RefactoringHistory,
) -> None:
    global _config, _session_memory, _history
    _config = config
    _session_memory = session_memory
    _history = history


# ---------------------------------------------------------------------------
# Directory Browser
# ---------------------------------------------------------------------------


@router.get("/browse")
async def browse_directory(path: str = Query(default="~")) -> dict:
    """List subdirectories at the given path for the folder picker."""
    try:
        target = Path(path).expanduser().resolve()
        if not target.is_dir():
            return {"error": f"Not a directory: {path}"}

        entries = []
        try:
            for child in sorted(target.iterdir()):
                if child.name.startswith("."):
                    continue
                if child.is_dir():
                    entries.append({
                        "name": child.name,
                        "path": str(child),
                        "has_children": any(
                            c.is_dir() for c in child.iterdir()
                            if not c.name.startswith(".")
                        ) if os.access(str(child), os.R_OK) else False,
                    })
        except PermissionError:
            return {"error": f"Permission denied: {target}"}

        return {
            "current": str(target),
            "parent": str(target.parent) if target != target.parent else None,
            "entries": entries,
        }
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# REST Endpoints
# ---------------------------------------------------------------------------


@router.post("/refactor", response_model=RefactorResponse)
async def start_refactor(req: RefactorRequest) -> RefactorResponse:
    """Start a refactoring session. Runs the agent in a background thread."""
    from phoenix_agent.agent import PhoenixAgent
    from phoenix_agent.models import RefactoringGoal

    try:
        resolved = resolve_input(
            input_type=req.input_type,
            target_path=req.target_path,
            pasted_code=req.pasted_code,
            pasted_files=req.pasted_files,
            github_url=req.github_url,
        )
    except InputResolutionError as e:
        return RefactorResponse(session_id="", status=f"error: {e}")

    loop = asyncio.get_running_loop()
    agent = PhoenixAgent(_config)

    goal = RefactoringGoal(description=req.request, target_files=[])
    session = agent.session_memory.create_session(goal, resolved.resolved_path)
    session_id = session.session_id

    register_temp(session_id, resolved)
    callback = make_phase_callback(session_id, loop)

    def _run_agent() -> dict[str, Any]:
        try:
            result = agent.run(
                req.request,
                resolved.resolved_path,
                on_phase=callback,
                session_id=session_id,
            )
            return result
        except Exception as e:
            logger.error(f"Agent error: {e}", exc_info=True)
            return {"status": "failed", "reason": str(e)}
        finally:
            agent.close()
            cleanup_session(session_id)
            queue = manager.get_queue(session_id)
            loop.call_soon_threadsafe(queue.put_nowait, None)

    loop.run_in_executor(_executor, _run_agent)

    return RefactorResponse(session_id=session_id, status="started")


@router.post("/analyze", response_model=AnalyzeResponse)
async def run_analysis(req: AnalyzeRequest) -> AnalyzeResponse:
    """Run AST analysis + tests on a target project (synchronous, fast)."""
    try:
        resolved = resolve_input(
            input_type=req.input_type,
            target_path=req.target_path,
            pasted_code=req.pasted_code,
            pasted_files=req.pasted_files,
            github_url=req.github_url,
        )
    except InputResolutionError as e:
        return AnalyzeResponse(files=[], test_results={"error": str(e)})

    target = Path(resolved.resolved_path)
    try:
        parser = ASTParserTool()
        runner = TestRunnerTool()

        py_files = sorted(
            str(p)
            for p in target.rglob("*.py")
            if "__pycache__" not in str(p) and "test_" not in p.name and "/tests/" not in str(p)
        )

        ast_result = parser.execute(file_paths=py_files)
        test_result = runner.execute(project_path=str(target), coverage_required=False)

        files = ast_result.output.get("parsed_files", []) if ast_result.success else []
        test_data = test_result.output if test_result.success else {"error": test_result.error}

        return AnalyzeResponse(files=files, test_results=test_data)
    finally:
        resolved.cleanup()


@router.get("/sessions", response_model=list[SessionSummary])
async def list_sessions() -> list[SessionSummary]:
    """List recent refactoring sessions from PostgreSQL history."""
    if not _history:
        return []
    records = _history.get_history(limit=20)
    return [
        SessionSummary(
            session_id=r.session_id,
            outcome=r.outcome,
            duration_seconds=r.duration_seconds,
            files_modified=r.files_modified,
            pr_url=r.pr_url,
            timestamp=r.timestamp.isoformat() if r.timestamp else None,
        )
        for r in records
    ]


@router.get("/sessions/{session_id}")
async def get_session(session_id: str) -> dict:
    """Get session details + iteration data from Redis."""
    if not _session_memory:
        return {"error": "Session memory not available"}

    session = _session_memory.get_session(session_id)
    if not session:
        # Try PostgreSQL history as fallback
        if _history:
            record = _history.get_by_session(session_id)
            if record:
                data = record.model_dump(mode="json")
                # Wrap in same structure frontend expects
                return {
                    "session": {
                        "session_id": record.session_id,
                        "status": record.outcome,
                        "duration_seconds": record.duration_seconds,
                    },
                    "iterations": [],
                    "original_files": record.original_files or {},
                    "refactored_files": record.refactored_files or {},
                    "metrics_before": record.metrics_before or {},
                    "metrics_after": record.metrics_after or {},
                }
        return {"error": "Session not found"}

    iterations = _session_memory.get_all_iterations(session_id)

    # Include file contents from history if available
    files_data = {}
    if _history:
        record = _history.get_by_session(session_id)
        if record:
            files_data = {
                "original_files": record.original_files or {},
                "refactored_files": record.refactored_files or {},
                "metrics_before": record.metrics_before or {},
                "metrics_after": record.metrics_after or {},
            }

    return {
        "session": session.model_dump(mode="json"),
        "iterations": [it.model_dump(mode="json") for it in iterations],
        **files_data,
    }


# ---------------------------------------------------------------------------
# Review Endpoints (human-in-the-loop approval)
# ---------------------------------------------------------------------------


@router.get("/sessions/{session_id}/review")
async def get_review(session_id: str) -> dict:
    """Fetch the review payload for a session (used when reconnecting)."""
    if not _session_memory:
        return {"error": "Session memory not available"}
    review = _session_memory.get_review(session_id)
    if not review:
        return {"error": "No review found for this session"}
    return review.model_dump(mode="json")


@router.post("/sessions/{session_id}/review")
async def submit_review(session_id: str, body: dict) -> dict:
    """Submit approval or rejection for a pending diff review."""
    from phoenix_agent.api.agent_registry import submit_verdict
    from phoenix_agent.models import ReviewVerdict, SessionStatus

    if _session_memory:
        session = _session_memory.get_session(session_id)
        if not session:
            return {"error": "Session not found"}
        if session.status not in (SessionStatus.AWAITING_REVIEW, SessionStatus.AWAITING_APPROVAL):
            return {"error": f"Session is not awaiting review/approval (status: {session.status})"}

    verdict = ReviewVerdict(
        approved=body.get("approved", False),
        comment=body.get("comment", ""),
    )
    success = submit_verdict(session_id, verdict)
    if not success:
        return {"error": "No pending review for this session"}

    return {"status": "ok", "session_id": session_id, "approved": verdict.approved}


# ---------------------------------------------------------------------------
# WebSocket Endpoint
# ---------------------------------------------------------------------------


@ws_router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str) -> None:
    """Stream real-time phase events to the client.

    The ConnectionManager handles draining the event queue and broadcasting
    to all connected clients. This handler just keeps the connection alive
    and cleans up on disconnect.
    """
    await manager.connect(session_id, websocket)
    try:
        # Keep connection open — just wait for client messages or disconnect
        while True:
            try:
                await websocket.receive_text()
            except WebSocketDisconnect:
                break
    except RuntimeError:
        pass
    except Exception as e:
        logger.error(f"WebSocket error for {session_id}: {e}")
    finally:
        manager.disconnect(session_id, websocket)
