"""ACT phase - execute refactoring plan steps using tools."""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from phoenix_agent.config import PhoenixConfig
from phoenix_agent.crew.code_gen import (
    generate_code,
    is_test_file,
    modify_file,
)
from phoenix_agent.models import RefactoringPlan, RefactoringStep
from phoenix_agent.tools.base import ToolResult
from phoenix_agent.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class Executor:
    def __init__(self, config: PhoenixConfig, tool_registry: ToolRegistry, llm: Any = None) -> None:
        self._config = config
        self._tools = tool_registry
        self._llm = llm
        self._last_test_failures: list[dict] = []

    def execute(
        self,
        plan: RefactoringPlan,
        tool_mapping: dict[str, str],
        project_path: str,
        on_step: Optional[Callable[..., None]] = None,
    ) -> list[dict]:
        """Execute all plan steps in order. Returns list of step results."""
        logger.info(f"ACT: executing {len(plan.steps)} plan steps")
        results: list[dict] = []
        emit_step = on_step or (lambda **kw: None)
        total_steps = len(plan.steps)

        for step in plan.steps:
            logger.info(f"  Step {step.step_id}: {step.action} - {step.description}")
            emit_step(
                status="running",
                step_id=step.step_id,
                total_steps=total_steps,
                action=step.action,
                description=step.description,
                target_file=step.target_file,
            )

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
                    "metadata": result.metadata,
                }
                results.append(step_result)

                if not result.success:
                    logger.error(f"  Step {step.step_id} FAILED: {result.error}")
                    emit_step(
                        status="failed",
                        step_id=step.step_id,
                        total_steps=total_steps,
                        action=step.action,
                        error=result.error,
                    )
                    if step.action == "modify_code":
                        if is_test_file(step.target_file):
                            logger.warning(f"  Test file modification failed (non-critical): {step.target_file}")
                        else:
                            step_result["critical"] = True
                            break
                else:
                    logger.info(f"  Step {step.step_id} SUCCESS")
                    emit_step(
                        status="success",
                        step_id=step.step_id,
                        total_steps=total_steps,
                        action=step.action,
                    )

            except Exception as e:
                logger.error(f"  Step {step.step_id} EXCEPTION: {e}")
                emit_step(
                    status="failed",
                    step_id=step.step_id,
                    total_steps=total_steps,
                    action=step.action,
                    error=str(e),
                )
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

        elif step.action == "generate_tests":
            return self._tools.execute(
                "test_generator",
                file_path=step.target_file,
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
        code_changes = step.code_changes

        if not code_changes:
            if not self._llm:
                return ToolResult(
                    success=False,
                    error="No code_changes provided and no LLM available to generate code",
                )
            logger.info(f"  Generating code via LLM for {step.target_file}...")
            code_changes = generate_code(
                self._llm,
                step.target_file,
                step.description,
                self._last_test_failures,
            )
            if code_changes is None:
                return ToolResult(
                    success=False,
                    error="LLM failed to generate code for this step",
                )
            logger.debug(f"  Generated code preview:\n{code_changes[:500]}")

        return modify_file(step.target_file, code_changes)

    def set_test_failures(self, failures: list[dict]) -> None:
        """Set test failure context from a previous iteration."""
        self._last_test_failures = failures
