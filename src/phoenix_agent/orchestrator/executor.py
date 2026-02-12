"""ACT phase - execute refactoring plan steps using tools."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from phoenix_agent.config import PhoenixConfig
from phoenix_agent.models import RefactoringPlan, RefactoringStep
from phoenix_agent.tools.registry import ToolRegistry
from phoenix_agent.tools.base import ToolResult

logger = logging.getLogger(__name__)

CODE_GEN_SYSTEM_PROMPT = """You are an expert Python developer. You will be given a file's current
source code and a description of what refactoring to apply. Respond with ONLY the complete
new file contents — no explanations, no markdown fences, no commentary.

Rules:
- Output ONLY valid Python code
- Preserve all existing functionality unless the description says to change it
- Keep imports, maintain the same module-level API
- Do NOT wrap your response in ```python``` or any other markers"""

CODE_GEN_PROMPT = """Apply the following refactoring to this file.

## Refactoring Description
{description}

## Current File: {file_path}
{file_content}

Respond with the complete updated file contents only."""


class Executor:
    def __init__(self, config: PhoenixConfig, tool_registry: ToolRegistry, llm: Any = None) -> None:
        self._config = config
        self._tools = tool_registry
        self._llm = llm

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
        """Write code changes to the target file.

        If `code_changes` is already provided (e.g. from a capable LLM like Claude),
        use it directly. Otherwise, generate the code via an LLM call using the
        step description and current file content.
        """
        code_changes = step.code_changes

        # Generate code via LLM if not provided by the planner
        if not code_changes:
            if not self._llm:
                return ToolResult(
                    success=False,
                    error="No code_changes provided and no LLM available to generate code",
                )
            logger.info(f"  Generating code via LLM for {step.target_file}...")
            code_changes = self._generate_code(step)
            if code_changes is None:
                return ToolResult(
                    success=False,
                    error="LLM failed to generate code for this step",
                )
            logger.debug(f"  Generated code preview:\n{code_changes[:500]}")

        target = Path(step.target_file)
        if not target.parent.exists():
            target.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Read original for backup
            original = ""
            if target.exists():
                original = target.read_text()

            # Write new content
            target.write_text(code_changes)

            # Verify the file is valid Python
            try:
                import ast as ast_module
                ast_module.parse(code_changes)
                logger.info(f"  Syntax check passed for {step.target_file}")
            except SyntaxError as e:
                # Rollback on syntax error
                logger.error(f"  SYNTAX ERROR in generated code for {step.target_file}: {e}")
                logger.error(f"  First 300 chars of generated code:\n{code_changes[:300]}")
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
                    "new_lines": len(code_changes.splitlines()),
                },
                metadata={"original_content": original},
            )

        except Exception as e:
            return ToolResult(success=False, error=f"File write failed: {e}")

    def _generate_code(self, step: RefactoringStep) -> str | None:
        """Ask the LLM to generate refactored code for a modify_code step."""
        target = Path(step.target_file)

        # Read current file content
        file_content = "(new file)"
        if target.exists():
            try:
                file_content = target.read_text()
            except Exception as e:
                logger.warning(f"Could not read {step.target_file}: {e}")

        prompt = CODE_GEN_PROMPT.format(
            description=step.description,
            file_path=step.target_file,
            file_content=file_content,
        )

        messages = [
            SystemMessage(content=CODE_GEN_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ]

        try:
            response = self._llm.invoke(messages)
            raw = response.content
            logger.debug(f"  Raw LLM response ({len(raw)} chars): {raw[:200]}...")
            code = self._clean_code_response(raw)
            logger.info(f"  LLM generated {len(code.splitlines())} lines for {step.target_file}")
            return code

        except Exception as e:
            logger.error(f"  LLM code generation failed: {e}")
            return None

    @staticmethod
    def _clean_code_response(raw: str) -> str:
        """Strip markdown fences and prose from LLM code output."""
        import re

        text = raw.strip()

        # If the response contains a fenced code block, extract just the code
        fence_match = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.DOTALL)
        if fence_match:
            return fence_match.group(1).strip()

        # If it starts with a fence but doesn't close properly, strip the opening
        if text.startswith("```"):
            lines = text.splitlines()
            lines = lines[1:]  # drop ```python
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            return "\n".join(lines).strip()

        # If there's prose before the code, try to find where Python starts
        # (look for common first-line patterns: import, from, class, def, #)
        lines = text.splitlines()
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped and (
                stripped.startswith(("import ", "from ", "class ", "def ", "#", '"""', "'''"))
            ):
                return "\n".join(lines[i:]).strip()

        return text
