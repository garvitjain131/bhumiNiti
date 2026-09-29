"""Database access: DuckDB (analytics, read-only) + SQLite (application state, read-write)."""
from __future__ import annotations

import json
import sqlite3
import threading

import duckdb
from fastapi import HTTPException

from .config import ANALYTICS_DB, APP_DB

_duck: duckdb.DuckDBPyConnection | None = None
_duck_lock = threading.Lock()


def duck() -> duckdb.DuckDBPyConnection:
    """A cursor on the shared read-only analytics connection (one cursor per request)."""
    global _duck
    with _duck_lock:
        if _duck is None:
            if not ANALYTICS_DB.exists():
                raise HTTPException(503, "analytics database not built: run  python etl/build_db.py")
            _duck = duckdb.connect(str(ANALYTICS_DB), read_only=True)
            _duck.execute("LOAD spatial; LOAD fts;")
    return _duck.cursor()


def _clean(v):
    if isinstance(v, float) and (v != v or v in (float("inf"), float("-inf"))):
        return None  # NaN / inf are not valid JSON
    return v


def rows(sql: str, params: list | None = None) -> list[dict]:
    cur = duck().execute(sql, params or [])
    cols = [c[0] for c in cur.description]
    return [{c: _clean(v) for c, v in zip(cols, r)} for r in cur.fetchall()]


def one(sql: str, params: list | None = None) -> dict | None:
    r = rows(sql, params)
    return r[0] if r else None


def feature_collection(sql: str, params: list | None = None) -> dict:
    """SQL must return a `gj` column (GeoJSON geometry text) plus property columns."""
    feats = []
    for r in rows(sql, params):
        geom = r.pop("gj")
        feats.append({"type": "Feature", "geometry": json.loads(geom) if geom else None, "properties": r})
    return {"type": "FeatureCollection", "features": feats}


# --------------------------------------------------------------------------- application DB (SQLite)

def app_db() -> sqlite3.Connection:
    con = sqlite3.connect(APP_DB, timeout=15, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA journal_mode = WAL")
    return con


def q(sql: str, params: tuple | list = ()) -> list[dict]:
    with app_db() as con:
        return [dict(r) for r in con.execute(sql, params).fetchall()]


def q1(sql: str, params: tuple | list = ()) -> dict | None:
    r = q(sql, params)
    return r[0] if r else None


def execute(sql: str, params: tuple | list = ()) -> int:
    """Run a write; returns lastrowid."""
    with app_db() as con:
        cur = con.execute(sql, params)
        return cur.lastrowid


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, name TEXT NOT NULL, pw_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('researcher','institution_admin','official','reviewer','admin')),
    institution TEXT, active INTEGER NOT NULL DEFAULT 1, created_at TEXT DEFAULT CURRENT_TIMESTAMP);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY, ts TEXT NOT NULL, user_id INTEGER, user_email TEXT, action TEXT NOT NULL,
    resource TEXT, detail TEXT, prev_hash TEXT NOT NULL, hash TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS api_key (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, key_hash TEXT UNIQUE NOT NULL, owner_id INTEGER REFERENCES users(id),
    active INTEGER NOT NULL DEFAULT 1, created_at TEXT DEFAULT CURRENT_TIMESTAMP);

CREATE TABLE IF NOT EXISTS access_request (
    id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), dataset TEXT NOT NULL,
    purpose TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','rejected')),
    decided_by INTEGER REFERENCES users(id), decided_at TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);

