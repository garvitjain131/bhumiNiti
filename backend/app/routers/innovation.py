"""
Innovation portal (#15) and the feedback loop: research gaps -> calls (grants, hackathons, pilots, competitions)
-> applications -> referee scoring -> award & milestones (DoLR grant workflow) -> pilots -> outcomes ->
researcher submissions -> review -> new evidence that updates the Gap Radar.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..core.db import execute, q, q1, rows
from ..core.security import audit, current_user, require

router = APIRouter(prefix="/api/v1", tags=["innovation portal & feedback loop"])

GRANT_STAGES = ["submitted", "under_review", "shortlisted", "awarded", "advance_released", "review_1", "review_2",
                "final_report", "completed"]
DOLR_SCHEMES = {
    "institutional_grant": {"name": "Institutional Research Grant", "per_year": 10, "max_lakh": 20, "years": 2},
    "individual_grant": {"name": "Individual Research Grant", "per_year": 20, "max_lakh": 10, "years": 2},
}
DISBURSEMENT = [("advance_released", 40, "40% advance on award"), ("review_2", 30, "2nd instalment after utilisation certificate"),
                ("completed", 30, "final instalment after final report")]


# --------------------------------------------------------------------------- research gap radar

@router.get("/gaps/states")
def gap_radar():
    """Where land problems are serious but research is thin. need = mean percentile of conflicts per 10 M people
    and share of parcels without ULPIN; coverage = land-relevant research items mentioning the state
    (incl. approved platform contributions). gap = need / ln(2 + coverage)."""
    contrib = {}
    for c in q("SELECT states FROM contribution WHERE status = 'approved'"):
        for s in json.loads(c["states"] or "[]"):
            contrib[s.upper()] = contrib.get(s.upper(), 0) + 1
    res = rows("""
        WITH cov AS (
            SELECT upper(s) AS state, count(*) AS evidence_items
            FROM (SELECT unnest(states) AS s FROM evidence_item WHERE land_score >= 4 AND source <> 'landconflictwatch')
            GROUP BY 1),
        pop AS (SELECT g.state_name, sum(i.value) AS population FROM indicator i JOIN geo_district g USING (district_lgd)
                WHERE i.indicator = 'pc11_pca_tot_p' GROUP BY 1),
        conf AS (SELECT soi_state, count(*) AS conflicts, sum(people_affected) AS people_affected FROM land_conflict GROUP BY 1)
        SELECT g.name AS state, g.state_lgd, coalesce(c.conflicts, 0) AS conflicts, c.people_affected,
               round(coalesce(c.conflicts, 0) / nullif(p.population, 0) * 1e7, 1) AS conflicts_per_10m,
               d.ulpin_pct, coalesce(v.evidence_items, 0) AS evidence_items
        FROM geo_state g JOIN dilrmp_state d ON d.soi_state_name = g.name
        LEFT JOIN pop p ON p.state_name = g.name LEFT JOIN conf c ON c.soi_state = g.name
        LEFT JOIN cov v ON v.state = g.name OR v.state = replace(g.name, ' & ', ' AND ')""")
    import numpy as np
    for r in res:
        r["evidence_items"] += contrib.get(r["state"], 0)
    for key, col in (("c", "conflicts_per_10m"), ("u", "ulpin_pct")):
        vals = np.array([(r[col] if r[col] is not None else 0) for r in res], float)
        if key == "u":
            vals = 100 - vals
        ranks = vals.argsort().argsort() / max(len(vals) - 1, 1)
        for r, pr in zip(res, ranks):
            r[f"_{key}"] = pr
    for r in res:
        r["need_index"] = round((r.pop("_c") + r.pop("_u")) / 2, 3)
        r["gap_score"] = round(r["need_index"] / np.log(2 + r["evidence_items"]), 3)
    res.sort(key=lambda r: -r["gap_score"])
    return res


class GapCall(BaseModel):
    state: str
    theme: str = "land_disputes"
    kind: str = Field("institutional_grant", pattern="^(institutional_grant|individual_grant|hackathon|pilot|competition)$")


@router.post("/gaps/to-call")
def gap_to_call(body: GapCall, user: dict = Depends(require("official"))):
    """Turn a Gap Radar finding into a draft call, pre-filled with what is known and what is missing."""
    g = next((r for r in gap_radar() if r["state"] == body.state.upper()), None)
    if not g:
        raise HTTPException(404, "state not found in the Gap Radar")
    known = rows("""SELECT title, year FROM evidence_item WHERE land_score >= 4 AND list_contains(states, ?)
                    ORDER BY cited_by DESC NULLS LAST LIMIT 5""", [body.state.title()])
    scheme = DOLR_SCHEMES.get(body.kind, {})
    desc = (f"Research gap identified by the platform's Gap Radar for {body.state.title()}: "
            f"{g['conflicts']} documented land conflicts ({g['conflicts_per_10m']} per 10 million people), "
            f"ULPIN coverage {g['ulpin_pct']}%, but only {g['evidence_items']} research items. "
            f"Theme: {body.theme.replace('_', ' ')}. Proposals should test a hypothesis with a stated method and "
            f"deposit data and findings on the platform.\n\nExisting evidence to build on:\n" +
            "\n".join(f"- {k['title']} ({k['year'] or 'n.d.'})" for k in known))
    cid = execute("""INSERT INTO call (kind, title, description, theme, geography, budget_lakh, opens, closes, status,
                     source_gap, created_by) VALUES (?,?,?,?,?,?,date('now'),date('now','+60 day'),'draft',?,?)""",
                  (body.kind, f"{scheme.get('name', body.kind.replace('_', ' ').title())}: {body.theme.replace('_', ' ')} in "
                              f"{body.state.title()}", desc, body.theme, body.state.title(), scheme.get("max_lakh"),
                   json.dumps(g, default=str), user["id"]))
    audit(user, "gap_to_call", f"call:{cid}", {"state": body.state})
    return q1("SELECT * FROM call WHERE id = ?", (cid,))


# --------------------------------------------------------------------------- calls

@router.get("/calls")
def calls(kind: str | None = None, status: str | None = None):
    return q("""SELECT c.*, (SELECT count(*) FROM application a WHERE a.call_id = c.id) AS applications
                FROM call c WHERE (? IS NULL OR kind = ?) AND (? IS NULL OR status = ?) ORDER BY c.id DESC""",
             (kind, kind, status, status))


@router.get("/calls/schemes")
def schemes():
    return {"dolr_grant_schemes": DOLR_SCHEMES, "grant_stages": GRANT_STAGES,
            "disbursement": [{"after_stage": s, "pct": p, "note": n} for s, p, n in DISBURSEMENT]}


class NewCall(BaseModel):
    kind: str = Field(pattern="^(institutional_grant|individual_grant|hackathon|pilot|competition)$")
    title: str = Field(min_length=5, max_length=200)
    description: str = Field(min_length=20)
    theme: str | None = None
    geography: str | None = None
    budget_lakh: float | None = None
    closes: str | None = None
    status: str = Field("open", pattern="^(draft|open|closed)$")


@router.post("/calls")
def create_call(body: NewCall, user: dict = Depends(require("official"))):
    cid = execute("""INSERT INTO call (kind, title, description, theme, geography, budget_lakh, opens, closes, status, created_by)
                     VALUES (?,?,?,?,?,?,date('now'),?,?,?)""",
                  (body.kind, body.title, body.description, body.theme, body.geography, body.budget_lakh, body.closes,
                   body.status, user["id"]))
    audit(user, "call_create", f"call:{cid}")
    return q1("SELECT * FROM call WHERE id = ?", (cid,))


@router.post("/calls/{cid}/status")
def call_status(cid: int, status: str = Query(pattern="^(draft|open|closed|awarded)$"),
                user: dict = Depends(require("official"))):
    execute("UPDATE call SET status = ? WHERE id = ?", (status, cid))
    audit(user, "call_status", f"call:{cid}", {"status": status})
    return q1("SELECT * FROM call WHERE id = ?", (cid,))


@router.get("/calls/{cid}")
def get_call(cid: int, user: dict = Depends(current_user)):
    c = q1("SELECT * FROM call WHERE id = ?", (cid,))
    if not c:
        raise HTTPException(404, "call not found")
    see_all = user["role"] in ("reviewer", "official", "admin")
    c["applications"] = q("""SELECT a.*, u.name AS applicant, u.institution,
                                    (SELECT round(avg(score), 1) FROM review r WHERE r.application_id = a.id
                                     AND conflict_of_interest = 0) AS avg_score,
                                    (SELECT count(*) FROM review r WHERE r.application_id = a.id) AS reviews
                             FROM application a JOIN users u ON u.id = a.applicant_id
                             WHERE call_id = ? AND (? OR applicant_id = ?) ORDER BY avg_score DESC NULLS LAST""",
                          (cid, see_all, user.get("id")))
    return c


class Apply(BaseModel):
    title: str = Field(min_length=5, max_length=250)
    hypothesis: str = Field(min_length=20)
    methodology: str = Field(min_length=20)
    budget_lakh: float = Field(gt=0)


@router.post("/calls/{cid}/applications")
def apply(cid: int, body: Apply, user: dict = Depends(require("researcher"))):
    c = q1("SELECT * FROM call WHERE id = ?", (cid,))
    if not c or c["status"] != "open":
        raise HTTPException(400, "call is not open")
    if c["budget_lakh"] and body.budget_lakh > c["budget_lakh"]:
        raise HTTPException(400, f"budget exceeds the scheme limit of Rs {c['budget_lakh']} lakh")
    aid = execute("INSERT INTO application (call_id, applicant_id, title, hypothesis, methodology, budget_lakh) VALUES (?,?,?,?,?,?)",
                  (cid, user["id"], body.title, body.hypothesis, body.methodology, body.budget_lakh))
    audit(user, "application_submit", f"application:{aid}")
    return q1("SELECT * FROM application WHERE id = ?", (aid,))


@router.get("/applications/mine")
def my_applications(user: dict = Depends(require("researcher"))):
    return q("""SELECT a.*, c.title AS call_title, c.kind FROM application a JOIN call c ON c.id = a.call_id
                WHERE applicant_id = ? ORDER BY a.id DESC""", (user["id"],))


class Review(BaseModel):
    score: int = Field(ge=0, le=100)
    comments: str = Field(min_length=10)
    conflict_of_interest: bool = False


@router.post("/applications/{aid}/reviews")
def review(aid: int, body: Review, user: dict = Depends(require("reviewer"))):
    """Referee scoring. Reviewers declare conflicts of interest; declared reviews are excluded from the average,
    and reviewers cannot score their own institution's applications."""
    a = q1("SELECT a.*, u.institution FROM application a JOIN users u ON u.id = a.applicant_id WHERE a.id = ?", (aid,))
    if not a:
        raise HTTPException(404, "application not found")
    if a["applicant_id"] == user["id"]:
        raise HTTPException(403, "you cannot review your own application")
    coi = body.conflict_of_interest or bool(a["institution"] and a["institution"] == user.get("institution"))
    execute("INSERT OR REPLACE INTO review (application_id, reviewer_id, score, comments, conflict_of_interest) VALUES (?,?,?,?,?)",
            (aid, user["id"], body.score, body.comments, int(coi)))
    if a["stage"] == "submitted":
        execute("UPDATE application SET stage = 'under_review' WHERE id = ?", (aid,))
    audit(user, "review_submit", f"application:{aid}", {"score": body.score, "coi": coi})
    return {"ok": True, "conflict_of_interest_recorded": coi}


