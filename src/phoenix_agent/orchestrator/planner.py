"""PLAN phase - generate ordered refactoring steps with rollback strategy."""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from phoenix_agent.models import (
    ObservationResult,
    ReasoningAnalysis,
    RefactoringPlan,
    RefactoringStep,
)

logger = logging.getLogger(__name__)

PLANNING_SYSTEM_PROMPT = """You are an expert refactoring planner. Given a code analysis and
refactoring approach, create a detailed, ordered plan of steps to execute the refactoring.

Each step should be a concrete action that maps to one of these tool actions:
- "parse_code": Analyze a specific file's structure
- "modify_code": Make specific code changes to a file (include the complete new file content)
- "run_tests": Execute the test suite to validate changes

Respond with valid JSON matching this schema:
{
    "steps": [
        {
            "step_id": 1,
            "action": "parse_code" | "modify_code" | "run_tests",
            "target_file": "path/to/file.py",
            "description": "What this step does",
            "dependencies": [],
            "code_changes": "Complete new file content (only for modify_code)"
        }
    ],
    "rollback_strategy": "How to undo these changes if they fail",
    "validation_checkpoints": [3, 5]
}

CRITICAL RULES:
- For "modify_code" steps, code_changes MUST contain the COMPLETE new file content
- Preserve ALL existing functionality - refactoring changes structure, not behavior
- Include "run_tests" steps after modifications to validate
- Keep step count reasonable (typically 5-15 steps)
- Each step should be independently verifiable"""

PLANNING_PROMPT = """Create a refactoring plan based on this analysis.

## Refactoring Approach
{approach}

## Root Cause
{root_cause}

## Files to Modify
{files}

## Current Code
{code_content}

## Expected Impact
{expected_impact}

Generate an ordered list of steps to execute this refactoring safely."""


class Planner:
    def __init__(self, llm: Any) -> None:
        self._llm = llm

    def plan(
        self, analysis: ReasoningAnalysis, observation: ObservationResult
    ) -> RefactoringPlan:
        logger.info("PLAN: generating refactoring steps")

        # Read the actual file contents for context
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
            plan = self._parse_response(response.content)
            logger.info(f"PLAN complete: {len(plan.steps)} steps")
            return plan
        except Exception as e:
            logger.error(f"Planning failed: {e}")
            return RefactoringPlan(
                steps=[],
                rollback_strategy="git reset --hard to original commit",
            )

    def _parse_response(self, content: str) -> RefactoringPlan:
        text = content.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        data = json.loads(text)

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
