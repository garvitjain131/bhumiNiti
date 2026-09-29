"""
Authentication, role-based access control, dataset access levels, and the tamper-evident audit log.

Roles (least to most privileged): public (anonymous) < researcher < institution_admin < reviewer < official < admin
Data classes: open (anyone) | registered (any signed-in user) | restricted (officials/admins, or an approved
access request) | confidential (admins only).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import secrets

import jwt
from fastapi import Depends, Header, HTTPException, Request

from .config import SECRET, TOKEN_HOURS
from .db import execute, q, q1

ROLES = ["public", "researcher", "institution_admin", "reviewer", "official", "admin"]
DATA_CLASSES = ("open", "registered", "restricted", "confidential")

# datasets with an access class above "open"
DATASET_CLASS = {
    "land_records_synthetic": "restricted",      # parcel-level owner records (SYNTHETIC demo)
    "land_records_identified": "confidential",   # the same, without masking
    "audit_log": "confidential",
}


# --------------------------------------------------------------------------- passwords & tokens

def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    h = hashlib.scrypt(pw.encode(), salt=salt, n=2 ** 14, r=8, p=1)
    return f"scrypt${salt.hex()}${h.hex()}"


def verify_password(pw: str, stored: str) -> bool:
    try:
        _, salt, h = stored.split("$")
    except ValueError:
        return False
    calc = hashlib.scrypt(pw.encode(), salt=bytes.fromhex(salt), n=2 ** 14, r=8, p=1)
    return hmac.compare_digest(calc.hex(), h)


def create_token(user: dict) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    return jwt.encode({"sub": str(user["id"]), "role": user["role"], "email": user["email"],
                       "iat": now, "exp": now + dt.timedelta(hours=TOKEN_HOURS)}, SECRET, algorithm="HS256")


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


# --------------------------------------------------------------------------- current user

PUBLIC = {"id": None, "email": None, "name": "Public", "role": "public", "institution": None}


def current_user(authorization: str | None = Header(None), x_api_key: str | None = Header(None)) -> dict:
    """Bearer JWT -> user; X-API-Key -> partner system (researcher-level read access); nothing -> public."""
    if authorization and authorization.lower().startswith("bearer "):
        try:
            claims = jwt.decode(authorization[7:], SECRET, algorithms=["HS256"])
        except jwt.PyJWTError:
            raise HTTPException(401, "invalid or expired token")
        u = q1("SELECT id, email, name, role, institution, active FROM users WHERE id = ?", (int(claims["sub"]),))
        if not u or not u["active"]:
            raise HTTPException(401, "account disabled")
        return u
    if x_api_key:
        k = q1("SELECT id, name, owner_id FROM api_key WHERE key_hash = ? AND active = 1", (hash_key(x_api_key),))
        if not k:
            raise HTTPException(401, "invalid API key")
        return {"id": k["owner_id"], "email": None, "name": f"API: {k['name']}", "role": "researcher",
                "institution": "partner system", "api_key_id": k["id"]}
    return PUBLIC


def rank(role: str) -> int:
    return ROLES.index(role) if role in ROLES else 0


def require(min_role: str = "researcher"):
    """Dependency: user must be signed in with at least `min_role`."""
    def dep(user: dict = Depends(current_user)) -> dict:
        if user["role"] == "public":
            raise HTTPException(401, "sign in required")
        if rank(user["role"]) < rank(min_role):
            raise HTTPException(403, f"requires role '{min_role}' or higher")
        return user
    return dep


def require_any(*roles: str):
    def dep(user: dict = Depends(current_user)) -> dict:
        if user["role"] not in roles:
            raise HTTPException(403, f"requires one of: {', '.join(roles)}")
        return user
    return dep


def can_access(user: dict, dataset: str) -> bool:
    cls = DATASET_CLASS.get(dataset, "open")
    role = user["role"]
    if cls == "open":
        return True
    if cls == "registered":
        return role != "public"
    if cls == "restricted":
        if role in ("official", "admin"):
            return True
        return bool(user.get("id")) and bool(q1(
            "SELECT 1 FROM access_request WHERE user_id = ? AND dataset = ? AND status = 'approved'",
            (user["id"], dataset)))
    return role == "admin"  # confidential


# --------------------------------------------------------------------------- audit log (hash chain)

def audit(user: dict, action: str, resource: str = "", detail: dict | str | None = None) -> None:
    """Append-only; each entry stores the previous entry's hash, so any edit breaks the chain."""
    prev = q1("SELECT hash FROM audit_log ORDER BY id DESC LIMIT 1")
    prev_hash = prev["hash"] if prev else "0" * 64
    ts = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    det = detail if isinstance(detail, str) else json.dumps(detail or {}, sort_keys=True, default=str)
    body = json.dumps([ts, user.get("id"), user.get("email"), action, resource, det, prev_hash])
    execute("INSERT INTO audit_log (ts, user_id, user_email, action, resource, detail, prev_hash, hash) "
            "VALUES (?,?,?,?,?,?,?,?)", (ts, user.get("id"), user.get("email"), action, resource, det, prev_hash,
                                         hashlib.sha256(body.encode()).hexdigest()))


def verify_audit_chain() -> dict:
    prev, n = "0" * 64, 0
    for r in q("SELECT * FROM audit_log ORDER BY id"):
        body = json.dumps([r["ts"], r["user_id"], r["user_email"], r["action"], r["resource"], r["detail"], prev])
        if r["prev_hash"] != prev or hashlib.sha256(body.encode()).hexdigest() != r["hash"]:
            return {"valid": False, "entries_checked": n, "broken_at_id": r["id"]}
        prev, n = r["hash"], n + 1
    return {"valid": True, "entries_checked": n, "head_hash": prev}


# --------------------------------------------------------------------------- rate limiting

_hits: dict[str, list[float]] = {}


def rate_limited(request: Request, limit_per_min: int) -> bool:
    import time
    key = request.headers.get("x-api-key") or (request.client.host if request.client else "?")
    now = time.time()
    window = [t for t in _hits.get(key, []) if now - t < 60]
    window.append(now)
    _hits[key] = window
    return len(window) > limit_per_min
