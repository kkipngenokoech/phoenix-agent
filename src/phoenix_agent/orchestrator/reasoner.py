"""REASON phase - LLM analysis of code for refactoring opportunities."""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from phoenix_agent.llm_json import extract_json

from phoenix_agent.models import (
    ObservationResult,
    ReasoningAnalysis,
    RiskLevel,
)

logger = logging.getLogger(__name__)

REASONING_SYSTEM_PROMPT = """You are an expert code architect specializing in refactoring.
You analyze codebases to identify structural and architectural issues, then recommend
specific refactoring approaches with detailed risk assessments.

Always respond with valid JSON matching this exact schema:
{
    "root_cause": "Description of the core structural/architectural issue",
    "approach": "Specific refactoring approach to take (e.g., Extract Class, Extract Method)",
    "risk_assessment": "LOW" | "MEDIUM" | "HIGH",
    "expected_impact": "Description of expected improvements",
    "files_to_modify": ["list", "of", "file", "paths"],
    "rationale": "Detailed explanation of why this approach is recommended"
}"""

REASONING_PROMPT = """Analyze the following codebase for refactoring opportunities.

## Developer Request
{request}

## Codebase Observation
### Files
{files}

### Code Metrics
{metrics}

### Code Smells Detected
{smells}

### Git Status
Branch: {branch}
Uncommitted changes: {uncommitted}

Provide your analysis as JSON with: root_cause, approach, risk_assessment (LOW/MEDIUM/HIGH),
expected_impact, files_to_modify, and rationale."""


class Reasoner:
    def __init__(self, llm: Any) -> None:
        self._llm = llm

    def reason(self, observation: ObservationResult, request: str) -> ReasoningAnalysis:
        logger.info("REASON: analyzing code for refactoring opportunities")

        # Format observation data for the LLM
        files_text = "\n".join(f"- {f}" for f in observation.snapshot.files[:20])
        metrics_text = self._format_metrics(observation.file_metrics)
        smells_text = self._format_smells(observation)

        prompt = REASONING_PROMPT.format(
            request=request,
            files=files_text or "No files found",
            metrics=metrics_text or "No metrics available",
            smells=smells_text or "No code smells detected",
            branch=observation.snapshot.current_branch or "unknown",
            uncommitted=observation.snapshot.has_uncommitted_changes,
        )

        messages = [
            SystemMessage(content=REASONING_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ]

        try:
            response = self._llm.invoke(messages)
            analysis = self._parse_response(response.content)
            logger.info(f"REASON complete: risk={analysis.risk_assessment.value}, "
                        f"files={len(analysis.files_to_modify)}")
            return analysis
        except Exception as e:
            logger.error(f"Reasoning failed: {e}")
            return ReasoningAnalysis(
                root_cause="Analysis failed - unable to complete reasoning",
                approach="manual_review",
                risk_assessment=RiskLevel.HIGH,
                expected_impact="Unknown",
                rationale=f"Error during reasoning: {e}",
            )

    def _parse_response(self, content: str) -> ReasoningAnalysis:
        data = extract_json(content)

        risk = data.get("risk_assessment", "MEDIUM").upper()
        if risk not in ("LOW", "MEDIUM", "HIGH"):
            risk = "MEDIUM"

        return ReasoningAnalysis(
            root_cause=data.get("root_cause", ""),
            approach=data.get("approach", ""),
            risk_assessment=RiskLevel(risk),
            expected_impact=data.get("expected_impact", ""),
            files_to_modify=data.get("files_to_modify", []),
            rationale=data.get("rationale", ""),
        )

    def _format_metrics(self, metrics: list) -> str:
        if not metrics:
            return ""
        lines = []
        for m in metrics:
            lines.append(
                f"- {m.file_path}: {m.lines_of_code} LOC, "
                f"complexity={m.cyclomatic_complexity}, "
                f"functions={m.function_count}, classes={m.class_count}, "
                f"max_nesting={m.max_nesting_depth}"
            )
        return "\n".join(lines)

    def _format_smells(self, observation: ObservationResult) -> str:
        # Code smells are embedded in the AST results, summarize from metrics
        lines = []
        for m in observation.file_metrics:
            issues = []
            if m.cyclomatic_complexity > 20:
                issues.append(f"high complexity ({m.cyclomatic_complexity})")
            if m.max_nesting_depth > 4:
                issues.append(f"deep nesting (depth {m.max_nesting_depth})")
            if m.function_count > 15:
                issues.append(f"many functions ({m.function_count})")
            if issues:
                lines.append(f"- {m.file_path}: {', '.join(issues)}")
        return "\n".join(lines)
