"""PLAN phase - generate ordered refactoring steps with rollback strategy."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from phoenix_agent.llm_json import extract_json
from phoenix_agent.models import (
    ObservationResult,
    ReasoningAnalysis,
    RefactoringPlan,
    RefactoringStep,
)

logger = logging.getLogger(__name__)

# Simplified prompt — do NOT ask for code_changes here.
# Embedding Python code inside JSON strings is too error-prone for local models.
# Actual code generation happens in the executor phase.
PLANNING_SYSTEM_PROMPT = """You are an expert refactoring planner. Given a code analysis,
create an ordered plan of steps.

Each step has an action:
- "parse_code": Analyze a file's structure
- "modify_code": Describe ALL code changes to make to a file in ONE step (the executor will generate the code)
- "run_tests": Run the test suite

CRITICAL: Use exactly ONE "modify_code" step per file. Each modify_code step COMPLETELY rewrites
the file, so multiple modify_code steps on the same file will overwrite each other. Put ALL
changes for a file into a single step with a comprehensive description.

Respond with ONLY valid JSON, no other text:
{
    "steps": [
        {
            "step_id": 1,
            "action": "parse_code",
            "target_file": "path/to/file.py",
            "description": "Analyze the current structure"
        },
        {
            "step_id": 2,
            "action": "modify_code",
            "target_file": "path/to/file.py",
            "description": "Refactor the entire file: extract AuthService class for authentication, UserValidator for validation, UserRepository for persistence. Create a UserService facade that coordinates between the extracted classes using dependency injection. Keep all classes in the same file."
        },
        {
            "step_id": 3,
            "action": "modify_code",
            "target_file": "path/to/test_file.py",
            "description": "Update tests to use the new class structure with correct imports and fixtures"
        },
        {
            "step_id": 4,
            "action": "run_tests",
            "target_file": "",
            "description": "Run tests to validate changes"
        }
    ],
    "rollback_strategy": "git reset --hard"
}

Rules:
- Do NOT include code_changes — just describe what to change in "description"
- Use ONE modify_code step per file with a comprehensive description of ALL changes
- After modifying source files, add ONE modify_code step to update the test file
- End with exactly ONE "run_tests" step
- Keep to 3-5 steps total. Be concise.
- Respond with JSON only"""

PLANNING_PROMPT = """Create a refactoring plan.

## Approach
{approach}

## Root Cause
{root_cause}

## Files to Modify
{files}

## Current Code
{code_content}

## Expected Impact
{expected_impact}

## Last Test Failure
{test_failure_summary}

