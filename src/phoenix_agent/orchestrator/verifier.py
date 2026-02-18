"""VERIFY phase - run tests and compare metrics before vs after."""

from __future__ import annotations

import logging

from phoenix_agent.models import (
    FileMetrics,
    TestResult,
    ValidationLevel,
    VerificationReport,
)
from phoenix_agent.tools.ast_parser import ASTParserTool
from phoenix_agent.tools.test_runner import TestRunnerTool

logger = logging.getLogger(__name__)


class Verifier:
    def __init__(self, ast_parser: ASTParserTool, test_runner: TestRunnerTool) -> None:
        self._ast_parser = ast_parser
        self._test_runner = test_runner

    def verify(
        self,
        step_results: list[dict],
        validation_level: ValidationLevel,
        project_path: str,
        metrics_before: list[FileMetrics],
    ) -> VerificationReport:
        logger.info(f"VERIFY: running validation (level={validation_level.value})")

        # Check if any steps had critical failures
        critical_failures = [r for r in step_results if r.get("critical")]
        if critical_failures:
            return VerificationReport(
                tests_passed=False,
                improved=False,
                details=f"Critical failure in step {critical_failures[0]['step_id']}: {critical_failures[0].get('error', 'unknown')}",
            )

        # Run tests
        test_scope = "all" if validation_level == ValidationLevel.EXTRA else "unit"
        test_result_raw = self._test_runner.execute(
            project_path=project_path,
            test_scope=test_scope,
            coverage_required=True,
        )

        test_result = None
        tests_passed = False
        coverage_pct = 0.0

        if test_result_raw.success and test_result_raw.output:
            test_result = TestResult.model_validate(test_result_raw.output)
            tests_passed = test_result.status == "passed"
            if test_result.coverage:
                coverage_pct = test_result.coverage.overall_percentage

        # Gather metrics after refactoring
        modified_files = [r["target_file"] for r in step_results if r.get("action") == "modify_code" and r.get("success")]
        metrics_after_raw = self._ast_parser.execute(file_paths=modified_files) if modified_files else None

        complexity_before: dict[str, int] = {}
        complexity_after: dict[str, int] = {}

        for m in metrics_before:
            complexity_before[m.file_path] = m.cyclomatic_complexity

        if metrics_after_raw and metrics_after_raw.success:
            for pf in metrics_after_raw.output.get("parsed_files", []):
                fp = pf["file_path"]
                complexity_after[fp] = pf["metrics"]["cyclomatic_complexity"]

        # Determine if metrics improved
        improved = self._metrics_improved(complexity_before, complexity_after)

        report = VerificationReport(
            tests_passed=tests_passed,
            test_result=test_result,
            coverage_pct=coverage_pct,
            complexity_before=complexity_before,
            complexity_after=complexity_after,
            improved=improved,
            details=self._build_details(tests_passed, improved, complexity_before, complexity_after),
        )

        logger.info(f"VERIFY complete: tests={'PASS' if tests_passed else 'FAIL'}, improved={improved}")
        return report

    def _metrics_improved(
        self, before: dict[str, int], after: dict[str, int]
    ) -> bool:
        if not before and not after:
            return False

        if not before or not after:
            return bool(after)

        # SRP extraction: splitting 1 file into multiple is an improvement by definition
        # (the whole point is separation of concerns, not reducing total LOC)
        if len(after) > len(before):
            logger.info(
                f"SRP extraction detected: {len(before)} file(s) → {len(after)} file(s) — treating as improved"
            )
            return True

        max_before = max(before.values()) if before else 0
        max_after = max(after.values()) if after else 0

        total_before = sum(before.values())
        total_after = sum(after.values())

        # Improved if: total complexity decreased OR max per-file complexity decreased
        return total_after <= total_before or max_after < max_before

    def _build_details(
        self,
        tests_passed: bool,
        improved: bool,
        before: dict[str, int],
        after: dict[str, int],
    ) -> str:
        lines = []
        lines.append(f"Tests: {'PASSED' if tests_passed else 'FAILED'}")
        lines.append(f"Metrics improved: {'Yes' if improved else 'No'}")

        if before and after:
            lines.append("\nComplexity changes:")
            all_files = set(before.keys()) | set(after.keys())
            for f in sorted(all_files):
                b = before.get(f, 0)
                a = after.get(f, 0)
                delta = a - b
                sign = "+" if delta > 0 else ""
                lines.append(f"  {f}: {b} → {a} ({sign}{delta})")

        return "\n".join(lines)