@router.post("/applications/{aid}/advance")
def advance(aid: int, to: str = Query(...), user: dict = Depends(require("official"))):
    """Move an application through the DoLR grant workflow; awarding creates a pilot record."""
    if to not in GRANT_STAGES + ["rejected"]:
        raise HTTPException(400, f"stage must be one of {GRANT_STAGES + ['rejected']}")
    a = q1("SELECT a.*, c.geography, c.kind FROM application a JOIN call c ON c.id = a.call_id WHERE a.id = ?", (aid,))
    if not a:
        raise HTTPException(404, "application not found")
    execute("UPDATE application SET stage = ? WHERE id = ?", (to, aid))
    if to == "awarded" and not q1("SELECT 1 FROM pilot WHERE application_id = ?", (aid,)):
        execute("INSERT INTO pilot (application_id, title, state, status, start_date) VALUES (?,?,?, 'running', date('now'))",
                (aid, a["title"], a["geography"]))
    audit(user, "application_stage", f"application:{aid}", {"to": to})
    released = sum(p for s, p, _ in DISBURSEMENT if to in GRANT_STAGES and GRANT_STAGES.index(to) >= GRANT_STAGES.index(s))
    return {**q1("SELECT * FROM application WHERE id = ?", (aid,)), "funds_released_pct": released}


