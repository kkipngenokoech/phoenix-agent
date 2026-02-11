"""
Phoenix Agent - Streamlit Web Interface

Run with: streamlit run app.py
"""

import os
import sys
import json
import time
from pathlib import Path

src_path = Path(__file__).parent / "src"
if src_path.exists() and str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

import streamlit as st

st.set_page_config(
    page_title="Phoenix Agent",
    page_icon="🔥",
    layout="wide",
)

# Custom CSS
st.markdown("""
<style>
.main-header {
    background: linear-gradient(90deg, #ff6b35 0%, #f7c948 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-size: 2.5rem;
    font-weight: 700;
}
.phase-badge {
    display: inline-block;
    padding: 2px 12px;
    border-radius: 12px;
    font-size: 0.8rem;
    font-weight: 600;
    margin: 2px;
}
.phase-observe { background: #e3f2fd; color: #1565c0; }
.phase-reason { background: #f3e5f5; color: #7b1fa2; }
.phase-plan { background: #e8f5e9; color: #2e7d32; }
.phase-decide { background: #fff3e0; color: #e65100; }
.phase-act { background: #fce4ec; color: #c62828; }
.phase-verify { background: #e0f7fa; color: #00695c; }
.phase-update { background: #f1f8e9; color: #33691e; }
.metric-card {
    background: #f8f9fa;
    border-radius: 8px;
    padding: 16px;
    margin: 4px 0;
    border-left: 4px solid #ff6b35;
}
</style>
""", unsafe_allow_html=True)


def init_session():
    if "agent" not in st.session_state:
        st.session_state.agent = None
    if "result" not in st.session_state:
        st.session_state.result = None
    if "running" not in st.session_state:
        st.session_state.running = False


def load_agent():
    from phoenix_agent.agent import PhoenixAgent
    from phoenix_agent.config import PhoenixConfig

    config = PhoenixConfig.from_env()
    st.session_state.agent = PhoenixAgent(config)
    return st.session_state.agent


def run_analysis_only(target_path):
    """Run just the AST analysis without the full agent loop."""
    from phoenix_agent.tools.ast_parser import ASTParserTool
    from phoenix_agent.tools.test_runner import TestRunnerTool

    parser = ASTParserTool()
    runner = TestRunnerTool()

    # Find Python files
    py_files = sorted(str(p) for p in Path(target_path).rglob("*.py")
                      if "__pycache__" not in str(p) and "test_" not in p.name and "/tests/" not in str(p))

    ast_result = parser.execute(file_paths=py_files)
    test_result = runner.execute(project_path=target_path, coverage_required=False)

    return ast_result, test_result


def display_ast_results(result):
    if not result.success:
        st.error(f"Analysis failed: {result.error}")
        return

    for pf in result.output.get("parsed_files", []):
        fname = pf["file_path"].split("/")[-1]
        m = pf["metrics"]
        smells = pf.get("code_smells", [])

        with st.expander(f"📄 {fname} — complexity: {m['cyclomatic_complexity']}, smells: {len(smells)}", expanded=True):
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Lines of Code", m["lines_of_code"])
            col2.metric("Cyclomatic Complexity", m["cyclomatic_complexity"])
            col3.metric("Functions", m["function_count"])
            col4.metric("Max Nesting", m["max_nesting_depth"])

            if smells:
                st.markdown("**Code Smells:**")
                for smell in smells:
                    severity = smell.get("severity", "low")
                    icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(severity, "⚪")
                    loc = smell.get("location", {})
                    line = loc.get("start_line", "?")
                    st.markdown(f"- {icon} **{smell['type']}** (line {line}): {smell.get('description', '')}")


def display_test_results(result):
    if not result.success:
        st.error(f"Tests failed: {result.error}")
        return

    summary = result.output.get("summary", {})
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total", summary.get("total", 0))
    col2.metric("Passed", summary.get("passed", 0))
    col3.metric("Failed", summary.get("failed", 0))
    col4.metric("Duration", f"{summary.get('duration_seconds', 0):.2f}s")


