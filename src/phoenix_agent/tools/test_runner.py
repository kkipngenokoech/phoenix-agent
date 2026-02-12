"""Tool 2: Test Runner & Validator - run test suites and validate refactored code."""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Optional

from phoenix_agent.models import (
    CoverageReport,
    TestFailure,
    TestFailureType,
    TestResult,
    TestScope,
    TestSummary,
)
from phoenix_agent.tools.base import BaseTool, ToolCategory, ToolResult

logger = logging.getLogger(__name__)


class TestRunnerTool(BaseTool):
    name = "test_runner"
    description = "Run test suites to validate refactored code maintains correctness."
    category = ToolCategory.TESTING
    parameters_schema = {
        "required": ["project_path"],
        "properties": {
            "project_path": {"type": "string", "description": "Path to project root"},
            "test_scope": {"type": "string", "default": "unit"},
            "test_paths": {"type": "array", "default": []},
            "parallel": {"type": "boolean", "default": False},
            "coverage_required": {"type": "boolean", "default": True},
            "timeout_seconds": {"type": "integer", "default": 600},
            "fail_fast": {"type": "boolean", "default": False},
        },
    }

    def execute(
        self,
        project_path: str,
        test_scope: str = "unit",
        test_paths: Optional[list[str]] = None,
        parallel: bool = False,
        coverage_required: bool = True,
        timeout_seconds: int = 600,
        fail_fast: bool = False,
        **kwargs,
    ) -> ToolResult:
        project = Path(project_path)
        if not project.exists():
            return ToolResult(success=False, error=f"Project path not found: {project_path}")

        cmd = self._build_command(
            project, test_scope, test_paths, parallel,
            coverage_required, fail_fast,
        )

        logger.info(f"Running tests: {' '.join(cmd)}")

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                cwd=str(project),
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                output=TestResult(status="error", summary=TestSummary()).model_dump(),
                error=f"Test execution timed out after {timeout_seconds}s",
            )
        except FileNotFoundError:
            return ToolResult(
                success=False,
                error="pytest not found. Install with: pip install pytest",
            )

        # Pytest exit code 5 = no tests collected (not a failure)
        if proc.returncode == 5:
            logger.info("No tests collected — treating as passed")
            return ToolResult(
                success=True,
                output=TestResult(
                    status="passed",
                    summary=TestSummary(total=0, passed=0),
                ).model_dump(),
                metadata={"return_code": 5, "note": "no tests collected"},
            )

        test_result = self._parse_output(proc, coverage_required, str(project))

        error_msg = None
        if test_result.status != "passed":
            failure_details = "; ".join(
                f"{f.test_name}: {f.error_message}" for f in test_result.failures[:3]
            ) if test_result.failures else proc.stderr[:200] or "Tests failed (see output)"
            error_msg = failure_details

        return ToolResult(
            success=test_result.status == "passed",
            output=test_result.model_dump(),
            error=error_msg,
            metadata={
                "return_code": proc.returncode,
                "stdout_lines": len(proc.stdout.splitlines()),
            },
        )

    # ------------------------------------------------------------------
    # Command building
    # ------------------------------------------------------------------

    def _build_command(
        self,
        project: Path,
        test_scope: str,
        test_paths: Optional[list[str]],
        parallel: bool,
        coverage: bool,
        fail_fast: bool,
    ) -> list[str]:
        cmd = [sys.executable, "-m", "pytest", "-v", "--tb=short"]

        # JSON report for structured output
        cmd.extend(["--json-report", "--json-report-file=.pytest_report.json"])

        # Scope filtering via markers
        if test_scope == "unit":
            cmd.extend(["-m", "not integration and not e2e"])
        elif test_scope == "integration":
            cmd.extend(["-m", "integration"])
        elif test_scope == "e2e":
            cmd.extend(["-m", "e2e"])
        # "all" = no marker filter

        if fail_fast:
            cmd.append("-x")

        if parallel:
            cmd.extend(["-n", "auto"])  # requires pytest-xdist

        if coverage:
            # Determine the source directory
            src_dir = "src" if (project / "src").exists() else "."
            cmd.extend([f"--cov={src_dir}", "--cov-report=json:.coverage_report.json"])

        # Specific test paths or default
        if test_paths:
            cmd.extend(test_paths)
        else:
            tests_dir = project / "tests"
            if tests_dir.exists():
                cmd.append("tests/")

        return cmd

    # ------------------------------------------------------------------
    # Output parsing
    # ------------------------------------------------------------------

    def _parse_output(self, proc: subprocess.CompletedProcess, coverage: bool, project_path: str) -> TestResult:
        # Try parsing JSON report first
        json_report = self._read_json_report(project_path)
        if json_report:
            return self._parse_json_report(json_report, proc, coverage, project_path)

        # Fallback: parse stdout
        return self._parse_stdout(proc)

    def _read_json_report(self, project_path: str) -> Optional[dict]:
        report_path = Path(project_path) / ".pytest_report.json"
        try:
            with open(report_path) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def _parse_json_report(
        self, report: dict, proc: subprocess.CompletedProcess, coverage: bool, project_path: str = "."
    ) -> TestResult:
        summary_data = report.get("summary", {})
        tests = report.get("tests", [])

        summary = TestSummary(
            total=summary_data.get("total", 0),
            passed=summary_data.get("passed", 0),
            failed=summary_data.get("failed", 0),
            skipped=summary_data.get("deselected", 0) + summary_data.get("xfailed", 0),
            errors=summary_data.get("error", 0),
            duration_seconds=report.get("duration", 0.0),
        )

        failures: list[TestFailure] = []
        for test in tests:
            if test.get("outcome") in ("failed", "error"):
                call = test.get("call", {})
                failures.append(TestFailure(
                    test_name=test.get("nodeid", "unknown"),
                    test_file=test.get("nodeid", "").split("::")[0],
                    failure_type=TestFailureType.EXCEPTION if test["outcome"] == "error" else TestFailureType.ASSERTION,
                    error_message=call.get("crash", {}).get("message", ""),
                    stack_trace=call.get("longrepr", ""),
                ))

        status = "passed" if proc.returncode == 0 else "failed"
        if summary.errors > 0:
            status = "error"

        coverage_report = self._parse_coverage(project_path) if coverage else None

        return TestResult(
            status=status,
            summary=summary,
            failures=failures,
            coverage=coverage_report,
        )

    def _parse_stdout(self, proc: subprocess.CompletedProcess) -> TestResult:
        """Fallback parser for when JSON report is unavailable."""
        output = proc.stdout + proc.stderr
        passed = failed = errors = 0

        for line in output.splitlines():
            if "passed" in line and "failed" in line.lower():
                # Parse "X passed, Y failed" summary line
                parts = line.split(",")
                for part in parts:
                    part = part.strip()
                    if "passed" in part:
                        try:
                            passed = int(part.split()[0])
                        except (ValueError, IndexError):
                            pass
                    elif "failed" in part:
                        try:
                            failed = int(part.split()[0])
                        except (ValueError, IndexError):
                            pass
                    elif "error" in part:
                        try:
                            errors = int(part.split()[0])
                        except (ValueError, IndexError):
                            pass
            elif "passed" in line and "failed" not in line.lower():
                try:
                    passed = int(line.strip().split()[0])
                except (ValueError, IndexError):
                    pass

        status = "passed" if proc.returncode == 0 else "failed"
        if errors > 0:
            status = "error"

        return TestResult(
            status=status,
            summary=TestSummary(
                total=passed + failed + errors,
                passed=passed,
                failed=failed,
                errors=errors,
            ),
        )

    def _parse_coverage(self, project_path: str = ".") -> Optional[CoverageReport]:
        try:
            with open(Path(project_path) / ".coverage_report.json") as f:
                data = json.load(f)

            totals = data.get("totals", {})
            files = data.get("files", {})

            per_file = {}
            uncovered: dict[str, list[int]] = {}
            for fp, file_data in files.items():
                summary = file_data.get("summary", {})
                per_file[fp] = summary.get("percent_covered", 0.0)
                missing = file_data.get("missing_lines", [])
                if missing:
                    uncovered[fp] = missing

            return CoverageReport(
                overall_percentage=totals.get("percent_covered", 0.0),
                per_file=per_file,
                uncovered_lines=uncovered,
            )
        except Exception:
            return None
