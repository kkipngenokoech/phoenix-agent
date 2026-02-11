"""DECIDE phase - risk scoring and approval decisions."""

from __future__ import annotations

import logging

from phoenix_agent.config import PhoenixConfig
from phoenix_agent.models import (
    Decision,
    ReasoningAnalysis,
    RefactoringPlan,
    RiskLevel,
    RiskScore,
    ValidationLevel,
)

logger = logging.getLogger(__name__)


class Arbiter:
    def __init__(self, config: PhoenixConfig) -> None:
        self._high_threshold = config.agent.high_risk_threshold
        self._medium_threshold = config.agent.medium_risk_threshold

    def decide(
        self,
        plan: RefactoringPlan,
        analysis: ReasoningAnalysis,
        test_coverage_pct: float = 0.0,
    ) -> Decision:
        logger.info("DECIDE: calculating risk and determining approval")

        if not plan.steps:
            return Decision(
                approved=False,
                requires_human=False,
                reason="No refactoring steps generated - plan is empty",
            )

        # Calculate risk score
        risk = RiskScore(
            llm_risk=analysis.risk_assessment,
            files_affected=len(analysis.files_to_modify),
            test_coverage_pct=test_coverage_pct,
            expected_complexity_change=0.0,
        )
        score = risk.calculate()

        # Map plan steps to tools
        tool_mapping = {}
        for step in plan.steps:
            if step.action == "parse_code":
                tool_mapping[str(step.step_id)] = "ast_parser"
            elif step.action == "modify_code":
                tool_mapping[str(step.step_id)] = "code_modifier"
            elif step.action == "run_tests":
                tool_mapping[str(step.step_id)] = "test_runner"

        # Decision logic
        if score > self._high_threshold:
            logger.info(f"HIGH risk ({score:.1f}) - requires human approval")
            return Decision(
                approved=False,
                validation_level=ValidationLevel.EXTRA,
                tool_mapping=tool_mapping,
                requires_human=True,
                risk_score=risk,
                reason=f"Risk score {score:.1f} exceeds high threshold {self._high_threshold}",
            )
        elif score > self._medium_threshold:
            logger.info(f"MEDIUM risk ({score:.1f}) - extra validation required")
            return Decision(
                approved=True,
                validation_level=ValidationLevel.EXTRA,
                tool_mapping=tool_mapping,
                requires_human=False,
                risk_score=risk,
                reason=f"Risk score {score:.1f} - proceeding with extra validation",
            )
        else:
            logger.info(f"LOW risk ({score:.1f}) - standard validation")
            return Decision(
                approved=True,
                validation_level=ValidationLevel.STANDARD,
                tool_mapping=tool_mapping,
                requires_human=False,
                risk_score=risk,
                reason=f"Risk score {score:.1f} - proceeding with standard validation",
            )
