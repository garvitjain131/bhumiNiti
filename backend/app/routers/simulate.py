"""Policy simulation lab (#12, #14 scenario analysis): run, compare, reproduce, export a brief."""
from __future__ import annotations

import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..core.db import execute, q, q1
from ..core.security import audit, current_user
from ..services import sim

router = APIRouter(prefix="/api/v1/simulations", tags=["policy simulation"])


@router.get("/levers")
def levers():
    return [{"id": k, "name": v["name"], "question": v["question"], "model_id": v["model_id"],
             "default_params": v["params"], "param_help": v["param_help"]} for k, v in sim.LEVERS.items()]


class RunReq(BaseModel):
    lever: str
    params: dict = Field(default_factory=dict)
    seed: int = 42
    draws: int = Field(2000, ge=200, le=10000)
    label: str | None = None


def _run(body: RunReq) -> dict:
    if body.lever not in sim.LEVERS:
        raise HTTPException(404, f"unknown lever; choose from {list(sim.LEVERS)}")
    try:
        return sim.run(body.lever, body.params, body.seed, body.draws)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/run")
def run(body: RunReq, user: dict = Depends(current_user)):
    """Run one scenario. Stored with its inputs, seed and hash so anyone can reproduce it."""
    out = _run(body)
    rid = execute("INSERT INTO sim_run (user_id, lever, params, seed, result, hash) VALUES (?,?,?,?,?,?)",
                  (user.get("id"), body.lever, json.dumps(out["params"], default=str), body.seed,
                   json.dumps(out, default=str), out["hash"]))
    out["run_id"] = rid
    out["label"] = body.label
    audit(user, "simulation_run", f"sim_run:{rid}", {"lever": body.lever, "hash": out["hash"]})
    return out


class CompareReq(BaseModel):
    lever: str
    scenarios: list[dict] = Field(min_length=1, max_length=4, description="list of {label, params}")
    seed: int = 42


@router.post("/compare")
def compare(body: CompareReq, user: dict = Depends(current_user)):
    """Side-by-side scenarios on the same random seed (differences come from the policy, not from noise)."""
    out = []
    for sc in body.scenarios:
        r = _run(RunReq(lever=body.lever, params=sc.get("params", {}), seed=body.seed))
        r["label"] = sc.get("label") or f"Scenario {len(out) + 1}"
        out.append(r)
    audit(user, "simulation_compare", body.lever, {"scenarios": [s.get("label") for s in body.scenarios]})
    return {"lever": body.lever, "seed": body.seed, "scenarios": out}


@router.get("/runs")
def runs(limit: int = 30):
    return q("SELECT id, lever, params, seed, hash, created_at FROM sim_run ORDER BY id DESC LIMIT ?", (limit,))


@router.get("/runs/{rid}")
def get_run(rid: int):
    r = q1("SELECT * FROM sim_run WHERE id = ?", (rid,))
    if not r:
        raise HTTPException(404, "run not found")
    return {**json.loads(r["result"]), "run_id": r["id"], "created_at": r["created_at"]}


@router.post("/runs/{rid}/reproduce")
def reproduce(rid: int):
    """Re-run with the stored inputs and seed; identical output proves reproducibility."""
    r = q1("SELECT * FROM sim_run WHERE id = ?", (rid,))
    if not r:
        raise HTTPException(404, "run not found")
    stored = json.loads(r["result"])
    again = sim.run(r["lever"], json.loads(r["params"]), r["seed"], stored.get("draws", 2000))
    same = json.dumps(again["impact"], sort_keys=True, default=str) == json.dumps(stored["impact"], sort_keys=True, default=str)
    return {"run_id": rid, "hash": r["hash"], "identical_results": same}


@router.get("/runs/{rid}/brief")
def brief(rid: int, user: dict = Depends(current_user)):
    """Policy brief (markdown) listing every assumption and source, with a content hash for verification."""
    r = q1("SELECT * FROM sim_run WHERE id = ?", (rid,))
    if not r:
        raise HTTPException(404, "run not found")
    o = json.loads(r["result"])
    lines = [f"# Policy brief: {o['lever_name']}", "",
             f"*Scenario run #{rid} · model {o['model_id']} · seed {o['seed']} · {o['draws']} Monte Carlo draws · "
             f"generated from platform data; SIMULATED, not a forecast.*", "",
             "## Headline", o["headline"], "", "## Scenario settings"]
    lines += [f"- **{k}**: {v}" for k, v in o["params"].items() if v not in (None, {}, [])]
    lines += ["", "## Assumptions and evidence grades", "| Coefficient | Range | Grade | Source |", "|---|---|---|---|"]
    lines += [f"| {c['name']} | {c['low']:.3g} – {c['high']:.3g} {c['unit']} | {c['grade']} | {c['source']} |"
              for c in o["coefficients"]]
    lines += ["", "## What drives the result (sensitivity)"]
    lines += [f"{i + 1}. {t['parameter']}: swing {t['swing']:,.1f} {o['unit']}" for i, t in enumerate(o["tornado"])]
    lines += ["", "## Context", *(f"- {k}: {v}" for k, v in o["context"].items()), "",
              "## Limitations", "- " + o["disclaimer"],
              "- Grade C coefficients are expert assumptions: commission research to replace them (see the "
              "Innovation Portal).", ""]
    text = "\n".join(lines)
    digest = hashlib.sha256(text.encode()).hexdigest()
    audit(user, "brief_export", f"sim_run:{rid}", {"sha256": digest})
    return {"run_id": rid, "markdown": text + f"\n---\nVerification hash (SHA-256): `{digest}`\n", "sha256": digest}


class VerifyReq(BaseModel):
    markdown: str


@router.post("/verify-brief")
def verify_brief(body: VerifyReq):
    """Paste an exported brief: checks its hash against the audit log to prove it is unaltered."""
    text, _, tail = body.markdown.rpartition("\n---\nVerification hash (SHA-256): `")
    claimed = tail.split("`")[0] if tail else ""
    actual = hashlib.sha256(text.encode()).hexdigest()
    logged = q1("SELECT ts, resource FROM audit_log WHERE action = 'brief_export' AND detail LIKE ?", (f"%{actual}%",))
    return {"hash_matches_content": bool(claimed) and claimed == actual, "found_in_audit_log": bool(logged),
            "issued": logged, "sha256": actual}