Respond with JSON only."""


class Planner:
    def __init__(self, llm: Any) -> None:
        self._llm = llm

    def plan(
        self,
        analysis: ReasoningAnalysis,
        observation: ObservationResult,
        last_test_failure: Optional[Any] = None,
        project_path: str = "",
    ) -> RefactoringPlan:
        logger.info("PLAN: generating refactoring steps")

        code_content = self._read_target_files(analysis.files_to_modify)
        
        if last_test_failure:
            failures = [f"- {f.test_name}: {f.error_message}" for f in last_test_failure.failures]
            test_failure_summary = (
                f"The last attempt failed with these test errors:\n"
                + "\n".join(failures)
                + "\nYour new plan MUST fix these tests."
            )
        else:
            test_failure_summary = "None."

        prompt = PLANNING_PROMPT.format(
            approach=analysis.approach,
            root_cause=analysis.root_cause,
            files="\n".join(f"- {f}" for f in analysis.files_to_modify),
            code_content=code_content,
            expected_impact=analysis.expected_impact,
            test_failure_summary=test_failure_summary,
        )

        messages = [
            SystemMessage(content=PLANNING_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ]

        try:
            response = self._llm.invoke(messages)
            raw = response.content
            logger.debug(f"PLAN raw LLM response ({len(raw)} chars): {raw[:500]}")
            plan = self._parse_response(raw, project_path, analysis.files_to_modify)
            if not plan.steps:
                # LLM returned JSON but with empty/missing steps
                logger.warning("PLAN: LLM returned no steps, generating default plan")
                plan = self._default_plan(analysis)
        except Exception as e:
            logger.error(f"Planning failed: {e}")
            logger.debug(f"PLAN: raw content was: {response.content[:500] if 'response' in dir() else 'N/A'}")
            plan = self._default_plan(analysis)


        # Strip any generate_tests the LLM may have included — we handle this
        plan.steps = [s for s in plan.steps if s.action != "generate_tests"]

        # Consolidate multiple modify_code steps for the same file into one
        plan.steps = self._consolidate_modify_steps(plan.steps)

        # Ensure there's exactly one run_tests at the end
        has_run_tests = any(s.action == "run_tests" for s in plan.steps)
        if not has_run_tests:
            plan.steps.append(RefactoringStep(
                step_id=0, action="run_tests", target_file="",
                description="Run the complete test suite to validate changes",
            ))

        # Renumber all steps
        for i, step in enumerate(plan.steps):
            step.step_id = i + 1

        if plan.steps:
            logger.info(f"PLAN complete: {len(plan.steps)} steps")
        return plan

    def _parse_response(
        self, content: str, project_path: str = "", known_files: list[str] | None = None,
    ) -> RefactoringPlan:
        data = extract_json(content)

        raw_steps = data.get("steps", [])
        validated_steps = []

        # Build a lookup of known file basenames → absolute paths
        # so we can resolve LLM-generated relative/hallucinated paths
        known_map: dict[str, str] = {}
        for fp in (known_files or []):
            known_map[Path(fp).name] = fp
            # Also map relative path from project root
            try:
                rel = str(Path(fp).relative_to(project_path))
                known_map[rel] = fp
            except ValueError:
                pass

        # Actions that require an existing file path
        existing_file_actions = ["parse_code", "generate_tests"]

        for s in raw_steps:
            action = s.get("action")
            target_file = s.get("target_file", "")

            # Try to resolve the path the LLM gave us
            target_file = self._resolve_file_path(target_file, project_path, known_map)

            if action in existing_file_actions:
                if not target_file or not Path(target_file).is_file():
                    logger.warning(
                        f"Planner LLM generated step with invalid target_file ('{s.get('target_file')}') "
                        f"for action '{action}'. Discarding step."
                    )
                    continue

            if action == "modify_code" and not target_file:
                logger.warning("Planner LLM generated modify_code step with no target_file. Discarding.")
                continue

            validated_steps.append(RefactoringStep(
                step_id=s.get("step_id", len(validated_steps) + 1),
                action=action,
                target_file=target_file,
                description=s.get("description", ""),
                dependencies=s.get("dependencies", []),
                code_changes=s.get("code_changes"),
            ))

        # Renumber step_ids to ensure they are sequential
        for i, step in enumerate(validated_steps):
            step.step_id = i + 1

        return RefactoringPlan(
            steps=validated_steps,
            rollback_strategy=data.get("rollback_strategy", "git reset --hard"),
            validation_checkpoints=data.get("validation_checkpoints", []),
        )

    @staticmethod
    def _resolve_file_path(
        target_file: str, project_path: str, known_map: dict[str, str]
    ) -> str:
        """Try to resolve an LLM-generated file path to an actual path.

        Strategy:
        1. If it's already absolute and exists, use it.
        2. If it matches a known file by basename or relative path, use that.
        3. If it's relative, resolve against the project path.
        4. Otherwise return as-is (for modify_code creating new files).
        """
        if not target_file:
            return target_file

        p = Path(target_file)

        # Already absolute and exists
        if p.is_absolute() and p.exists():
            return target_file

        # Match by exact relative path or basename in known files
        if target_file in known_map:
            return known_map[target_file]
        if p.name in known_map:
            return known_map[p.name]

        # Resolve relative against project path
        if project_path:
            resolved = Path(project_path) / target_file
            if resolved.exists():
                return str(resolved)

        # For modify_code (new files), resolve against project path anyway
        if project_path:
            return str(Path(project_path) / target_file)

        return target_file

    @staticmethod
    def _consolidate_modify_steps(steps: list[RefactoringStep]) -> list[RefactoringStep]:
        """Merge multiple modify_code steps for the same file into one.

        Each modify_code step rewrites the entire file, so having multiple
        steps for the same target causes later steps to overwrite earlier ones.
        """
        from collections import OrderedDict

        consolidated: list[RefactoringStep] = []
        # Track modify_code steps per file, preserving order
        modify_by_file: OrderedDict[str, RefactoringStep] = OrderedDict()

        for step in steps:
            if step.action == "modify_code" and step.target_file:
                key = step.target_file
                if key in modify_by_file:
                    # Merge descriptions
                    existing = modify_by_file[key]
                    existing.description += f". Additionally: {step.description}"
                    logger.info(f"PLAN: Merged duplicate modify_code for {Path(key).name}")
                else:
                    modify_by_file[key] = step
            else:
                consolidated.append(step)

        # Insert all modify_code steps (in original order) after any parse_code steps
        # but before run_tests
        insert_idx = 0
        for i, s in enumerate(consolidated):
            if s.action == "parse_code":
                insert_idx = i + 1

        for step in modify_by_file.values():
            consolidated.insert(insert_idx, step)
            insert_idx += 1

        return consolidated

    def _default_plan(self, analysis: ReasoningAnalysis) -> RefactoringPlan:
        """Generate a sensible default plan when LLM parsing fails."""
        steps = []
        step_id = 1

        for fp in analysis.files_to_modify:
            steps.append(RefactoringStep(
                step_id=step_id,
                action="parse_code",
                target_file=fp,
                description=f"Analyze structure of {fp}",
            ))
            step_id += 1

            steps.append(RefactoringStep(
                step_id=step_id,
                action="modify_code",
                target_file=fp,
                description=f"Apply refactoring: {analysis.approach}. {analysis.root_cause}",
            ))
            step_id += 1

        steps.append(RefactoringStep(
            step_id=step_id,
            action="run_tests",
            target_file="",
            description="Run test suite to validate all changes",
        ))

        logger.info(f"PLAN (default): {len(steps)} steps for {len(analysis.files_to_modify)} files")
        return RefactoringPlan(
            steps=steps,
            rollback_strategy="git reset --hard to original commit",
        )

    def _read_target_files(self, file_paths: list[str]) -> str:
        sections = []
        for fp in file_paths:
            try:
                with open(fp) as f:
                    content = f.read()
                sections.append(f"### {fp}\n```python\n{content}\n```")
            except FileNotFoundError:
                sections.append(f"### {fp}\n(file not found)")
            except Exception as e:
                sections.append(f"### {fp}\n(error reading: {e})")
        return "\n\n".join(sections)
