from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS hypotheses (
  hypothesis_id TEXT PRIMARY KEY,
  statement TEXT NOT NULL,
  question TEXT NOT NULL,
  voi_prior REAL NOT NULL,
  kaggle_ref TEXT,
  paper_ref TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY,
  hypothesis_id TEXT NOT NULL,
  variant TEXT NOT NULL,
  params_json TEXT NOT NULL,
  metric REAL NOT NULL,
  score REAL NOT NULL,
  started_at TEXT NOT NULL,
  ended_at TEXT NOT NULL,
  FOREIGN KEY(hypothesis_id) REFERENCES hypotheses(hypothesis_id)
);

CREATE TABLE IF NOT EXISTS validations (
  validation_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  passed INTEGER NOT NULL,
  notes TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY(run_id) REFERENCES runs(run_id)
);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.executescript(SCHEMA)
    return conn


def insert_hypothesis(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO hypotheses (
          hypothesis_id, statement, question, voi_prior, kaggle_ref, paper_ref, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row["hypothesis_id"],
            row["statement"],
            row["question"],
            row["voi_prior"],
            row.get("kaggle_ref"),
            row.get("paper_ref"),
            row["created_at"],
        ),
    )
    conn.commit()


def insert_run(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO runs (
          run_id, hypothesis_id, variant, params_json, metric, score, started_at, ended_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row["run_id"],
            row["hypothesis_id"],
            row["variant"],
            row["params_json"],
            row["metric"],
            row["score"],
            row["started_at"],
            row["ended_at"],
        ),
    )
    conn.commit()


def insert_validation(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO validations (validation_id, run_id, passed, notes, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            row["validation_id"],
            row["run_id"],
            1 if row["passed"] else 0,
            row.get("notes", ""),
            row["created_at"],
        ),
    )
    conn.commit()
