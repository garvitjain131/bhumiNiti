"""Accounts, roles, API keys, access requests, and the audit log."""
from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..core.db import execute, q, q1
from ..core.security import (DATASET_CLASS, ROLES, audit, can_access, create_token, current_user, hash_key,
                             hash_password, require, verify_audit_chain, verify_password)

router = APIRouter(prefix="/api/v1", tags=["auth & access"])


EMAIL = r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$"


class Register(BaseModel):
    email: str = Field(pattern=EMAIL, max_length=200)
    name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=10, max_length=200)
    institution: str | None = None


class Login(BaseModel):
    email: str = Field(pattern=EMAIL, max_length=200)
    password: str


@router.post("/auth/register")
def register(body: Register):
    """Self-registration always creates a researcher; higher roles are granted by an admin."""
    if q1("SELECT 1 FROM users WHERE email = ?", (body.email.lower(),)):
        raise HTTPException(409, "email already registered")
    uid = execute("INSERT INTO users (email, name, pw_hash, role, institution) VALUES (?,?,?,?,?)",
                  (body.email.lower(), body.name, hash_password(body.password), "researcher", body.institution))
    user = q1("SELECT id, email, name, role, institution FROM users WHERE id = ?", (uid,))
    audit(user, "register", f"user:{uid}")
    return {"token": create_token(user), "user": user}


@router.post("/auth/login")
def login(body: Login):
    u = q1("SELECT * FROM users WHERE email = ? AND active = 1", (body.email.lower(),))
    if not u or not verify_password(body.password, u["pw_hash"]):
        audit({"id": None, "email": body.email.lower()}, "login_failed", "auth")
        raise HTTPException(401, "wrong email or password")
    user = {k: u[k] for k in ("id", "email", "name", "role", "institution")}
    audit(user, "login", "auth")
    return {"token": create_token(user), "user": user}


@router.get("/auth/me")
def me(user: dict = Depends(current_user)):
    datasets = {d: can_access(user, d) for d in DATASET_CLASS}
    return {"user": user, "roles": ROLES, "dataset_access": datasets}


# --------------------------------------------------------------------------- admin: users & API keys

@router.get("/admin/users")
def list_users(_: dict = Depends(require("admin"))):
    return q("SELECT id, email, name, role, institution, active, created_at FROM users ORDER BY id")


class RoleChange(BaseModel):
    role: str
    active: bool = True


@router.patch("/admin/users/{uid}")
def change_role(uid: int, body: RoleChange, admin: dict = Depends(require("admin"))):
    if body.role not in ROLES[1:]:
        raise HTTPException(400, f"role must be one of {ROLES[1:]}")
    execute("UPDATE users SET role = ?, active = ? WHERE id = ?", (body.role, int(body.active), uid))
    audit(admin, "change_role", f"user:{uid}", body.model_dump())
    return q1("SELECT id, email, name, role, active FROM users WHERE id = ?", (uid,))


class NewKey(BaseModel):
    name: str = Field(min_length=3, max_length=80)


@router.post("/admin/api-keys")
def create_api_key(body: NewKey, admin: dict = Depends(require("admin"))):
    """Key for a partner system (e.g. a state Land Stack, a university repository). Shown once."""
    key = "lpip_" + secrets.token_urlsafe(32)
    kid = execute("INSERT INTO api_key (name, key_hash, owner_id) VALUES (?,?,?)", (body.name, hash_key(key), admin["id"]))
    audit(admin, "create_api_key", f"api_key:{kid}", {"name": body.name})
    return {"id": kid, "name": body.name, "key": key, "note": "store it now; only its hash is kept"}


@router.get("/admin/api-keys")
def list_api_keys(_: dict = Depends(require("admin"))):
    return q("SELECT id, name, active, created_at FROM api_key ORDER BY id")


@router.delete("/admin/api-keys/{kid}")
def revoke_api_key(kid: int, admin: dict = Depends(require("admin"))):
    execute("UPDATE api_key SET active = 0 WHERE id = ?", (kid,))
    audit(admin, "revoke_api_key", f"api_key:{kid}")
    return {"revoked": kid}


# --------------------------------------------------------------------------- access requests

class AccessReq(BaseModel):
    dataset: str
    purpose: str = Field(min_length=20, max_length=2000)


@router.post("/access-requests")
def request_access(body: AccessReq, user: dict = Depends(require("researcher"))):
    if body.dataset not in DATASET_CLASS:
        raise HTTPException(404, "unknown dataset")
    if DATASET_CLASS[body.dataset] == "confidential":
        raise HTTPException(403, "confidential data is not available on request")
    rid = execute("INSERT INTO access_request (user_id, dataset, purpose) VALUES (?,?,?)",
                  (user["id"], body.dataset, body.purpose))
    audit(user, "request_access", f"dataset:{body.dataset}", {"request": rid})
    return q1("SELECT * FROM access_request WHERE id = ?", (rid,))


@router.get("/access-requests")
def list_access_requests(user: dict = Depends(require("researcher"))):
    if user["role"] in ("official", "admin"):
        return q("""SELECT r.*, u.email, u.name, u.institution FROM access_request r JOIN users u ON u.id = r.user_id
                    ORDER BY r.status = 'pending' DESC, r.id DESC""")
    return q("SELECT * FROM access_request WHERE user_id = ? ORDER BY id DESC", (user["id"],))


class Decision(BaseModel):
    approve: bool


@router.post("/access-requests/{rid}/decide")
def decide_access(rid: int, body: Decision, user: dict = Depends(require("official"))):
    r = q1("SELECT * FROM access_request WHERE id = ?", (rid,))
    if not r:
        raise HTTPException(404, "request not found")
    status = "approved" if body.approve else "rejected"
    execute("UPDATE access_request SET status = ?, decided_by = ?, decided_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, user["id"], rid))
    audit(user, f"access_{status}", f"dataset:{r['dataset']}", {"request": rid, "requester": r["user_id"]})
    return q1("SELECT * FROM access_request WHERE id = ?", (rid,))


# --------------------------------------------------------------------------- audit

@router.get("/audit")
def audit_log(limit: int = 200, _: dict = Depends(require("admin"))):
    return q("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,))


@router.get("/audit/verify")
def audit_verify():
    """Anyone can check that the audit log has not been altered (hash chain intact)."""
    return verify_audit_chain()
