"""Shared code generation utilities extracted from executor.py.

Used by both the legacy Executor class and the new CoderAgent.
"""

from __future__ import annotations

import ast as ast_module
import logging
import re
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

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

## Project Structure
{project_context}
{related_source}
## Current File: {file_path}
{file_content}
{test_failure_context}
Respond with the complete updated file contents only. Use real import paths from the project — never use placeholder names like 'your_module'."""


def generate_code(
    llm: Any,
    target_file: str,
    description: str,
    test_failures: list[dict] | None = None,
) -> str | None:
    """Ask the LLM to generate refactored code for a file.

    Returns the generated code string, or None on failure.
    """
    target = Path(target_file)

    file_content = "(new file)"
    if target.exists():
        try:
            file_content = target.read_text()
        except Exception as e:
            logger.warning(f"Could not read {target_file}: {e}")

    project_context = build_project_context(target_file)

    related_source = ""
    if is_test_file(target_file):
        related_source = get_related_source(target_file)

    test_failure_context = ""
    if test_failures:
        relevant = [f for f in test_failures
                    if Path(target_file).name in f.get("test_file", "")]
        if relevant:
            lines = ["## Previous Test Failures (you MUST fix these)"]
            for f in relevant[:5]:
                lines.append(f"- {f.get('test_name', '?')}: {f.get('error_message', '?')}")
            test_failure_context = "\n".join(lines) + "\n"

    prompt = CODE_GEN_PROMPT.format(
        description=description,
        file_path=target_file,
        file_content=file_content,
        project_context=project_context,
        related_source=related_source,
        test_failure_context=test_failure_context,
    )

    messages = [
        SystemMessage(content=CODE_GEN_SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ]

    try:
        response = llm.invoke(messages)
        raw = response.content
        logger.debug(f"Raw LLM response ({len(raw)} chars): {raw[:200]}...")
        code = clean_code_response(raw)
        logger.info(f"LLM generated {len(code.splitlines())} lines for {target_file}")
        return code
    except Exception as e:
        logger.error(f"LLM code generation failed: {e}")
        return None


def modify_file(target_file: str, code_changes: str) -> ToolResult:
    """Write code changes to a file with syntax validation and rollback.

    Returns a ToolResult indicating success or failure.
    """
    target = Path(target_file)
    if not target.parent.exists():
        target.parent.mkdir(parents=True, exist_ok=True)

    try:
        original = ""
        if target.exists():
            original = target.read_text()

        target.write_text(code_changes)

        try:
            ast_module.parse(code_changes)
            logger.info(f"Syntax check passed for {target_file}")
        except SyntaxError as e:
            logger.error(f"SYNTAX ERROR in generated code for {target_file}: {e}")
            logger.error(f"First 300 chars of generated code:\n{code_changes[:300]}")
            if original:
                target.write_text(original)
            return ToolResult(
                success=False,
                error=f"Generated code has syntax error: {e}. Rolled back.",
            )

        return ToolResult(
            success=True,
            output={
                "file": target_file,
                "original_lines": len(original.splitlines()),
                "new_lines": len(code_changes.splitlines()),
            },
            metadata={"original_content": original},
        )
    except Exception as e:
        return ToolResult(success=False, error=f"File write failed: {e}")


def clean_code_response(raw: str) -> str:
    """Strip markdown fences and prose from LLM code output."""
    text = raw.strip()

    fence_match = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.DOTALL)
    if fence_match:
        return fence_match.group(1).strip()

    if text.startswith("```"):
        lines = text.splitlines()
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()

    lines = text.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped and (
            stripped.startswith(("import ", "from ", "class ", "def ", "#", '"""', "'''"))
        ):
            return "\n".join(lines[i:]).strip()

    return text


def build_project_context(target_file: str) -> str:
    """Build a short project structure summary so the LLM knows real import paths."""
    target = Path(target_file)
    project_root = target.parent
    for parent in target.parents:
        if any((parent / marker).exists() for marker in ("pyproject.toml", "setup.py", "setup.cfg")):
            project_root = parent
            break

    py_files = sorted(
        str(p.relative_to(project_root))
        for p in project_root.rglob("*.py")
        if "__pycache__" not in str(p)
    )[:30]

    if not py_files:
        return "(no Python files found)"

    lines = [f"Project root: {project_root}"]
    src_dir = project_root / "src"
    if src_dir.is_dir():
        packages = [d.name for d in src_dir.iterdir() if d.is_dir() and (d / "__init__.py").exists()]
        if packages:
            lines.append(f"Source packages: {', '.join(packages)}")

    lines.append("Files:")
    for f in py_files:
        lines.append(f"  {f}")

    return "\n".join(lines)


def get_related_source(test_file: str) -> str:
    """Find and read the source file(s) that a test file is testing."""
    test_path = Path(test_file)
    name = test_path.name

    source_name = name.replace("test_", "", 1) if name.startswith("test_") else None
    if not source_name:
        return ""

    project_root = test_path.parent
    while project_root.parent != project_root:
        project_root = project_root.parent
        if (project_root / "src").is_dir():
            break

    matches = list(project_root.rglob(source_name))
    if not matches:
        return ""

    sections = []
    for src_path in matches[:2]:
        try:
            content = src_path.read_text()
            sections.append(f"\n## Source File Being Tested: {src_path}\n{content}\n")
        except Exception:
            pass

    return "\n".join(sections)


def is_test_file(file_path: str) -> bool:
    """Check if a file path refers to a test file."""
    name = Path(file_path).name
    return name.startswith("test_") or name.endswith("_test.py") or "/tests/" in file_path
