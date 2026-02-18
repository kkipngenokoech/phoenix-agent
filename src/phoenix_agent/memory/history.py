"""Long-term memory: PostgreSQL refactoring history."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional

import psycopg2
import psycopg2.extras

from phoenix_agent.config import PhoenixConfig
from phoenix_agent.models import RefactoringRecord, TeamPreference

logger = logging.getLogger(__name__)


class RefactoringHistory:
    def __init__(self, config: PhoenixConfig) -> None:
        self._url = config.postgres.url
        self._conn: Optional[psycopg2.extensions.connection] = None
        try:
            self._conn = psycopg2.connect(self._url)
            self._conn.autocommit = True
            logger.info("Connected to PostgreSQL")
        except psycopg2.OperationalError as e:
            logger.warning(f"PostgreSQL unavailable: {e} - history will not be persisted")

    # ------------------------------------------------------------------
    # Refactoring Records
    # ------------------------------------------------------------------

    def record_refactoring(self, record: RefactoringRecord) -> None:
        if not self._conn:
            logger.warning("No DB connection - skipping record")
            return
        try:
            with self._conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO refactoring_history
                        (session_id, timestamp, files_modified, risk_score,
                         metrics_before, metrics_after, pr_url, outcome,
                         duration_seconds, original_files, refactored_files)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (session_id) DO UPDATE SET
                        files_modified = EXCLUDED.files_modified,
                        metrics_after = EXCLUDED.metrics_after,
                        pr_url = EXCLUDED.pr_url,
                        outcome = EXCLUDED.outcome,
                        duration_seconds = EXCLUDED.duration_seconds,
                        original_files = EXCLUDED.original_files,
                        refactored_files = EXCLUDED.refactored_files
                    """,
                    (
                        record.session_id,
                        record.timestamp,
                        json.dumps(record.files_modified),
                        record.risk_score,
                        json.dumps(record.metrics_before),
                        json.dumps(record.metrics_after),
                        record.pr_url,
                        record.outcome,
                        record.duration_seconds,
                        json.dumps(record.original_files),
                        json.dumps(record.refactored_files),
                    ),
                )
            logger.info(f"Recorded refactoring {record.session_id}")
        except Exception as e:
            logger.error(f"Failed to record refactoring: {e}")

    def get_history(self, limit: int = 50) -> list[RefactoringRecord]:
        if not self._conn:
            return []
        try:
            with self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM refactoring_history ORDER BY timestamp DESC LIMIT %s",
                    (limit,),
                )
                rows = cur.fetchall()
                return [self._row_to_record(r) for r in rows]
        except Exception as e:
            logger.error(f"Failed to fetch history: {e}")
            return []

    def get_by_session(self, session_id: str) -> Optional[RefactoringRecord]:
        if not self._conn:
            return None
        try:
            with self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM refactoring_history WHERE session_id = %s",
                    (session_id,),
                )
                row = cur.fetchone()
                return self._row_to_record(row) if row else None
        except Exception as e:
            logger.error(f"Failed to fetch session: {e}")
            return None

    def get_successful_patterns(self) -> list[dict]:
        if not self._conn:
            return []
        try:
            with self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM refactoring_history WHERE outcome = 'success' ORDER BY timestamp DESC LIMIT 20"
                )
                return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.error(f"Failed to fetch patterns: {e}")
            return []

    # ------------------------------------------------------------------
    # Team Preferences
    # ------------------------------------------------------------------

    def set_preference(self, pref: TeamPreference) -> None:
        if not self._conn:
            return
        try:
            with self._conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO team_preferences (key, value, rationale)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (key) DO UPDATE SET
                        value = EXCLUDED.value,
                        rationale = EXCLUDED.rationale,
                        updated_at = NOW()
                    """,
                    (pref.key, json.dumps(pref.value), pref.rationale),
                )
        except Exception as e:
            logger.error(f"Failed to set preference: {e}")

    def get_preferences(self) -> list[TeamPreference]:
        if not self._conn:
            return []
        try:
            with self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM team_preferences ORDER BY key")
                return [
                    TeamPreference(
                        key=r["key"],
                        value=r["value"],
                        rationale=r["rationale"],
                        created_at=r["created_at"],
                    )
                    for r in cur.fetchall()
                ]
        except Exception as e:
            logger.error(f"Failed to fetch preferences: {e}")
            return []

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_record(row: dict) -> RefactoringRecord:
        def _parse_json(val, default):
            if val is None:
                return default
            if isinstance(val, (dict, list)):
                return val
            return json.loads(val)

        return RefactoringRecord(
            session_id=row["session_id"],
            timestamp=row["timestamp"],
            files_modified=_parse_json(row["files_modified"], []),
            risk_score=row["risk_score"],
            metrics_before=_parse_json(row["metrics_before"], {}),
            metrics_after=_parse_json(row["metrics_after"], {}),
            pr_url=row.get("pr_url"),
            outcome=row["outcome"],
            duration_seconds=row["duration_seconds"],
            original_files=_parse_json(row.get("original_files"), {}),
            refactored_files=_parse_json(row.get("refactored_files"), {}),
        )

    def close(self) -> None:
        if self._conn:
            self._conn.close()
