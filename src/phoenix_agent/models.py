"""Phoenix Agent data models - all schemas for the 7-phase agent loop."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class AgentPhase(str, Enum):
    OBSERVE = "OBSERVE"
    REASON = "REASON"
    PLAN = "PLAN"
    DECIDE = "DECIDE"
    ACT = "ACT"
    VERIFY = "VERIFY"
    UPDATE = "UPDATE"


class SessionStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    REJECTED = "rejected"
    AWAITING_APPROVAL = "awaiting_approval"
    AWAITING_REVIEW = "awaiting_review"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ValidationLevel(str, Enum):
    STANDARD = "standard"       # unit tests only
    EXTRA = "extra"             # full test suite + integration


class CodeSmellType(str, Enum):
    LONG_METHOD = "long_method"
    GOD_CLASS = "god_class"
    DUPLICATE_CODE = "duplicate_code"
    LONG_PARAMETER_LIST = "long_parameter_list"
    DEEP_NESTING = "deep_nesting"
    MAGIC_NUMBERS = "magic_numbers"


class SmellSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TestScope(str, Enum):
    UNIT = "unit"
    INTEGRATION = "integration"
    E2E = "e2e"
    ALL = "all"


class TestFailureType(str, Enum):
    ASSERTION = "assertion"
    EXCEPTION = "exception"
    TIMEOUT = "timeout"


class GitOperation(str, Enum):
    CREATE_BRANCH = "create_branch"
    COMMIT = "commit"
    CREATE_PR = "create_pr"
    MERGE = "merge"
    RESET = "reset"
    DIFF = "diff"


# ---------------------------------------------------------------------------
# Session & Agent State
# ---------------------------------------------------------------------------

class RefactoringGoal(BaseModel):
    description: str
    target_files: list[str] = Field(default_factory=list)
    scope: str = "structural"  # structural | architectural


class SessionState(BaseModel):
    session_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    goal: RefactoringGoal
    status: SessionStatus = SessionStatus.ACTIVE
    current_phase: AgentPhase = AgentPhase.OBSERVE
    iteration_count: int = 0
    retry_count: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    target_path: str = ""
    branch_name: Optional[str] = None
    pr_url: Optional[str] = None
    error_message: Optional[str] = None
    last_test_failure: Optional[TestResult] = None



# ---------------------------------------------------------------------------
# Observation Phase
# ---------------------------------------------------------------------------

class CodebaseSnapshot(BaseModel):
    files: list[str] = Field(default_factory=list)
    git_status: str = ""
    current_branch: str = ""
    commit_hash: str = ""
    has_uncommitted_changes: bool = False


class FileMetrics(BaseModel):
    file_path: str
    lines_of_code: int = 0
    cyclomatic_complexity: int = 0
    function_count: int = 0
    class_count: int = 0
    max_nesting_depth: int = 0


class ObservationResult(BaseModel):
    snapshot: CodebaseSnapshot
    file_metrics: list[FileMetrics] = Field(default_factory=list)
    existing_test_results: Optional[TestResult] = None
    session_context: dict = Field(default_factory=dict)
    complete: bool = True


# ---------------------------------------------------------------------------
# Reasoning Phase
# ---------------------------------------------------------------------------

class ReasoningAnalysis(BaseModel):
    root_cause: str = ""
    approach: str = ""
    risk_assessment: RiskLevel = RiskLevel.MEDIUM
    expected_impact: str = ""
    files_to_modify: list[str] = Field(default_factory=list)
    rationale: str = ""


# ---------------------------------------------------------------------------
# Planning Phase
# ---------------------------------------------------------------------------

class RefactoringStep(BaseModel):
    step_id: int
    action: str  # "parse_code" | "modify_code" | "run_tests"
    target_file: str = ""
    description: str = ""
    dependencies: list[int] = Field(default_factory=list)  # step_ids
    code_changes: Optional[str] = None  # LLM-generated code


class RefactoringPlan(BaseModel):
    steps: list[RefactoringStep] = Field(default_factory=list)
    rollback_strategy: str = ""
    validation_checkpoints: list[int] = Field(default_factory=list)  # step_ids


# ---------------------------------------------------------------------------
# Decision Phase
# ---------------------------------------------------------------------------

class RiskScore(BaseModel):
    llm_risk: RiskLevel = RiskLevel.MEDIUM
    files_affected: int = 0
    test_coverage_pct: float = 0.0
    expected_complexity_change: float = 0.0
    total_score: float = 0.0

    def calculate(self) -> float:
        score = 0.0
        score += {"LOW": 1, "MEDIUM": 3, "HIGH": 5}[self.llm_risk.value]
        score += min(self.files_affected * 0.5, 3.0)
        if self.test_coverage_pct < 50:
            score += 2.0
        elif self.test_coverage_pct < 80:
            score += 1.0
        if self.expected_complexity_change > 0:
            score += 1.0
        self.total_score = score
        return score


class Decision(BaseModel):
    approved: bool = True
    validation_level: ValidationLevel = ValidationLevel.STANDARD
    tool_mapping: dict[str, str] = Field(default_factory=dict)
    requires_human: bool = False
    risk_score: RiskScore = Field(default_factory=RiskScore)
    reason: str = ""


# ---------------------------------------------------------------------------
# Tool Results (matching spec schemas)
# ---------------------------------------------------------------------------

class CodeSmell(BaseModel):
    type: CodeSmellType
    location: dict = Field(default_factory=dict)  # {"start_line": int, "end_line": int}
    severity: SmellSeverity = SmellSeverity.MEDIUM
    description: str = ""


class ParsedFile(BaseModel):
    file_path: str
    language: str = "python"
    metrics: FileMetrics
    dependencies: list[str] = Field(default_factory=list)
    code_smells: list[CodeSmell] = Field(default_factory=list)


class ASTAnalysisResult(BaseModel):
    status: str = "success"  # success | partial_success | failed
    parsed_files: list[ParsedFile] = Field(default_factory=list)
    dependency_graph: dict = Field(default_factory=dict)
    errors: list[dict] = Field(default_factory=list)


class TestFailure(BaseModel):
    test_name: str
    test_file: str = ""
    failure_type: TestFailureType = TestFailureType.ASSERTION
    error_message: str = ""
    stack_trace: str = ""
    affected_code: list[str] = Field(default_factory=list)


class TestSummary(BaseModel):
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    duration_seconds: float = 0.0


class CoverageReport(BaseModel):
    overall_percentage: float = 0.0
    per_file: dict[str, float] = Field(default_factory=dict)
    uncovered_lines: dict[str, list[int]] = Field(default_factory=dict)


class TestResult(BaseModel):
    status: str = "passed"  # passed | failed | error
    summary: TestSummary = Field(default_factory=TestSummary)
    failures: list[TestFailure] = Field(default_factory=list)
    coverage: Optional[CoverageReport] = None


class GitOperationResult(BaseModel):
    status: str = "success"  # success | failed
    operation: str = ""
    result: dict = Field(default_factory=dict)
    error: Optional[dict] = None


# ---------------------------------------------------------------------------
# Verification Phase
# ---------------------------------------------------------------------------

class VerificationReport(BaseModel):
    tests_passed: bool = False
    test_result: Optional[TestResult] = None
    coverage_pct: float = 0.0
    complexity_before: dict[str, int] = Field(default_factory=dict)
    complexity_after: dict[str, int] = Field(default_factory=dict)
    improved: bool = False
    details: str = ""


# ---------------------------------------------------------------------------
# Memory / History
# ---------------------------------------------------------------------------

class RefactoringRecord(BaseModel):
    session_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    files_modified: list[str] = Field(default_factory=list)
    risk_score: float = 0.0
    metrics_before: dict = Field(default_factory=dict)
    metrics_after: dict = Field(default_factory=dict)
    pr_url: Optional[str] = None
    outcome: str = "success"  # success | failed | timeout | rejected
    duration_seconds: float = 0.0


class TeamPreference(BaseModel):
    key: str
    value: Any
    rationale: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Iteration Record (stored in Redis per iteration)
# ---------------------------------------------------------------------------

class IterationData(BaseModel):
    iteration: int
    phase: AgentPhase
    observation: Optional[dict] = None
    reasoning: Optional[dict] = None
    plan: Optional[dict] = None
    decision: Optional[dict] = None
    tool_results: list[dict] = Field(default_factory=list)
    verification: Optional[dict] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Review / Human-in-the-Loop
# ---------------------------------------------------------------------------

class FileDiff(BaseModel):
    """Before/after diff for a single file."""
    file_path: str
    relative_path: str
    original_content: str
    modified_content: str
    unified_diff: str
    lines_added: int = 0
    lines_removed: int = 0


class ReviewPayload(BaseModel):
    """Full review package sent to the frontend for approval."""
    session_id: str
    files: list[FileDiff] = Field(default_factory=list)
    test_result: Optional[TestResult] = None
    coverage_pct: float = 0.0
    complexity_before: dict[str, int] = Field(default_factory=dict)
    complexity_after: dict[str, int] = Field(default_factory=dict)
    risk_score: float = 0.0
    plan_summary: str = ""


class ReviewVerdict(BaseModel):
    """User's approval or rejection of proposed changes."""
    approved: bool
    comment: str = ""