CREATE TABLE IF NOT EXISTS workspace (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, question TEXT, description TEXT, geography TEXT, period TEXT,
    indicators TEXT, owner_id INTEGER NOT NULL REFERENCES users(id), status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS workspace_member (
    workspace_id INTEGER REFERENCES workspace(id) ON DELETE CASCADE, user_id INTEGER REFERENCES users(id),
    role TEXT NOT NULL CHECK (role IN ('owner','editor','viewer')), PRIMARY KEY (workspace_id, user_id));
CREATE TABLE IF NOT EXISTS workspace_item (
    id INTEGER PRIMARY KEY, workspace_id INTEGER REFERENCES workspace(id) ON DELETE CASCADE,
    evidence_id TEXT NOT NULL, note TEXT, stance TEXT, added_by INTEGER REFERENCES users(id),
    created_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE (workspace_id, evidence_id));
CREATE TABLE IF NOT EXISTS workspace_note (
    id INTEGER PRIMARY KEY, workspace_id INTEGER REFERENCES workspace(id) ON DELETE CASCADE, note_key TEXT NOT NULL,
    title TEXT NOT NULL, body TEXT NOT NULL, version INTEGER NOT NULL, author_id INTEGER REFERENCES users(id),
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','in_review','approved','changes_requested')),
    created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS workspace_comment (
    id INTEGER PRIMARY KEY, workspace_id INTEGER REFERENCES workspace(id) ON DELETE CASCADE, target TEXT,
    body TEXT NOT NULL, author_id INTEGER REFERENCES users(id), created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS workspace_task (
    id INTEGER PRIMARY KEY, workspace_id INTEGER REFERENCES workspace(id) ON DELETE CASCADE, title TEXT NOT NULL,
    assignee_id INTEGER REFERENCES users(id), status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','done')),
    created_at TEXT DEFAULT CURRENT_TIMESTAMP);

CREATE TABLE IF NOT EXISTS call (
    id INTEGER PRIMARY KEY, kind TEXT NOT NULL CHECK (kind IN ('institutional_grant','individual_grant','hackathon','pilot','competition')),
    title TEXT NOT NULL, description TEXT, theme TEXT, geography TEXT, budget_lakh REAL, opens TEXT, closes TEXT,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('draft','open','closed','awarded')),
    source_gap TEXT, created_by INTEGER REFERENCES users(id), created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS application (
    id INTEGER PRIMARY KEY, call_id INTEGER REFERENCES call(id), applicant_id INTEGER REFERENCES users(id),
    title TEXT NOT NULL, hypothesis TEXT, methodology TEXT, budget_lakh REAL,
    stage TEXT NOT NULL DEFAULT 'submitted' CHECK (stage IN ('submitted','under_review','shortlisted','awarded',
        'advance_released','review_1','review_2','final_report','completed','rejected')),
    created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS review (
    id INTEGER PRIMARY KEY, application_id INTEGER REFERENCES application(id) ON DELETE CASCADE,
    reviewer_id INTEGER REFERENCES users(id), score INTEGER CHECK (score BETWEEN 0 AND 100), comments TEXT,
    conflict_of_interest INTEGER NOT NULL DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (application_id, reviewer_id));
CREATE TABLE IF NOT EXISTS pilot (
    id INTEGER PRIMARY KEY, application_id INTEGER REFERENCES application(id), title TEXT NOT NULL,
    district_lgd INTEGER, state TEXT, status TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('planned','running','completed')),
    start_date TEXT, end_date TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS outcome (
    id INTEGER PRIMARY KEY, pilot_id INTEGER REFERENCES pilot(id) ON DELETE CASCADE, indicator TEXT NOT NULL,
    baseline REAL, result REAL, unit TEXT, notes TEXT, contribution_id INTEGER, created_at TEXT DEFAULT CURRENT_TIMESTAMP);

CREATE TABLE IF NOT EXISTS contribution (
    id INTEGER PRIMARY KEY, submitter_id INTEGER REFERENCES users(id), kind TEXT NOT NULL,
    title TEXT NOT NULL, abstract TEXT NOT NULL, method TEXT, finding_direction TEXT, states TEXT, themes TEXT,
    district_lgd INTEGER, url TEXT, file_name TEXT, call_id INTEGER, pilot_id INTEGER,
    status TEXT NOT NULL DEFAULT 'submitted' CHECK (status IN ('submitted','approved','rejected')),
    reviewer_id INTEGER REFERENCES users(id), review_note TEXT, decided_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP);

CREATE TABLE IF NOT EXISTS sim_run (
    id INTEGER PRIMARY KEY, user_id INTEGER, lever TEXT NOT NULL, params TEXT NOT NULL, seed INTEGER NOT NULL,
    result TEXT NOT NULL, hash TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
"""


def init_app_db() -> None:
    APP_DB.parent.mkdir(exist_ok=True)
    with app_db() as con:
        con.executescript(SCHEMA)
