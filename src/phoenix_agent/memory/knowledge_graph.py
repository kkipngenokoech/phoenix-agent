"""Knowledge graph: Neo4j codebase structure mapping."""

from __future__ import annotations

import logging
from typing import Optional

from neo4j import GraphDatabase

from phoenix_agent.config import PhoenixConfig
from phoenix_agent.models import ASTAnalysisResult, ParsedFile

logger = logging.getLogger(__name__)


class CodebaseGraph:
    def __init__(self, config: PhoenixConfig) -> None:
        self._driver = None
        try:
            self._driver = GraphDatabase.driver(
                config.neo4j.uri,
                auth=(config.neo4j.user, config.neo4j.password),
            )
            self._driver.verify_connectivity()
            logger.info("Connected to Neo4j")
        except Exception as e:
            logger.warning(f"Neo4j unavailable: {e} - knowledge graph will not be updated")

    def _run(self, query: str, **params) -> list[dict]:
        if not self._driver:
            return []
        try:
            with self._driver.session() as session:
                result = session.run(query, **params)
                return [dict(record) for record in result]
        except Exception as e:
            logger.error(f"Neo4j query failed: {e}")
            return []

    # ------------------------------------------------------------------
    # Update from AST analysis
    # ------------------------------------------------------------------

    def update_from_ast(self, parsed_file: ParsedFile) -> None:
        if not self._driver:
            return

        file_path = parsed_file.file_path
        module_name = file_path.rsplit("/", 1)[-1].replace(".py", "")

        # Create/update module node
        self._run(
            """
            MERGE (m:Module {file_path: $file_path})
            SET m.name = $name,
                m.loc = $loc,
                m.complexity = $complexity,
                m.function_count = $function_count,
                m.class_count = $class_count
            """,
            file_path=file_path,
            name=module_name,
            loc=parsed_file.metrics.lines_of_code,
            complexity=parsed_file.metrics.cyclomatic_complexity,
            function_count=parsed_file.metrics.function_count,
            class_count=parsed_file.metrics.class_count,
        )

        # Create dependency edges
        for dep in parsed_file.dependencies:
            self._run(
                """
                MERGE (m:Module {file_path: $file_path})
                MERGE (d:Module {name: $dep_name})
                MERGE (m)-[:IMPORTS]->(d)
                """,
                file_path=file_path,
                dep_name=dep,
            )

    def update_from_analysis(self, result: ASTAnalysisResult) -> None:
        for pf in result.parsed_files:
            self.update_from_ast(pf)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_dependencies(self, file_path: str) -> list[str]:
        records = self._run(
            """
            MATCH (m:Module {file_path: $file_path})-[:IMPORTS]->(d)
            RETURN d.name AS dependency
            """,
            file_path=file_path,
        )
        return [r["dependency"] for r in records]

    def get_dependents(self, file_path: str) -> list[str]:
        module_name = file_path.rsplit("/", 1)[-1].replace(".py", "")
        records = self._run(
            """
            MATCH (m)-[:IMPORTS]->(d:Module {name: $name})
            RETURN m.file_path AS dependent
            """,
            name=module_name,
        )
        return [r["dependent"] for r in records]

    def get_impact_analysis(self, files: list[str]) -> dict:
        """Get all modules that could be affected by changes to the given files."""
        all_dependents: set[str] = set()
        for f in files:
            deps = self.get_dependents(f)
            all_dependents.update(deps)

        return {
            "files_to_change": files,
            "affected_modules": list(all_dependents),
            "total_impact": len(files) + len(all_dependents),
        }

    def get_all_modules(self) -> list[dict]:
        return self._run(
            """
            MATCH (m:Module)
            RETURN m.name AS name, m.file_path AS file_path,
                   m.loc AS loc, m.complexity AS complexity
            ORDER BY m.complexity DESC
            """
        )

    def clear(self) -> None:
        self._run("MATCH (n) DETACH DELETE n")
        logger.info("Cleared Neo4j graph")

    def close(self) -> None:
        if self._driver:
            self._driver.close()
