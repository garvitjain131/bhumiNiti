"""
Hybrid retrieval: BM25 keyword search (DuckDB FTS) + semantic similarity (LSA vectors), merged by
reciprocal rank fusion, then filtered. Also nearest-neighbour recommendations with stated reasons.
"""
from __future__ import annotations

import json
import re
import threading
from functools import lru_cache

import numpy as np

from ..core.config import AI_DIR
from ..core.db import q, rows

RRF_K = 60
_lock = threading.Lock()


@lru_cache(maxsize=1)
def _index():
    import joblib
    if not (AI_DIR / "vectors.npy").exists():
        return None
    vecs = np.load(AI_DIR / "vectors.npy")
    ids = json.loads((AI_DIR / "ids.json").read_text())
    return vecs, ids, {e: i for i, e in enumerate(ids)}, joblib.load(AI_DIR / "model.joblib")


@lru_cache(maxsize=1)
def vocabulary() -> set[str]:
    idx = _index()
    return set(idx[3].named_steps["tfidfvectorizer"].vocabulary_) if idx else set()


def semantic_available() -> bool:
    return _index() is not None


def embed(texts: list[str]) -> np.ndarray:
    idx = _index()
    with _lock:  # sklearn transform is not guaranteed thread-safe
        return idx[3].transform(texts).astype(np.float32)


def semantic(query: str, k: int = 300) -> list[tuple[str, float]]:
    idx = _index()
    if idx is None:
        return []
    vecs, ids, _, _ = idx
    s = vecs @ embed([query])[0]
    top = np.argpartition(-s, min(k, len(s) - 1))[:k]
    return [(ids[i], float(s[i])) for i in top[np.argsort(-s[top])]]


def keyword(query: str, k: int = 300) -> list[tuple[str, float]]:
    r = rows("""SELECT evidence_id, score FROM (
                  SELECT evidence_id, fts_main_evidence_item.match_bm25(evidence_id, ?) AS score FROM evidence_item)
                WHERE score IS NOT NULL ORDER BY score DESC LIMIT ?""", [query, k])
    return [(x["evidence_id"], x["score"]) for x in r]


FIELDS = """evidence_id, title, type, type_group, source, source_org, year, states, themes, authors, doi, url,
            pdf_url, license, cited_by, land_score, substr(abstract, 1, 500) AS snippet,
            evidence_id IN (SELECT evidence_id FROM doc_file) AS has_file"""


def hybrid(query: str, *, state=None, theme=None, source=None, type_group=None, year_from=None, year_to=None,
           min_relevance=4, limit=20, offset=0) -> dict:
    kw, sem = keyword(query), semantic(query)
    fused: dict[str, dict] = {}
    for rank_, (eid, s) in enumerate(kw):
        fused.setdefault(eid, {"rrf": 0.0})["rrf"] += 1 / (RRF_K + rank_ + 1)
        fused[eid]["keyword_rank"] = rank_ + 1
    for rank_, (eid, s) in enumerate(sem):
        fused.setdefault(eid, {"rrf": 0.0})["rrf"] += 1 / (RRF_K + rank_ + 1)
        fused[eid]["semantic_rank"], fused[eid]["similarity"] = rank_ + 1, round(s, 3)
    if not fused:
        return {"query": query, "total": 0, "results": []}
    cand = list(fused)
    meta = rows(f"""
        SELECT {FIELDS} FROM evidence_item
        WHERE list_contains(?, evidence_id) AND land_score >= ?
          AND (? IS NULL OR list_contains(states, ?)) AND (? IS NULL OR list_contains(themes, ?))
          AND (? IS NULL OR source = ?) AND (? IS NULL OR type_group = ?)
          AND (? IS NULL OR year >= ?) AND (? IS NULL OR year <= ?)""",
                [cand, min_relevance, state, state, theme, theme, source, source, type_group, type_group,
                 year_from, year_from, year_to, year_to])
    for m in meta:
        f = fused[m["evidence_id"]]
        # small prior for documents that are clearly about land governance
        m["score"] = round(f["rrf"] * (1 + 0.04 * min(m["land_score"] or 0, 10)), 5)
        m["match"] = {k: f[k] for k in ("keyword_rank", "semantic_rank", "similarity") if k in f}
    meta.sort(key=lambda m: -m["score"])
    seen_titles, unique = set(), []
    for m in meta:  # the same work often appears twice (preprint + journal version)
        key = re.sub(r"[^a-z0-9]", "", (m["title"] or "").lower())[:90]
        if key and key in seen_titles:
            continue
        seen_titles.add(key)
        unique.append(m)
    meta = unique
    results = meta[offset:offset + limit]
    return {"query": query, "total": len(meta), "mode": "hybrid (BM25 + semantic, reciprocal rank fusion)",
            "results": results, "contributions": _contributions(query)}