# --------------------------------------------------------------------------- pilots & outcomes

@router.get("/pilots")
def pilots():
    return q("""SELECT p.*, a.budget_lakh, u.name AS lead, (SELECT count(*) FROM outcome o WHERE o.pilot_id = p.id) AS outcomes
                FROM pilot p LEFT JOIN application a ON a.id = p.application_id LEFT JOIN users u ON u.id = a.applicant_id
                ORDER BY p.id DESC""")


class OutcomeIn(BaseModel):
    indicator: str
    baseline: float
    result: float
    unit: str
    notes: str | None = None


@router.post("/pilots/{pid}/outcomes")
def add_outcome(pid: int, body: OutcomeIn, user: dict = Depends(require("researcher"))):
    """Report a measured pilot outcome. It is also filed as a contribution, so it enters the evidence base on review."""
    p = q1("SELECT p.*, a.applicant_id FROM pilot p LEFT JOIN application a ON a.id = p.application_id WHERE p.id = ?", (pid,))
    if not p:
        raise HTTPException(404, "pilot not found")
    if user["role"] not in ("official", "admin") and p["applicant_id"] != user["id"]:
        raise HTTPException(403, "only the pilot lead or an official can report outcomes")
    change = body.result - body.baseline
    cid = execute("""INSERT INTO contribution (submitter_id, kind, title, abstract, method, finding_direction, states, themes, pilot_id)
                     VALUES (?,?,?,?,?,?,?,?,?)""",
                  (user["id"], "pilot_outcome", f"Pilot outcome: {p['title']} - {body.indicator}",
                   f"Measured {body.indicator} moved from {body.baseline} to {body.result} {body.unit} ({change:+.2f}). "
                   f"{body.notes or ''}", "Pilot measurement (before/after)",
                   "positive" if change > 0 else "negative" if change < 0 else "no clear effect",
                   json.dumps([p["state"]] if p["state"] else []), json.dumps(["pilot_outcome"]), pid))
    oid = execute("INSERT INTO outcome (pilot_id, indicator, baseline, result, unit, notes, contribution_id) VALUES (?,?,?,?,?,?,?)",
                  (pid, body.indicator, body.baseline, body.result, body.unit, body.notes, cid))
    audit(user, "pilot_outcome", f"pilot:{pid}", {"outcome": oid})
    return {"outcome_id": oid, "contribution_id": cid, "status": "submitted for review"}