def display_agent_result(result):
    status = result.get("status", "unknown")

    if status == "success":
        st.success("Refactoring completed successfully!")

        col1, col2, col3 = st.columns(3)
        col1.metric("Session", result.get("session_id", ""))
        col2.metric("Duration", f"{result.get('duration_seconds', 0):.1f}s")
        col3.metric("Branch", result.get("branch", "N/A"))

        if result.get("pr_url"):
            st.markdown(f"**Pull Request:** [{result['pr_url']}]({result['pr_url']})")

        # Metrics comparison
        before = result.get("metrics_before", {})
        after = result.get("metrics_after", {})
        if before or after:
            st.markdown("### Complexity Changes")
            cols = st.columns(len(before) or 1)
            for i, f in enumerate(sorted(set(before.keys()) | set(after.keys()))):
                b = before.get(f, 0)
                a = after.get(f, 0)
                delta = a - b
                cols[i % len(cols)].metric(
                    f.split("/")[-1],
                    a,
                    delta=delta,
                    delta_color="inverse",
                )

    elif status == "awaiting_approval":
        st.warning("Awaiting human approval")
        st.json(result)

    else:
        st.error(f"Refactoring failed: {result.get('reason', 'Unknown')}")
        st.json(result)


# ---- Main App ----

init_session()

st.markdown('<p class="main-header">Phoenix Agent</p>', unsafe_allow_html=True)
st.markdown("*Agentic code refactoring: Observe → Reason → Plan → Decide → Act → Verify → Update*")

# Sidebar
with st.sidebar:
    st.header("Configuration")

    if st.button("Initialize Agent", use_container_width=True):
        with st.spinner("Loading agent..."):
            try:
                agent = load_agent()
                st.success(f"Agent ready ({agent.config.llm.provider})")
            except Exception as e:
                st.error(f"Failed: {e}")

    st.divider()
    st.markdown("**Infrastructure**")
    st.markdown("```\ndocker-compose up -d\n```")
    st.markdown("Starts Redis, PostgreSQL, Neo4j")

    st.divider()
    st.markdown("**About**")
    st.markdown(
        "Phoenix Agent is a deep agentic system that "
        "analyzes, refactors, tests, and creates PRs "
        "for code improvements."
    )

# Main tabs
tab1, tab2, tab3 = st.tabs(["🔄 Refactor", "🔍 Analyze", "📊 History"])

with tab1:
    st.subheader("Run Refactoring Agent")

    target = st.text_input("Target Project Path", value="./sample_project")
    request = st.text_area(
        "Refactoring Request",
        value="Refactor UserService to follow the Single Responsibility Principle. "
              "Extract authentication, validation, persistence, and notification into separate classes.",
        height=100,
    )

    if st.button("Start Refactoring", type="primary", disabled=st.session_state.running):
        if not st.session_state.agent:
            st.warning("Initialize the agent first (sidebar)")
        else:
            st.session_state.running = True
            with st.spinner("Running agent loop... (this may take a few minutes)"):
                try:
                    result = st.session_state.agent.run(request, target)
                    st.session_state.result = result
                    display_agent_result(result)
                except Exception as e:
                    st.error(f"Agent error: {e}")
                finally:
                    st.session_state.running = False

    if st.session_state.result:
        with st.expander("Full Result JSON"):
            st.json(st.session_state.result)

with tab2:
    st.subheader("Code Analysis")
    analysis_target = st.text_input("Project Path", value="./sample_project", key="analysis_target")

    if st.button("Run Analysis"):
        with st.spinner("Analyzing..."):
            ast_result, test_result = run_analysis_only(analysis_target)

        st.markdown("### AST Analysis")
        display_ast_results(ast_result)

        st.markdown("### Test Results")
        display_test_results(test_result)

with tab3:
    st.subheader("Refactoring History")

    if st.button("Load History"):
        try:
            from phoenix_agent.memory.history import RefactoringHistory
            from phoenix_agent.config import PhoenixConfig

            config = PhoenixConfig.from_env()
            history = RefactoringHistory(config)
            records = history.get_history(limit=20)

            if not records:
                st.info("No refactoring history found.")
            else:
                for r in records:
                    status_icon = "✅" if r.outcome == "success" else "❌"
                    with st.expander(f"{status_icon} {r.session_id} — {r.outcome} ({r.duration_seconds:.1f}s)"):
                        st.json(r.model_dump())

            history.close()
        except Exception as e:
            st.error(f"Failed to load history: {e}")