def _contributions(query: str) -> list[dict]:
    """Approved researcher submissions not yet in the rebuilt index (live merge)."""
    words = [w for w in query.lower().split() if len(w) > 3][:4]
    if not words:
        return []
    cond = " OR ".join(["lower(title || ' ' || abstract) LIKE ?"] * len(words))
    return q(f"""SELECT 'contribution:' || id AS evidence_id, title, kind AS type, 'Contribution' AS type_group,
                  'contribution' AS source, substr(abstract, 1, 500) AS snippet, states, themes, created_at
                FROM contribution WHERE status = 'approved' AND ({cond}) ORDER BY id DESC LIMIT 5""",
             [f"%{w}%" for w in words])


def _reasons(base: dict, other: dict) -> list[str]:
    r = []
    st = sorted(set(base.get("states") or []) & set(other.get("states") or []))
    th = sorted(set(base.get("themes") or []) & set(other.get("themes") or []))
    if th:
        r.append("same theme: " + ", ".join(t.replace("_", " ") for t in th[:2]))
    if st:
        r.append("same geography: " + ", ".join(st[:2]))
    if base.get("source_org") and base.get("source_org") == other.get("source_org"):
        r.append(f"same publisher: {base['source_org']}")
    return r


def recommend(evidence_id: str, k: int = 8) -> list[dict]:
    idx = _index()
    if idx is None or evidence_id not in idx[2]:
        return []
    vecs, ids, pos, _ = idx
    s = vecs @ vecs[pos[evidence_id]]
    order = [i for i in np.argsort(-s)[:k * 4] if ids[i] != evidence_id]
    base = rows(f"SELECT {FIELDS} FROM evidence_item WHERE evidence_id = ?", [evidence_id])[0]
    cand = rows(f"SELECT {FIELDS} FROM evidence_item WHERE list_contains(?, evidence_id) AND land_score >= 4",
                [[ids[i] for i in order]])
    sim = {ids[i]: float(s[i]) for i in order}
    for c in cand:
        c["similarity"] = round(sim[c["evidence_id"]], 3)
        c["because"] = ["similar content"] + _reasons(base, c)
    cand.sort(key=lambda c: -c["similarity"])
    return cand[:k]


def recommend_for_set(evidence_ids: list[str], k: int = 10) -> list[dict]:
    """Recommendations for a workspace collection: nearest to the collection's centroid."""
    idx = _index()
    if idx is None:
        return []
    vecs, ids, pos, _ = idx
    have = [pos[e] for e in evidence_ids if e in pos]
    if not have:
        return []
    c = vecs[have].mean(axis=0)
    s = vecs @ (c / (np.linalg.norm(c) or 1))
    exclude = set(evidence_ids)
    order = [i for i in np.argsort(-s)[:k * 4] if ids[i] not in exclude]
    cand = rows(f"SELECT {FIELDS} FROM evidence_item WHERE list_contains(?, evidence_id) AND land_score >= 4",
                [[ids[i] for i in order]])
    for x in cand:
        x["similarity"] = round(float(s[pos[x["evidence_id"]]]), 3)
        x["because"] = [f"close to the {len(have)} items in this collection"]
    cand.sort(key=lambda x: -x["similarity"])
    return cand[:k]