# --------------------------------------------------------------------------- researcher submissions (feedback loop)

class Contribution(BaseModel):
    kind: str = Field(pattern="^(finding|paper|dataset|case_study|policy_note)$")
    title: str = Field(min_length=5, max_length=300)
    abstract: str = Field(min_length=50, max_length=5000)
    method: str | None = None
    finding_direction: str | None = Field(None, pattern="^(positive|negative|no clear effect|descriptive|mixed)$")
    states: list[str] = Field(default_factory=list)
    themes: list[str] = Field(default_factory=list)
    district_lgd: int | None = None
    url: str | None = None
    call_id: int | None = None


@router.post("/contributions")
def submit(body: Contribution, user: dict = Depends(require("researcher"))):
    """Researchers submit findings; after review they join the evidence base, update the Gap Radar,
    and appear in search and in the assistant's answers."""
    cid = execute("""INSERT INTO contribution (submitter_id, kind, title, abstract, method, finding_direction, states, themes,
                     district_lgd, url, call_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                  (user["id"], body.kind, body.title, body.abstract, body.method, body.finding_direction,
                   json.dumps(body.states), json.dumps(body.themes), body.district_lgd, body.url, body.call_id))
    audit(user, "contribution_submit", f"contribution:{cid}")
    return q1("SELECT * FROM contribution WHERE id = ?", (cid,))


@router.get("/contributions")
def list_contributions(status: str | None = None, user: dict = Depends(current_user)):
    if user["role"] in ("reviewer", "official", "admin"):
        return q("""SELECT c.*, u.name AS submitter, u.institution FROM contribution c JOIN users u ON u.id = c.submitter_id
                    WHERE (? IS NULL OR status = ?) ORDER BY c.status = 'submitted' DESC, c.id DESC""", (status, status))
    if user["role"] == "public":
        return q("SELECT id, kind, title, abstract, states, themes, created_at FROM contribution WHERE status = 'approved' ORDER BY id DESC")
    return q("""SELECT * FROM contribution WHERE submitter_id = ? OR status = 'approved' ORDER BY id DESC""", (user["id"],))


class Decide(BaseModel):
    approve: bool
    note: str | None = None


@router.post("/contributions/{cid}/decide")
def decide(cid: int, body: Decide, user: dict = Depends(require("reviewer"))):
    c = q1("SELECT * FROM contribution WHERE id = ?", (cid,))
    if not c:
        raise HTTPException(404, "contribution not found")
    if c["submitter_id"] == user["id"]:
        raise HTTPException(403, "you cannot review your own submission")
    status = "approved" if body.approve else "rejected"
    execute("UPDATE contribution SET status = ?, reviewer_id = ?, review_note = ?, decided_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, user["id"], body.note, cid))
    audit(user, f"contribution_{status}", f"contribution:{cid}")
    return {**q1("SELECT * FROM contribution WHERE id = ?", (cid,)),
            "effect": "now searchable and counted in the Gap Radar; included in the next index rebuild" if body.approve else None}
