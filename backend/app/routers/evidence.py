"""Centralised repository (#7), AI search & recommendations (#8), research assistant (#14)."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ..core.config import DATA
from ..core.db import execute, one, rows
from ..core.security import audit, current_user
from ..services import research_assistant, search, synthesis

router = APIRouter(prefix="/api/v1", tags=["repository & AI search"])


@router.get("/evidence/search")
def search_evidence(q: str = Query(..., min_length=2, description="plain-language query"),
                    state: str | None = Query(None, description="e.g. 'Odisha'"), theme: str | None = None,
                    source: str | None = None, type_group: str | None = None, year_from: int | None = None,
                    year_to: int | None = None, min_relevance: int = Query(4, ge=0),
                    limit: int = Query(20, le=100), offset: int = 0):
    """Hybrid search: keyword (BM25) + semantic similarity, fused by reciprocal rank, with filters."""
    return search.hybrid(q, state=state, theme=theme, source=source, type_group=type_group, year_from=year_from,
                         year_to=year_to, min_relevance=min_relevance, limit=limit, offset=offset)


@router.get("/evidence/browse")
def browse(type_group: str | None = None, source: str | None = None, state: str | None = None,
           theme: str | None = None, sort: str = Query("recent", pattern="^(recent|cited)$"),
           limit: int = Query(30, le=200), offset: int = 0):
    """Browse the repository without a query (e.g. all legal documents, all case studies in Odisha)."""
    order = "year DESC NULLS LAST" if sort == "recent" else "cited_by DESC NULLS LAST"
    return rows(f"""
        SELECT {search.FIELDS} FROM evidence_item
        WHERE land_score >= 4 AND (? IS NULL OR type_group = ?) AND (? IS NULL OR source = ?)
          AND (? IS NULL OR list_contains(states, ?)) AND (? IS NULL OR list_contains(themes, ?))
        ORDER BY {order} LIMIT ? OFFSET ?""",
                [type_group, type_group, source, source, state, state, theme, theme, limit, offset])


@router.get("/evidence/facets")
def facets():
    """Counts for filters: document category, source, theme, state, decade."""
    base = "FROM evidence_item WHERE land_score >= 4"
    return {
        "type_group": rows(f"SELECT type_group AS key, count(*) AS n {base} GROUP BY 1 ORDER BY 2 DESC"),
        "source": rows(f"SELECT source AS key, count(*) AS n {base} GROUP BY 1 ORDER BY 2 DESC"),
        "theme": rows(f"SELECT t AS key, count(*) AS n FROM (SELECT unnest(themes) AS t {base}) GROUP BY 1 ORDER BY 2 DESC"),
        "state": rows(f"SELECT s AS key, count(*) AS n FROM (SELECT unnest(states) AS s {base}) GROUP BY 1 ORDER BY 2 DESC"),
        "decade": rows(f"SELECT (year // 10) * 10 AS key, count(*) AS n {base} AND year IS NOT NULL GROUP BY 1 ORDER BY 1"),
    }


@router.get("/evidence/{evidence_id}")
def get_evidence(evidence_id: str):
    r = one("SELECT e.*, d.path IS NOT NULL AS has_file FROM evidence_item e LEFT JOIN doc_file d USING (evidence_id) "
            "WHERE evidence_id = ?", [evidence_id])
    if not r:
        raise HTTPException(404, "evidence item not found")
    r["classification"] = synthesis.classify(f"{r['title']}. {r['abstract']}")
    return r


@router.get("/evidence/{evidence_id}/recommendations")
def recommendations(evidence_id: str, k: int = Query(8, le=30)):
    """Related items, each with the reason it was recommended."""
    return search.recommend(evidence_id, k)


@router.get("/evidence/{evidence_id}/file")
def evidence_file(evidence_id: str, user: dict = Depends(current_user)):
    """The locally stored PDF (open-access papers, World Bank and government documents)."""
    r = one("SELECT path FROM doc_file WHERE evidence_id = ?", [evidence_id])
    if not r or not (DATA / r["path"]).exists():
        raise HTTPException(404, "no local file for this item; use its source link")
    audit(user, "download_document", f"evidence:{evidence_id}")
    return FileResponse(DATA / r["path"], media_type="application/pdf", filename=(DATA / r["path"]).name)


class Ask(BaseModel):
    question: str = Field(min_length=5, max_length=500)
    state: str | None = None
    lever: str | None = Field(None, description="force a Digital Twin lever: agri_conversion | acquisition_reform | dispute_pendency")
    params: dict | None = Field(None, description="policy parameters for the lever (override what the router read from the question)")
    routes: list[str] | None = Field(None, description="force pipelines: any of document, data, policy")


@router.post("/assistant/ask")
def ask(body: Ask, user: dict = Depends(current_user)):
    """Research assistant. Query Router -> RAG / SQL-Analytics / Policy Digital Twin -> evidence verification ->
    evidence matrix -> conflicts, uncertainty and evidence gaps -> cited answer with full traceability.
    Simulated scenarios are stored like Policy Lab runs, so they can be reproduced and exported."""
    if body.routes and not set(body.routes) <= {"document", "data", "policy"}:
        raise HTTPException(400, "routes must be among: document, data, policy")
    out = research_assistant.answer(body.question, body.state, body.lever, body.params, body.routes)
    twin = out.get("twin") or {}
    if twin.get("status") == "ok":
        run = twin["run"]
        rid = execute("INSERT INTO sim_run (user_id, lever, params, seed, result, hash) VALUES (?,?,?,?,?,?)",
                      (user.get("id"), run["lever"], json.dumps(run["params"], default=str), run["seed"],
                       json.dumps(run, default=str), run["hash"]))
        twin["run"]["run_id"] = rid
        if out["traceability"]["policy"]:
            out["traceability"]["policy"][4]["detail"] += f", stored as run #{rid}"
    audit(user, "assistant_ask", "assistant", {"question": body.question,
                                               "routes": [r["route"] for r in out["router"]["routes"]],
                                               "synthesis": out["synthesis"]["mode"]})
    return out


@router.get("/research/topic-trends")
def topic_trends(since: int = 2000):
    """Research output per theme per year, with rising and neglected themes (last 5 years vs the 5 before)."""
    series = rows("""
        SELECT t AS theme, year, count(*) AS n FROM (
            SELECT unnest(themes) AS t, year FROM evidence_item
            WHERE land_score >= 4 AND source = 'openalex' AND year BETWEEN ? AND year(current_date))
        GROUP BY 1, 2 ORDER BY 1, 2""", [since])
    by = {}
    for r in series:
        by.setdefault(r["theme"], {})[r["year"]] = r["n"]
    import datetime as dt
    y = dt.date.today().year
    trend = []
    for th, s in by.items():
        recent = sum(s.get(t, 0) for t in range(y - 5, y))
        prior = sum(s.get(t, 0) for t in range(y - 10, y - 5))
        trend.append({"theme": th, "last_5y": recent, "previous_5y": prior,
                      "growth": round((recent - prior) / prior, 2) if prior else None})
    trend.sort(key=lambda t: -(t["growth"] if t["growth"] is not None else 99))
    return {"series": series, "themes": trend,
            "rising": [t["theme"] for t in trend if (t["growth"] or 0) > 0.5][:6],
            "neglected": [t["theme"] for t in sorted(trend, key=lambda t: t["last_5y"])][:6]}


@router.get("/datasets")
def datasets(job: str | None = None, limit: int = Query(600, le=2000)):
    """Dataset catalogue: every file with its source, licence, size, retrieval time and SHA-256."""
    return rows("SELECT job AS dataset, path, MB, prd_modules AS used_for, license, url, retrieved_at, sha256 "
                "FROM catalog WHERE (? IS NULL OR job = ?) ORDER BY job, path LIMIT ?", [job, job, limit])


@router.get("/datasets/summary")
def dataset_summary():
    return rows("SELECT job AS dataset, count(*) AS files, round(sum(MB)) AS MB, any_value(license) AS license, "
                "max(retrieved_at) AS retrieved_at FROM catalog GROUP BY 1 ORDER BY 3 DESC")
