"""ACT phase - execute refactoring plan steps using tools."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from phoenix_agent.config import PhoenixConfig
from phoenix_agent.models import RefactoringPlan, RefactoringStep
from phoenix_agent.tools.registry import ToolRegistry
from phoenix_agent.tools.base import ToolResult

logger = logging.getLogger(__name__)


class Executor:
    def __init__(self, config: PhoenixConfig, tool_registry: ToolRegistry) -> None:
        self._config = config
        self._tools = tool_registry

    def execute(
        self, plan: RefactoringPlan, tool_mapping: dict[str, str], project_path: str
    ) -> list[dict]:
        """Execute all plan steps in order. Returns list of step results."""
        logger.info(f"ACT: executing {len(plan.steps)} plan steps")
        results: list[dict] = []

        for step in plan.steps:
            logger.info(f"  Step {step.step_id}: {step.action} - {step.description}")

            try:
                result = self._execute_step(step, project_path)
                step_result = {
                    "step_id": step.step_id,
                    "action": step.action,
                    "target_file": step.target_file,
                    "success": result.success,
                    "output": result.output,
                    "error": result.error,
                    "execution_time_ms": result.execution_time_ms,
                }
                results.append(step_result)

                if not result.success:
                    logger.error(f"  Step {step.step_id} FAILED: {result.error}")
                    # Check if this is a critical failure
                    if step.action == "modify_code":
                        # Code modification failed - this is critical
                        step_result["critical"] = True
                        break
                else:
                    logger.info(f"  Step {step.step_id} SUCCESS")

            except Exception as e:
                logger.error(f"  Step {step.step_id} EXCEPTION: {e}")
                results.append({
                    "step_id": step.step_id,
                    "action": step.action,
                    "success": False,
                    "error": str(e),
                    "critical": True,
                })
                break

        logger.info(f"ACT complete: {sum(1 for r in results if r['success'])}/{len(results)} steps succeeded")
        return results

    def _execute_step(self, step: RefactoringStep, project_path: str) -> ToolResult:
        if step.action == "parse_code":
            return self._tools.execute(
                "ast_parser",
                file_paths=[step.target_file],
                analysis_depth="deep",
            )

        elif step.action == "modify_code":
            return self._modify_file(step)

        elif step.action == "run_tests":
            return self._tools.execute(
                "test_runner",
                project_path=project_path,
                test_scope="unit",
                coverage_required=True,
            )

        else:
            return ToolResult(success=False, error=f"Unknown action: {step.action}")

    def _modify_file(self, step: RefactoringStep) -> ToolResult:
        """Write code changes to the target file."""
        if not step.code_changes:
            return ToolResult(success=False, error="No code_changes provided for modify_code step")

        target = Path(step.target_file)
        if not target.parent.exists():
            target.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Read original for backup
            original = ""
            if target.exists():
                original = target.read_text()

            # Write new content
            target.write_text(step.code_changes)

            # Verify the file is valid Python
            try:
                import ast as ast_module
                ast_module.parse(step.code_changes)
            except SyntaxError as e:
                # Rollback on syntax error
                if original:
                    target.write_text(original)
                return ToolResult(
                    success=False,
                    error=f"Generated code has syntax error: {e}. Rolled back.",
                )

            return ToolResult(
                success=True,
                output={
                    "file": step.target_file,
                    "original_lines": len(original.splitlines()),
                    "new_lines": len(step.code_changes.splitlines()),
                },
                metadata={"original_content": original},
            )

        except Exception as e:
            return ToolResult(success=False, error=f"File write failed: {e}")
