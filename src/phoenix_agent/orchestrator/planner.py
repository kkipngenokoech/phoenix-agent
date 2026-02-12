"""PLAN phase - generate ordered refactoring steps with rollback strategy."""

from __future__ import annotations

import logging
from typing import Any

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
- "modify_code": Describe what code changes to make (the executor will generate the code)
- "run_tests": Run the test suite

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
            "description": "Extract the authentication methods into a new AuthService class"
        },
        {
            "step_id": 3,
            "action": "run_tests",
            "target_file": "",
            "description": "Run tests to validate changes"
        }
    ],
    "rollback_strategy": "git reset --hard"
}

Rules:
- Do NOT include code_changes — just describe what to change in "description"
- Include run_tests steps after modifications
- Keep to 3-8 steps
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

Respond with JSON only."""


class Planner:
    def __init__(self, llm: Any) -> None:
        self._llm = llm

    def plan(
        self, analysis: ReasoningAnalysis, observation: ObservationResult
    ) -> RefactoringPlan:
        logger.info("PLAN: generating refactoring steps")

        code_content = self._read_target_files(analysis.files_to_modify)

        prompt = PLANNING_PROMPT.format(
            approach=analysis.approach,
            root_cause=analysis.root_cause,
            files="\n".join(f"- {f}" for f in analysis.files_to_modify),
            code_content=code_content,
            expected_impact=analysis.expected_impact,
        )

        messages = [
            SystemMessage(content=PLANNING_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ]

        try:
            response = self._llm.invoke(messages)
            raw = response.content
            logger.debug(f"PLAN raw LLM response ({len(raw)} chars): {raw[:500]}")
            plan = self._parse_response(raw)
            if plan.steps:
                logger.info(f"PLAN complete: {len(plan.steps)} steps")
                return plan
            # LLM returned JSON but with empty/missing steps
            logger.warning("PLAN: LLM returned no steps, generating default plan")
        except Exception as e:
            logger.error(f"Planning failed: {e}")
            logger.debug(f"PLAN: raw content was: {response.content[:500] if 'response' in dir() else 'N/A'}")

        # Fallback: generate a default plan from the analysis
        return self._default_plan(analysis)

    def _parse_response(self, content: str) -> RefactoringPlan:
        data = extract_json(content)

        steps = []
        for s in data.get("steps", []):
            steps.append(RefactoringStep(
                step_id=s.get("step_id", len(steps) + 1),
                action=s.get("action", "parse_code"),
                target_file=s.get("target_file", ""),
                description=s.get("description", ""),
                dependencies=s.get("dependencies", []),
                code_changes=s.get("code_changes"),
            ))

        return RefactoringPlan(
            steps=steps,
            rollback_strategy=data.get("rollback_strategy", "git reset --hard"),
            validation_checkpoints=data.get("validation_checkpoints", []),
        )

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
