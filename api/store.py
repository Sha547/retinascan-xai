"""SQLite persistence for cases and the append-only decision log."""
from __future__ import annotations

import json
import sqlite3
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS cases (
    case_id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL,
    eye TEXT NOT NULL CHECK (eye IN ('left', 'right', 'unknown')),
    created_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'retake', 'accepted', 'overridden')),
    image_path TEXT NOT NULL,
    quality_json TEXT NOT NULL,
    prediction_json TEXT,
    evidence_json TEXT,
    recommendation TEXT NOT NULL,
    priority REAL,
    final_grade INTEGER,
    model_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS cases_status ON cases (status);

CREATE TABLE IF NOT EXISTS decisions (
    decision_id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id TEXT NOT NULL REFERENCES cases (case_id),
    action TEXT NOT NULL CHECK (action IN ('accept', 'override')),
    final_grade INTEGER NOT NULL,
    reviewer TEXT NOT NULL,
    note TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS decisions_case ON decisions (case_id);

CREATE TRIGGER IF NOT EXISTS decisions_no_delete BEFORE DELETE ON decisions
BEGIN SELECT RAISE(ABORT, 'decisions are append-only'); END;
CREATE TRIGGER IF NOT EXISTS decisions_no_update BEFORE UPDATE ON decisions
BEGIN SELECT RAISE(ABORT, 'decisions are append-only'); END;
"""

# Summary rows skip evidence_json, which holds the large heatmap.
SUMMARY_COLUMNS = (
    "c.case_id, c.patient_id, c.eye, c.created_at, c.status, c.quality_json, "
    "c.prediction_json, c.priority, c.final_grade, c.model_json"
)
QUEUES = {
    "pending": (
        "WHERE c.status = 'pending'",
        "ORDER BY c.priority DESC, c.created_at ASC, c.rowid ASC",
    ),
    "reviewed": (
        "WHERE c.status IN ('accepted', 'overridden')",
        "ORDER BY (SELECT MAX(d.decision_id) FROM decisions d WHERE d.case_id = c.case_id) DESC",
    ),
    "retake": ("WHERE c.status = 'retake'", "ORDER BY c.created_at DESC, c.rowid DESC"),
    "all": ("", "ORDER BY c.created_at DESC, c.rowid DESC"),
}


class CaseNotFound(Exception):
    pass


class DecisionNotAllowed(Exception):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _optional_json(text: str | None):
    return None if text is None else json.loads(text)


class Store:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection:
            connection.executescript(SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @contextmanager
    def _transaction(self):
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                yield connection
            except BaseException:
                connection.execute("ROLLBACK")
                raise
            connection.execute("COMMIT")

    def case_exists(self, case_id: str) -> bool:
        with closing(self._connect()) as connection:
            row = connection.execute("SELECT 1 FROM cases WHERE case_id = ?", (case_id,)).fetchone()
        return row is not None

    def next_patient_number(self) -> int:
        with closing(self._connect()) as connection:
            return connection.execute("SELECT COUNT(*) FROM cases").fetchone()[0] + 1

    def add_case(self, case: dict, image_path: Path) -> None:
        with self._transaction() as connection:
            connection.execute(
                """INSERT INTO cases (case_id, patient_id, eye, created_at, status, image_path,
                   quality_json, prediction_json, evidence_json, recommendation, priority,
                   final_grade, model_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)""",
                (
                    case["case_id"],
                    case["patient_id"],
                    case["eye"],
                    case["created_at"],
                    case["status"],
                    str(image_path),
                    json.dumps(case["quality"]),
                    None if case["prediction"] is None else json.dumps(case["prediction"]),
                    None if case["evidence"] is None else json.dumps(case["evidence"]),
                    case["recommendation"],
                    case["priority"],
                    json.dumps(case["model"]),
                ),
            )

    def get_case(self, case_id: str) -> dict:
        with closing(self._connect()) as connection:
            row = connection.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)).fetchone()
            if row is None:
                raise CaseNotFound(case_id)
            decisions = connection.execute(
                "SELECT * FROM decisions WHERE case_id = ? ORDER BY decision_id ASC", (case_id,)
            ).fetchall()
        return {
            "case_id": row["case_id"],
            "patient_id": row["patient_id"],
            "eye": row["eye"],
            "created_at": row["created_at"],
            "status": row["status"],
            "quality": json.loads(row["quality_json"]),
            "prediction": _optional_json(row["prediction_json"]),
            "recommendation": row["recommendation"],
            "evidence": _optional_json(row["evidence_json"]),
            "priority": row["priority"],
            "final_grade": row["final_grade"],
            "decisions": [dict(decision) for decision in decisions],
            "model": json.loads(row["model_json"]),
        }

    def image_path(self, case_id: str) -> Path:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT image_path FROM cases WHERE case_id = ?", (case_id,)
            ).fetchone()
        if row is None:
            raise CaseNotFound(case_id)
        return Path(row["image_path"])

    def list_cases(self, status: str, limit: int) -> tuple[list[dict], int]:
        where, order = QUEUES[status]
        with closing(self._connect()) as connection:
            total = connection.execute(f"SELECT COUNT(*) FROM cases c {where}").fetchone()[0]
            rows = connection.execute(
                f"SELECT {SUMMARY_COLUMNS} FROM cases c {where} {order} LIMIT ?", (limit,)
            ).fetchall()
        return [self._summary(row) for row in rows], total

    @staticmethod
    def _summary(row: sqlite3.Row) -> dict:
        prediction = _optional_json(row["prediction_json"]) or {}
        return {
            "case_id": row["case_id"],
            "patient_id": row["patient_id"],
            "eye": row["eye"],
            "created_at": row["created_at"],
            "status": row["status"],
            "quality_ok": json.loads(row["quality_json"])["ok"],
            "grade": prediction.get("grade"),
            "grade_label": prediction.get("grade_label"),
            "confidence": prediction.get("confidence"),
            "abstained": prediction.get("abstained"),
            "referable": prediction.get("referable"),
            "priority": row["priority"],
            "final_grade": row["final_grade"],
            "mock": json.loads(row["model_json"])["mock"],
        }

    def add_decision(
        self, case_id: str, action: str, final_grade: int | None, reviewer: str, note: str
    ) -> None:
        """Log a decision and update the case in one transaction."""
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT status, prediction_json FROM cases WHERE case_id = ?", (case_id,)
            ).fetchone()
            if row is None:
                raise CaseNotFound(case_id)
            if row["status"] == "retake":
                raise DecisionNotAllowed(case_id)

            if action == "accept":
                final_grade = json.loads(row["prediction_json"])["grade"]
            connection.execute(
                """INSERT INTO decisions (case_id, action, final_grade, reviewer, note, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (case_id, action, final_grade, reviewer, note, now_iso()),
            )
            status = "accepted" if action == "accept" else "overridden"
            connection.execute(
                "UPDATE cases SET status = ?, final_grade = ? WHERE case_id = ?",
                (status, final_grade, case_id),
            )
