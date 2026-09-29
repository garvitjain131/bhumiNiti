"""
Collaborative workspaces (#9): a workspace starts from a policy question; members (owner/editor/viewer)
collect evidence, write versioned notes, comment, assign tasks and send findings through review.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..core.db import execute, one, q, q1
from ..core.security import audit, require
from ..services import search

router = APIRouter(prefix="/api/v1/workspaces", tags=["collaborative workspaces"])
WRITE = ("owner", "editor")


def member_role(ws_id: int, user: dict) -> str | None:
    if user["role"] == "admin":
        return "owner"
    m = q1("SELECT role FROM workspace_member WHERE workspace_id = ? AND user_id = ?", (ws_id, user["id"]))
    return m["role"] if m else None


def need(ws_id: int, user: dict, roles=("owner", "editor", "viewer")) -> str:
    if not q1("SELECT 1 FROM workspace WHERE id = ?", (ws_id,)):
        raise HTTPException(404, "workspace not found")
    r = member_role(ws_id, user)
    if r not in roles:
        raise HTTPException(403, "you are not a member with the required role in this workspace")
    return r


class NewWorkspace(BaseModel):
    name: str = Field(min_length=3, max_length=150)
    question: str = Field(min_length=10, max_length=1000, description="the policy question this work answers")
    description: str | None = None
    geography: str | None = None
    period: str | None = None
    indicators: str | None = None


@router.post("")
def create(body: NewWorkspace, user: dict = Depends(require("researcher"))):
    wid = execute("INSERT INTO workspace (name, question, description, geography, period, indicators, owner_id) "
                  "VALUES (?,?,?,?,?,?,?)", (body.name, body.question, body.description, body.geography, body.period,
                                              body.indicators, user["id"]))
    execute("INSERT INTO workspace_member VALUES (?,?,?)", (wid, user["id"], "owner"))
    audit(user, "workspace_create", f"workspace:{wid}")
    return get(wid, user)


@router.get("")
def mine(user: dict = Depends(require("researcher"))):
    return q("""SELECT w.*, m.role AS my_role, u.name AS owner_name,
                       (SELECT count(*) FROM workspace_item i WHERE i.workspace_id = w.id) AS items,
                       (SELECT count(*) FROM workspace_member x WHERE x.workspace_id = w.id) AS members
                FROM workspace w JOIN workspace_member m ON m.workspace_id = w.id AND m.user_id = ?
                JOIN users u ON u.id = w.owner_id ORDER BY w.id DESC""", (user["id"],))


@router.get("/{wid}")
def get(wid: int, user: dict = Depends(require("researcher"))):
    role = need(wid, user)
    ws = q1("SELECT * FROM workspace WHERE id = ?", (wid,))
    items = q("SELECT * FROM workspace_item WHERE workspace_id = ? ORDER BY id DESC", (wid,))
    if items:
        from ..core.db import rows
        meta = {r["evidence_id"]: r for r in rows(
            "SELECT evidence_id, title, year, source, type_group, url FROM evidence_item WHERE list_contains(?, evidence_id)",
            [[i["evidence_id"] for i in items]])}
        for i in items:
            i["evidence"] = meta.get(i["evidence_id"])
    notes = q("""SELECT n.*, u.name AS author FROM workspace_note n JOIN users u ON u.id = n.author_id
                 WHERE workspace_id = ? AND version = (SELECT max(version) FROM workspace_note x
                                                       WHERE x.workspace_id = n.workspace_id AND x.note_key = n.note_key)
                 ORDER BY n.id DESC""", (wid,))
    return {**ws, "my_role": role,
            "members": q("""SELECT u.id, u.name, u.email, u.role AS platform_role, u.institution, m.role
                            FROM workspace_member m JOIN users u ON u.id = m.user_id WHERE m.workspace_id = ?""", (wid,)),
            "items": items, "notes": notes,
            "comments": q("""SELECT c.*, u.name AS author FROM workspace_comment c JOIN users u ON u.id = c.author_id
                             WHERE workspace_id = ? ORDER BY c.id""", (wid,)),
            "tasks": q("""SELECT t.*, u.name AS assignee FROM workspace_task t LEFT JOIN users u ON u.id = t.assignee_id
                          WHERE workspace_id = ? ORDER BY t.status, t.id""", (wid,))}


class Member(BaseModel):
    email: str
    role: str = Field("editor", pattern="^(editor|viewer)$")


@router.post("/{wid}/members")
def add_member(wid: int, body: Member, user: dict = Depends(require("researcher"))):
    need(wid, user, ("owner",))
    u = q1("SELECT id FROM users WHERE email = ?", (body.email.lower(),))
    if not u:
        raise HTTPException(404, "no user with that email")
    execute("INSERT OR REPLACE INTO workspace_member VALUES (?,?,?)", (wid, u["id"], body.role))
    audit(user, "workspace_add_member", f"workspace:{wid}", {"member": body.email, "role": body.role})
    return {"ok": True}


class Item(BaseModel):
    evidence_id: str
    note: str | None = None
    stance: str | None = Field(None, pattern="^(supports|contradicts|context)$")


@router.post("/{wid}/items")
def add_item(wid: int, body: Item, user: dict = Depends(require("researcher"))):
    need(wid, user, WRITE)
    if not one("SELECT 1 FROM evidence_item WHERE evidence_id = ?", [body.evidence_id]) and \
            not body.evidence_id.startswith("contribution:"):
        raise HTTPException(404, "evidence item not found")
    execute("INSERT OR IGNORE INTO workspace_item (workspace_id, evidence_id, note, stance, added_by) VALUES (?,?,?,?,?)",
            (wid, body.evidence_id, body.note, body.stance, user["id"]))
    return {"ok": True}


@router.delete("/{wid}/items/{item_id}")
def remove_item(wid: int, item_id: int, user: dict = Depends(require("researcher"))):
    need(wid, user, WRITE)
    execute("DELETE FROM workspace_item WHERE id = ? AND workspace_id = ?", (item_id, wid))
    return {"ok": True}


@router.get("/{wid}/recommendations")
def ws_recommendations(wid: int, user: dict = Depends(require("researcher"))):
    """Suggestions based on everything already in the collection."""
    need(wid, user)
    ids = [i["evidence_id"] for i in q("SELECT evidence_id FROM workspace_item WHERE workspace_id = ?", (wid,))]
    if not ids:
        ws = q1("SELECT question FROM workspace WHERE id = ?", (wid,))
        return search.hybrid(ws["question"], limit=10)["results"]
    return search.recommend_for_set(ids)


class Note(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    body: str = Field(min_length=1, max_length=50000)
    note_key: str | None = Field(None, description="omit to start a new note; pass an existing key to save a new version")


@router.post("/{wid}/notes")
def save_note(wid: int, body: Note, user: dict = Depends(require("researcher"))):
    """Every save is a new version; earlier versions are kept."""
    need(wid, user, WRITE)
    import uuid
    key = body.note_key or uuid.uuid4().hex[:10]
    v = q1("SELECT coalesce(max(version), 0) AS v FROM workspace_note WHERE workspace_id = ? AND note_key = ?", (wid, key))["v"]
    nid = execute("INSERT INTO workspace_note (workspace_id, note_key, title, body, version, author_id) VALUES (?,?,?,?,?,?)",
                  (wid, key, body.title, body.body, v + 1, user["id"]))
    return q1("SELECT * FROM workspace_note WHERE id = ?", (nid,))


@router.get("/{wid}/notes/{key}/history")
def note_history(wid: int, key: str, user: dict = Depends(require("researcher"))):
    need(wid, user)
    return q("""SELECT n.id, n.version, n.title, n.body, n.status, n.created_at, u.name AS author FROM workspace_note n
                JOIN users u ON u.id = n.author_id WHERE workspace_id = ? AND note_key = ? ORDER BY version DESC""", (wid, key))


class Status(BaseModel):
    status: str = Field(pattern="^(in_review|approved|changes_requested|draft)$")


@router.post("/{wid}/notes/{note_id}/status")
def note_status(wid: int, note_id: int, body: Status, user: dict = Depends(require("researcher"))):
    """Request review (editors) or approve / request changes (reviewers, officials, owners)."""
    role = need(wid, user)
    if body.status in ("approved", "changes_requested") and role != "owner" and user["role"] not in ("reviewer", "official", "admin"):
        raise HTTPException(403, "only the owner or a reviewer/official can approve")
    if body.status == "in_review" and role not in WRITE:
        raise HTTPException(403, "only editors can request review")
    execute("UPDATE workspace_note SET status = ? WHERE id = ? AND workspace_id = ?", (body.status, note_id, wid))
    audit(user, f"note_{body.status}", f"workspace:{wid}/note:{note_id}")
    return {"ok": True, "status": body.status}


class Comment(BaseModel):
    body: str = Field(min_length=1, max_length=5000)
    target: str | None = Field(None, description="e.g. note:12 or evidence:openalex:W123")


@router.post("/{wid}/comments")
def comment(wid: int, body: Comment, user: dict = Depends(require("researcher"))):
    need(wid, user)  # viewers may comment
    execute("INSERT INTO workspace_comment (workspace_id, target, body, author_id) VALUES (?,?,?,?)",
            (wid, body.target, body.body, user["id"]))
    return {"ok": True}


class Task(BaseModel):
    title: str = Field(min_length=2, max_length=300)
    assignee_email: str | None = None


@router.post("/{wid}/tasks")
def add_task(wid: int, body: Task, user: dict = Depends(require("researcher"))):
    need(wid, user, WRITE)
    aid = None
    if body.assignee_email:
        u = q1("SELECT id FROM users WHERE email = ?", (body.assignee_email.lower(),))
        aid = u["id"] if u else None
    execute("INSERT INTO workspace_task (workspace_id, title, assignee_id) VALUES (?,?,?)", (wid, body.title, aid))
    return {"ok": True}


@router.post("/{wid}/tasks/{tid}/toggle")
def toggle_task(wid: int, tid: int, user: dict = Depends(require("researcher"))):
    need(wid, user, WRITE)
    execute("UPDATE workspace_task SET status = CASE status WHEN 'open' THEN 'done' ELSE 'open' END WHERE id = ? "
            "AND workspace_id = ?", (tid, wid))
    return {"ok": True}


@router.get("/{wid}/bibliography")
def bibliography(wid: int, fmt: str = "bibtex", user: dict = Depends(require("researcher"))):
    """Export the collection as BibTeX or RIS."""
    need(wid, user)
    from ..core.db import rows
    ids = [i["evidence_id"] for i in q("SELECT evidence_id FROM workspace_item WHERE workspace_id = ?", (wid,))]
    items = rows("SELECT evidence_id, title, authors, year, source_org, doi, url FROM evidence_item "
                 "WHERE list_contains(?, evidence_id)", [ids]) if ids else []
    out = []
    for i, e in enumerate(items):
        authors = " and ".join(e["authors"] or []) or (e["source_org"] or "")
        if fmt == "ris":
            out.append("\n".join(["TY  - GEN", f"TI  - {e['title']}", *(f"AU  - {a}" for a in (e["authors"] or [])),
                                  f"PY  - {e['year'] or ''}", f"PB  - {e['source_org'] or ''}", f"DO  - {e['doi'] or ''}",
                                  f"UR  - {e['url'] or ''}", "ER  - "]))
        else:
            out.append(f"@misc{{lpip{i + 1},\n  title = {{{e['title']}}},\n  author = {{{authors}}},\n  year = {{{e['year'] or ''}}},\n"
                       f"  publisher = {{{e['source_org'] or ''}}},\n  doi = {{{(e['doi'] or '').replace('https://doi.org/', '')}}},\n"
                       f"  url = {{{e['url'] or ''}}}\n}}")
    return {"format": fmt, "count": len(out), "text": "\n\n".join(out)}
