"""LeadAgent - orchestrates sub-agents in the crew-style multi-agent system.

Replaces the sequential _run_iteration logic with:
1. AnalyzerAgent (OBSERVE + REASON) — sequential
2. StrategistAgent (PLAN + DECIDE) — sequential
3. Human approval gate — blocking (stays in LeadAgent)
4. CoderAgents — parse_code sequential, modify_code PARALLEL
5. TesterAgent (VERIFY) — sequential
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Optional

from phoenix_agent.config import PhoenixConfig
from phoenix_agent.crew.analyzer_agent import AnalyzerAgent
from phoenix_agent.crew.coder_agent import CoderAgent
from phoenix_agent.crew.strategist_agent import StrategistAgent
from phoenix_agent.crew.task import Task, TaskType
from phoenix_agent.crew.tester_agent import TesterAgent
from phoenix_agent.models import (
    Decision,
    ObservationResult,
    ReasoningAnalysis,
    RefactoringPlan,
    RefactoringStep,
    SessionState,
    VerificationReport,
)
from phoenix_agent.orchestrator.arbiter import Arbiter
from phoenix_agent.orchestrator.observer import Observer
from phoenix_agent.orchestrator.planner import Planner
from phoenix_agent.orchestrator.reasoner import Reasoner
from phoenix_agent.orchestrator.verifier import Verifier
from phoenix_agent.provider import create_llm
from phoenix_agent.tools.ast_parser import ASTParserTool
from phoenix_agent.tools.base import ToolResult
from phoenix_agent.tools.registry import ToolRegistry
from phoenix_agent.tools.test_runner import TestRunnerTool

logger = logging.getLogger(__name__)


class LeadAgent:
    """Orchestrator that delegates to specialized sub-agents."""

    def __init__(
        self,
        config: PhoenixConfig,
        observer: Observer,
        reasoner: Reasoner,
        planner: Planner,
        arbiter: Arbiter,
        verifier: Verifier,
        tool_registry: ToolRegistry,
        ast_parser: ASTParserTool,
        llm: Any,
        emit: Optional[Callable[..., Any]] = None,
    ) -> None:
        self._config = config
        self._llm = llm
        self._ast_parser = ast_parser
        self._tool_registry = tool_registry
        self._emit = emit or (lambda *a, **kw: None)
        self._max_coder_agents = getattr(config.agent, "max_coder_agents", 4)
        self._last_test_failures: list[dict] = []

        # Build sub-agents — they share the emit callback
        self._analyzer = AnalyzerAgent(observer, reasoner, emit=self._emit)
        self._strategist = StrategistAgent(planner, arbiter, emit=self._emit)
        self._verifier = verifier  # Used directly by TesterAgent per call

    def set_emit(self, emit: Callable[..., Any]) -> None:
        """Update the emit callback (set after construction by PhoenixAgent.run)."""
        self._emit = emit
        self._analyzer._emit = emit
        self._strategist._emit = emit

    def run_iteration(
        self,
        session: SessionState,
        iteration: int,
        request: str,
        target_path: str,
    ) -> tuple[
        ObservationResult | None,
        ReasoningAnalysis | None,
        RefactoringPlan | None,
        Decision | None,
        list[dict] | None,
        VerificationReport | None,
    ]:
        """Run one iteration through the sub-agent crew.

        Returns a tuple of (observation, analysis, plan, decision, step_results, report).
        Any element may be None if that phase wasn't reached.
        """
        emit = self._emit

        # ---- 1. ANALYZE (OBSERVE + REASON) ----
        analyze_task = Task(
            task_type=TaskType.ANALYZE,
            payload={
                "session_id": session.session_id,
                "target_path": target_path,
                "request": request,
                "iteration": iteration,
            },
        )
        analyze_result = self._analyzer.execute(analyze_task)

        if not analyze_result.success:
            logger.warning(f"Analysis failed: {analyze_result.error}")
            return None, None, None, None, None, None

        observation: ObservationResult = analyze_result.data["observation"]
        analysis: ReasoningAnalysis = analyze_result.data["analysis"]

        # ---- 2. STRATEGIZE (PLAN + DECIDE) ----
        strategize_task = Task(
            task_type=TaskType.STRATEGIZE,
            payload={
                "observation": observation,
                "analysis": analysis,
                "last_test_failure": session.last_test_failure,
                "project_path": target_path,
                "iteration": iteration,
            },
        )
        strategize_result = self._strategist.execute(strategize_task)

        if not strategize_result.success:
            logger.warning(f"Strategy failed: {strategize_result.error}")
            return observation, analysis, None, None, None, None

        plan: RefactoringPlan = strategize_result.data["plan"]
        decision: Decision = strategize_result.data["decision"]

        # NOTE: Human approval gate is handled by PhoenixAgent, not here.
        # We return plan + decision and let PhoenixAgent handle approval flow.

        return observation, analysis, plan, decision, None, None

    def execute_coding_tasks(
        self,
        plan: RefactoringPlan,
        target_path: str,
        iteration: int,
    ) -> list[dict]:
        """Execute all coding steps: parse_code sequential, modify_code in parallel.

        Returns list of step_result dicts (same format as Executor.execute).
        """
        emit = self._emit
        emit("phase_update", phase="ACT", data={"status": "executing", "total_steps": len(plan.steps)}, iteration=iteration)

        results: list[dict] = []
        total_steps = len(plan.steps)

        # Separate steps by type
        parse_steps = [s for s in plan.steps if s.action == "parse_code"]
        modify_steps = [s for s in plan.steps if s.action == "modify_code"]
        test_steps = [s for s in plan.steps if s.action == "run_tests"]

        # Split modify_code into source files vs test files.
        # Test files MUST run AFTER source files so they see the updated code.
        from phoenix_agent.crew.code_gen import is_test_file
        source_modify = [s for s in modify_steps if not is_test_file(s.target_file)]
        test_modify = [s for s in modify_steps if is_test_file(s.target_file)]

        # 1. parse_code steps — sequential, fast, no LLM
        for step in parse_steps:
            result = self._run_single_coder(step, iteration, total_steps)
            results.append(result)

        # 2a. Source file modify_code — PARALLEL (wave 1)
        if source_modify:
            logger.info(f"Wave 1: {len(source_modify)} source file(s) in parallel")
            parallel_results = self._run_parallel_coders(source_modify, iteration, total_steps)
            for r in parallel_results:
                results.append(r)
                if r.get("critical"):
                    logger.error(f"Critical failure in step {r['step_id']}")
                    break

        # 2b. Test file modify_code — PARALLEL (wave 2, after source files are written)
        critical = any(r.get("critical") for r in results)
        if test_modify and not critical:
            logger.info(f"Wave 2: {len(test_modify)} test file(s) in parallel")
            test_results = self._run_parallel_coders(test_modify, iteration, total_steps)
            for r in test_results:
                results.append(r)

        # 3. run_tests steps — sequential via test_runner tool
        critical = any(r.get("critical") for r in results)
        if not critical:
            for step in test_steps:
                tr = self._tool_registry.execute(
                    "test_runner",
                    project_path=target_path,
                    test_scope="unit",
                    coverage_required=True,
                )
                results.append({
                    "step_id": step.step_id,
                    "action": "run_tests",
                    "target_file": "",
                    "success": tr.success,
                    "output": tr.output,
                    "error": tr.error,
                    "execution_time_ms": tr.execution_time_ms,
                    "metadata": tr.metadata,
                })

        emit("phase_update", phase="ACT_RESULT", data=results, iteration=iteration)
        logger.info(f"ACT complete: {sum(1 for r in results if r.get('success'))}/{len(results)} steps succeeded")
        return results

    def run_verification(
        self,
        step_results: list[dict],
        decision: Decision,
        project_path: str,
        metrics_before: list,
        iteration: int,
    ) -> VerificationReport:
        """Run the TesterAgent for VERIFY phase."""
        tester = TesterAgent(self._verifier, emit=self._emit)
        task = Task(
            task_type=TaskType.TEST,
            payload={
                "step_results": step_results,
                "validation_level": decision.validation_level,
                "project_path": project_path,
                "metrics_before": metrics_before,
                "iteration": iteration,
            },
        )
        result = tester.execute(task)
        return result.data["report"]

    def set_test_failures(self, failures: list[dict]) -> None:
        """Store test failures for the next coding iteration."""
        self._last_test_failures = failures

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_single_coder(
        self, step: RefactoringStep, iteration: int, total_steps: int,
    ) -> dict:
        """Run a single coding step synchronously."""
        coder = CoderAgent(
            llm=self._llm,
            ast_parser=self._ast_parser,
            test_failures=self._last_test_failures,
            emit=self._emit,
        )
        task = Task(
            task_type=TaskType.CODE,
            payload={"step": step, "iteration": iteration, "total_steps": total_steps},
        )
        result = coder.execute(task)
        return result.data

    def _run_parallel_coders(
        self,
        steps: list[RefactoringStep],
        iteration: int,
        total_steps: int,
    ) -> list[dict]:
        """Run multiple modify_code steps in parallel, each with own LLM."""
        max_workers = min(len(steps), self._max_coder_agents)
        logger.info(f"Running {len(steps)} modify_code steps in parallel (max_workers={max_workers})")

        results_map: dict[int, dict] = {}

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {}
            for step in steps:
                # Each CoderAgent gets its own LLM instance for thread safety
                coder_llm = create_llm(self._config)
                coder = CoderAgent(
                    llm=coder_llm,
                    ast_parser=self._ast_parser,
                    test_failures=self._last_test_failures,
                    emit=self._emit,
                )
                task = Task(
                    task_type=TaskType.CODE,
                    payload={"step": step, "iteration": iteration, "total_steps": total_steps},
                )
                future = pool.submit(coder.execute, task)
                futures[future] = step.step_id

            for future in as_completed(futures):
                step_id = futures[future]
                try:
                    result = future.result()
                    results_map[step_id] = result.data
                except Exception as e:
                    logger.error(f"CoderAgent for step {step_id} raised: {e}")
                    results_map[step_id] = {
                        "step_id": step_id,
                        "action": "modify_code",
                        "success": False,
                        "error": str(e),
                        "critical": True,
                    }

        # Return in original step order
        return [results_map[s.step_id] for s in steps if s.step_id in results_map]
