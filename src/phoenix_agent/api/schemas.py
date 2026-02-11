"""API request/response schemas."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class RefactorRequest(BaseModel):
    target_path: str = "./sample_project"
    request: str = "Refactor UserService to follow the Single Responsibility Principle"


class RefactorResponse(BaseModel):
    session_id: str
    status: str = "started"


class AnalyzeRequest(BaseModel):
    target_path: str = "./sample_project"


class AnalyzeResponse(BaseModel):
    files: list[dict] = []
    test_results: Optional[dict] = None


class SessionSummary(BaseModel):
    session_id: str
    outcome: str
    duration_seconds: float
    files_modified: list[str] = []
    pr_url: Optional[str] = None
    timestamp: Optional[str] = None


class PhaseEvent(BaseModel):
    type: str  # "iteration_start" | "phase_update" | "completed" | "error"
    session_id: str
    iteration: int = 0
    phase: Optional[str] = None
    data: Any = None
    message: Optional[str] = None
