"""Paths and secrets. Everything derived lives under db/ (git-ignored)."""
from __future__ import annotations

import os
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data"
DB_DIR = ROOT / "db"
ANALYTICS_DB = DB_DIR / "lpip.duckdb"      # rebuilt by etl/build_db.py (read-only at runtime)
APP_DB = DB_DIR / "app.sqlite"              # users, workspaces, portal, audit (read-write)
AI_DIR = DB_DIR / "ai"                      # semantic index built by etl/build_ai.py
UPLOADS = DB_DIR / "uploads"                # researcher submissions


def _secret() -> str:
    if os.environ.get("LPIP_SECRET"):
        return os.environ["LPIP_SECRET"]
    f = DB_DIR / "secret.key"
    if not f.exists():
        DB_DIR.mkdir(exist_ok=True)
        f.write_text(secrets.token_hex(32))
    return f.read_text().strip()


SECRET = _secret()
TOKEN_HOURS = 12
CORS_ORIGINS = os.environ.get("LPIP_CORS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
RATE_LIMIT_PER_MIN = int(os.environ.get("LPIP_RATE_LIMIT", "240"))
