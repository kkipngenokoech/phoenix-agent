"""CoderAgent - handles a single modify_code or parse_code step.

Each instance gets its own LLM for thread safety when running in parallel.
"""

from __future__ import annotations

from typing import Any

from phoenix_agent.crew.base_agent import SubAgent
from phoenix_agent.crew.code_gen import generate_code, is_test_file, modify_file
from phoenix_agent.crew.task import Task, TaskResult, TaskType
from phoenix_agent.models import RefactoringStep
from phoenix_agent.tools.ast_parser import ASTParserTool
from phoenix_agent.tools.base import ToolResult


class CoderAgent(SubAgent):
    name = "coder"

    def __init__(
        self,
        llm: Any,
        ast_parser: ASTParserTool,
        test_failures: list[dict] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._llm = llm
        self._ast_parser = ast_parser
        self._test_failures = test_failures or []

    def execute(self, task: Task) -> TaskResult:
        """Execute a single coding step (parse_code or modify_code)."""
        step: RefactoringStep = task.payload["step"]
        iteration = task.payload.get("iteration", 1)
        total_steps = task.payload.get("total_steps", 1)

        self._log.info(f"Step {step.step_id}: {step.action} - {step.target_file}")
        self.emit_event(
            "act_step",
            data={
                "status": "running",
                "step_id": step.step_id,
                "total_steps": total_steps,
                "action": step.action,
                "description": step.description,
                "target_file": step.target_file,
            },
            iteration=iteration,
        )

        try:
            if step.action == "parse_code":
                result = self._parse_code(step)
            elif step.action == "modify_code":
                result = self._modify_code(step)
            else:
                result = ToolResult(success=False, error=f"CoderAgent cannot handle action: {step.action}")
        except Exception as e:
            self._log.error(f"Step {step.step_id} EXCEPTION: {e}")
            self.emit_event(
                "act_step",
                data={
                    "status": "failed",
                    "step_id": step.step_id,
                    "total_steps": total_steps,
                    "action": step.action,
                    "error": str(e),
                },
                iteration=iteration,
            )
            return TaskResult(
                task_id=task.task_id,
                task_type=TaskType.CODE,
                success=False,
                data=self._step_result_dict(step, ToolResult(success=False, error=str(e))),
                error=str(e),
            )

        status = "success" if result.success else "failed"
        self.emit_event(
            "act_step",
            data={
                "status": status,
                "step_id": step.step_id,
                "total_steps": total_steps,
                "action": step.action,
                **({"error": result.error} if result.error else {}),
            },
            iteration=iteration,
        )

        step_result = self._step_result_dict(step, result)

        # Syntax errors from LLM generation are NOT critical — the file
        # was rolled back by modify_file(), so the agent can safely retry.
        # Only mark truly unrecoverable errors (e.g. filesystem) as critical.
        if not result.success and step.action == "modify_code":
            error_msg = result.error or ""
            is_syntax = "syntax error" in error_msg.lower()
            is_llm_fail = "llm failed" in error_msg.lower()
            if not is_test_file(step.target_file) and not is_syntax and not is_llm_fail:
                step_result["critical"] = True

        return TaskResult(
            task_id=task.task_id,
            task_type=TaskType.CODE,
            success=result.success,
            data=step_result,
            error=result.error,
        )

    def _parse_code(self, step: RefactoringStep) -> ToolResult:
        return self._ast_parser.execute(
            file_paths=[step.target_file],
            analysis_depth="deep",
        )

    def _modify_code(self, step: RefactoringStep) -> ToolResult:
        code_changes = step.code_changes

        if not code_changes:
            self._log.info(f"Generating code via LLM for {step.target_file}...")
            code_changes = generate_code(
                self._llm,
                step.target_file,
                step.description,
                self._test_failures,
            )
            if code_changes is None:
                return ToolResult(
                    success=False,
                    error="LLM failed to generate code for this step",
                )

        return modify_file(step.target_file, code_changes)

    @staticmethod
    def _step_result_dict(step: RefactoringStep, result: ToolResult) -> dict:
        return {
            "step_id": step.step_id,
            "action": step.action,
            "target_file": step.target_file,
            "success": result.success,
            "output": result.output,
            "error": result.error,
            "execution_time_ms": result.execution_time_ms,
            "metadata": result.metadata,
        }
