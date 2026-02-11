"""Tool 1: AST Parser & Analyzer - parse source code and extract structural information."""

from __future__ import annotations

import ast
import logging
import os
from typing import Optional

from phoenix_agent.models import (
    ASTAnalysisResult,
    CodeSmell,
    CodeSmellType,
    FileMetrics,
    ParsedFile,
    SmellSeverity,
)
from phoenix_agent.tools.base import BaseTool, ToolCategory, ToolResult

logger = logging.getLogger(__name__)


class ASTParserTool(BaseTool):
    name = "ast_parser"
    description = "Parse source code into ASTs and extract metrics, dependencies, and code smells."
    category = ToolCategory.ANALYSIS
    parameters_schema = {
        "required": ["file_paths"],
        "properties": {
            "file_paths": {"type": "array", "description": "Absolute paths to analyze"},
            "language": {"type": "string", "default": "python"},
            "analysis_depth": {"type": "string", "default": "deep"},
            "include_dependencies": {"type": "boolean", "default": True},
        },
    }

    def execute(
        self,
        file_paths: list[str],
        language: str = "python",
        analysis_depth: str = "deep",
        include_dependencies: bool = True,
        **kwargs,
    ) -> ToolResult:
        parsed_files: list[ParsedFile] = []
        errors: list[dict] = []
        dep_graph: dict[str, list[str]] = {}

        for fp in file_paths:
            try:
                result = self._analyze_file(fp, analysis_depth, include_dependencies)
                parsed_files.append(result)
                if include_dependencies:
                    dep_graph[fp] = result.dependencies
            except SyntaxError as e:
                errors.append({"file_path": fp, "error_type": "syntax_error", "message": str(e)})
            except FileNotFoundError:
                errors.append({"file_path": fp, "error_type": "file_not_found", "message": f"File not found: {fp}"})
            except Exception as e:
                errors.append({"file_path": fp, "error_type": "parse_error", "message": str(e)})

        status = "success"
        if errors and not parsed_files:
            status = "failed"
        elif errors:
            status = "partial_success"

        result = ASTAnalysisResult(
            status=status,
            parsed_files=parsed_files,
            dependency_graph=dep_graph,
            errors=errors,
        )

        return ToolResult(
            success=status != "failed",
            output=result.model_dump(),
            metadata={"files_analyzed": len(parsed_files), "errors": len(errors)},
        )

    def _analyze_file(
        self, file_path: str, depth: str, include_deps: bool
    ) -> ParsedFile:
        with open(file_path, "r") as f:
            source = f.read()

        tree = ast.parse(source, filename=file_path)
        lines = source.splitlines()

        metrics = self._extract_metrics(tree, lines)
        metrics.file_path = file_path

        smells = self._detect_code_smells(source, tree) if depth == "deep" else []
        deps = self._extract_dependencies(tree) if include_deps else []

        return ParsedFile(
            file_path=file_path,
            language="python",
            metrics=metrics,
            dependencies=deps,
            code_smells=smells,
        )

    # ------------------------------------------------------------------
    # Metrics extraction
    # ------------------------------------------------------------------

    def _extract_metrics(self, tree: ast.AST, lines: list[str]) -> FileMetrics:
        function_count = sum(1 for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)))
        class_count = sum(1 for n in ast.walk(tree) if isinstance(n, ast.ClassDef))
        complexity = self._calculate_cyclomatic(tree)
        nesting = self._max_nesting(tree)

        return FileMetrics(
            file_path="",
            lines_of_code=len(lines),
            cyclomatic_complexity=complexity,
            function_count=function_count,
            class_count=class_count,
            max_nesting_depth=nesting,
        )

    def _calculate_cyclomatic(self, tree: ast.AST) -> int:
        """Cyclomatic complexity = 1 + decision points."""
        decision_nodes = (
            ast.If, ast.For, ast.While, ast.ExceptHandler,
            ast.With, ast.BoolOp, ast.IfExp,
        )
        complexity = 1
        for node in ast.walk(tree):
            if isinstance(node, decision_nodes):
                complexity += 1
                if isinstance(node, ast.BoolOp):
                    complexity += len(node.values) - 1
        return complexity

    def _max_nesting(self, tree: ast.AST, depth: int = 0) -> int:
        nesting_nodes = (ast.If, ast.For, ast.While, ast.With, ast.Try)
        max_depth = depth
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, nesting_nodes):
                child_depth = self._max_nesting(node, depth + 1)
                max_depth = max(max_depth, child_depth)
            else:
                child_depth = self._max_nesting(node, depth)
                max_depth = max(max_depth, child_depth)
        return max_depth

    # ------------------------------------------------------------------
    # Code smell detection
    # ------------------------------------------------------------------

    def _detect_code_smells(self, source: str, tree: ast.AST) -> list[CodeSmell]:
        smells: list[CodeSmell] = []
        lines = source.splitlines()

        for node in ast.walk(tree):
            # Long method (>20 lines)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if hasattr(node, "end_lineno") and node.end_lineno:
                    length = node.end_lineno - node.lineno
                    if length > 20:
                        severity = SmellSeverity.HIGH if length > 50 else SmellSeverity.MEDIUM
                        smells.append(CodeSmell(
                            type=CodeSmellType.LONG_METHOD,
                            location={"start_line": node.lineno, "end_line": node.end_lineno},
                            severity=severity,
                            description=f"Method '{node.name}' is {length} lines long",
                        ))

                # Long parameter list (>5)
                params = node.args
                param_count = len(params.args) + len(params.kwonlyargs)
                if params.vararg:
                    param_count += 1
                if params.kwarg:
                    param_count += 1
                if param_count > 5:
                    smells.append(CodeSmell(
                        type=CodeSmellType.LONG_PARAMETER_LIST,
                        location={"start_line": node.lineno, "end_line": node.lineno},
                        severity=SmellSeverity.MEDIUM,
                        description=f"Method '{node.name}' has {param_count} parameters",
                    ))

            # God class (>10 methods)
            if isinstance(node, ast.ClassDef):
                methods = [n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
                if len(methods) > 10:
                    smells.append(CodeSmell(
                        type=CodeSmellType.GOD_CLASS,
                        location={"start_line": node.lineno, "end_line": getattr(node, "end_lineno", node.lineno)},
                        severity=SmellSeverity.HIGH,
                        description=f"Class '{node.name}' has {len(methods)} methods",
                    ))

            # Deep nesting (>4 levels)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                nesting = self._max_nesting(node)
                if nesting > 4:
                    smells.append(CodeSmell(
                        type=CodeSmellType.DEEP_NESTING,
                        location={"start_line": node.lineno, "end_line": getattr(node, "end_lineno", node.lineno)},
                        severity=SmellSeverity.HIGH if nesting > 6 else SmellSeverity.MEDIUM,
                        description=f"Method '{node.name}' has nesting depth of {nesting}",
                    ))

        # Magic numbers
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                if node.value not in (0, 1, -1, 2, 0.0, 1.0, 100) and hasattr(node, "lineno"):
                    # Only flag if not in obvious contexts
                    smells.append(CodeSmell(
                        type=CodeSmellType.MAGIC_NUMBERS,
                        location={"start_line": node.lineno, "end_line": node.lineno},
                        severity=SmellSeverity.LOW,
                        description=f"Magic number {node.value} at line {node.lineno}",
                    ))

        return smells

    # ------------------------------------------------------------------
    # Dependency extraction
    # ------------------------------------------------------------------

    def _extract_dependencies(self, tree: ast.AST) -> list[str]:
        deps: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    deps.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    deps.append(node.module)
        return sorted(set(deps))
