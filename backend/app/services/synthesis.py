"""
Document Query pipeline (RAG) of the research assistant: retrieval, cited sentence extraction, a verifier,
the study matrix (method and direction of each source) and conflict flags.

Fully offline and extractive: every sentence it returns is copied from a retrieved source and cited to it,
and a verifier drops any sentence its cited source does not support. When the evidence is thin it reports
what is missing as an evidence gap instead of guessing. Final wording is done later, in
services/research_assistant.py, from verified claims only.
"""
from __future__ import annotations

import re

import numpy as np

from ..core.db import rows
from . import search

METHODS = [
    ("Difference-in-differences / quasi-experimental", r"difference[- ]in[- ]difference|quasi[- ]experiment|regression discontinuity|natural experiment|propensity score|instrumental variable"),
    ("Randomised trial", r"randomi[sz]ed|\bRCT\b"),
    ("Panel / regression analysis", r"panel data|regression|econometric|fixed effects"),
    ("Remote sensing / GIS", r"remote sensing|satellite|landsat|sentinel|\bGIS\b|land ?use.{0,20}classification|NDVI"),
    ("Household survey", r"household survey|survey of \d|questionnaire|sample of \d|respondents|NSS|NFHS"),
    ("Case study / qualitative", r"case study|qualitative|interviews?|ethnograph|focus group|field ?work"),
    ("Review / synthesis", r"systematic review|literature review|meta-analysis|we review"),
    ("Legal / policy analysis", r"\bAct\b|legislation|legal|judgment|court|policy analysis"),
]
POS = r"\b(improv\w*|increas\w* (in )?(income|investment|yield|credit|security|access)|benefit\w*|positive(ly)? (effect|impact|associat)|effective|succe\w+|enhanc\w*|strengthen\w*|reduc\w* (conflict|dispute|delay|poverty|corruption|litigation))"
NEG = r"\b(declin\w*|decreas\w*|negative(ly)? (effect|impact|associat)|adverse\w*|fail\w*|worsen\w*|loss of|displace\w*|dispossess\w*|ineffective|exacerbat\w*|increas\w* (conflict|dispute|litigation|inequality))"
NULL = r"\b(no (significant|statistically significant) (effect|impact|difference|change)|insignificant|did not (improve|change|affect)|mixed (results|evidence))"


def classify(text: str) -> dict:
    t = text or ""
    method = next((m for m, rx in METHODS if re.search(rx, t, re.I)), "Not stated")
    p, n, z = (len(re.findall(rx, t, re.I)) for rx in (POS, NEG, NULL))
    direction = "no clear effect" if z and z >= max(p, n) else "positive" if p > n else "negative" if n > p else \
        "mixed" if p and n else "descriptive"
    return {"method": method, "direction": direction}


def evidence_matrix(results: list[dict]) -> list[dict]:
    out = []
    ab = {r["evidence_id"]: r["abstract"] for r in rows(
        "SELECT evidence_id, abstract FROM evidence_item WHERE list_contains(?, evidence_id)",
        [[x["evidence_id"] for x in results]])}
    for r in results:
        c = classify(f"{r['title']}. {ab.get(r['evidence_id'], '')}")
        out.append({"evidence_id": r["evidence_id"], "title": r["title"], "year": r.get("year"),
                    "region": ", ".join(r.get("states") or []) or "India / unspecified", "method": c["method"],
                    "direction": c["direction"], "source": r.get("source"), "type": r.get("type_group")})
    return out


def conflicts(matrix: list[dict]) -> list[dict]:
    """Flag disagreement and suggest why (years, regions, methods differ). Heuristic, labelled as such."""
    pos = [m for m in matrix if m["direction"] == "positive"]
    neg = [m for m in matrix if m["direction"] in ("negative", "no clear effect")]
    if not pos or not neg:
        return []
    reasons = []
    yp = [m["year"] for m in pos if m["year"]]
    yn = [m["year"] for m in neg if m["year"]]
    if yp and yn and abs(np.median(yp) - np.median(yn)) >= 5:
        reasons.append(f"different periods (supporting studies ~{int(np.median(yp))}, opposing ~{int(np.median(yn))})")
    if {m["region"] for m in pos}.isdisjoint({m["region"] for m in neg}):
        reasons.append("different regions")
    if {m["method"] for m in pos}.isdisjoint({m["method"] for m in neg}):
        reasons.append("different methods")
    return [{"summary": f"{len(pos)} source(s) report a positive effect; {len(neg)} report a negative or no effect.",
             "supporting": [m["evidence_id"] for m in pos], "opposing": [m["evidence_id"] for m in neg],
             "possible_reasons": reasons or ["definitions or populations may differ; read the sources"],
             "note": "Direction is detected automatically from abstracts (heuristic). The platform does not decide "
                     "which side is right."}]


SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")
STOP = set("the of and to in a for on is are was were be by with that this as at from or an it its their which "
           "we our these those has have had not but can may also than more most other such into between".split())


def _content_words(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{4,}", s.lower()) if w not in STOP}


def verify(sentences: list[dict], sources: dict[str, str]) -> tuple[list[dict], int]:
    """Keep a sentence only if every citation exists and the cited text shares its key terms."""
    kept, dropped = [], 0
    for s in sentences:
        cites = [c for c in s.get("citations", []) if c in sources]
        words = _content_words(s["text"])
        support = max((len(words & _content_words(sources[c])) / max(len(words), 1) for c in cites), default=0)
        if cites and support >= 0.3:
            kept.append({**s, "citations": cites, "support": round(support, 2)})
        else:
            dropped += 1
    return kept, dropped


def _extractive(question: str, docs: list[dict], abstracts: dict[str, str]) -> list[dict]:
    cands = []
    for d in docs:
        for s in SENT.split(abstracts.get(d["evidence_id"]) or "")[:12]:
            if 60 <= len(s) <= 420:
                cands.append((d["evidence_id"], s.strip()))
    if not cands:
        return []
    q = search.embed([question])[0]
    sv = search.embed([c[1] for c in cands])
    scores = sv @ q
    picked, used, texts = [], set(), set()
    for i in np.argsort(-scores):
        eid, s = cands[i]
        norm = re.sub(r"[^a-z0-9]", "", s.lower())
        if eid in used or norm in texts or scores[i] < 0.12:
            continue
        texts.add(norm)
        picked.append({"text": s, "citations": [eid], "relevance": round(float(scores[i]), 3)})
        used.add(eid)
        if len(picked) == 5:
            break
    return picked


QUESTION_STOP = STOP | set("what does do how why when where which who whom whose will would should could effect "
                           "impact affect india indian".split())


def _coverage(question: str, texts: list[str]) -> tuple[float, list[str]]:
    """Share of the question's key terms the repository knows at all (index vocabulary, with s/z and plural
    variants). Terms the corpus has never seen mean the question is outside what the evidence covers."""
    terms = [w for w in re.findall(r"[a-z]{4,}", question.lower()) if w not in QUESTION_STOP]
    if not terms:
        return 1.0, []
    vocab = search.vocabulary()

    def known(t: str) -> bool:
        variants = {t, t.replace("z", "s"), t.replace("s", "z"), t + "s"}
        if t.endswith("s") and len(t) > 4:
            variants.add(t[:-1])
        return any(v in vocab for v in variants)
    missing = [t for t in terms if not known(t)]
    return 1 - len(missing) / len(terms), missing


CAUSAL_METHODS = ("Difference-in-differences / quasi-experimental", "Randomised trial")


def document_evidence(question: str, state: str | None = None, k: int = 8) -> dict:
    """RAG pipeline: retrieve (hybrid BM25 + semantic), rank, de-duplicate, extract cited sentences, verify them
    against their sources, and build the study matrix. Never returns a conclusion that is not in a source."""
    res = search.hybrid(question, state=state, min_relevance=4, limit=k)["results"]
    abstracts = {r["evidence_id"]: f"{r['title']}. {r['abstract']}" for r in rows(
        "SELECT evidence_id, title, abstract FROM evidence_item WHERE list_contains(?, evidence_id)",
        [[r["evidence_id"] for r in res]])} if res else {}
    cov, missing = _coverage(question, list(abstracts.values()))
    gaps = []
    if len(res) < 2 or cov < 0.6 or (missing and cov < 0.9):
        if missing:
            gaps.append({"kind": "insufficient_research", "severity": "high",
                         "what": f"No source in the repository discusses: {', '.join(missing)}.",
                         "why": "The document evidence cannot say anything about these terms, so any answer about them "
                                "would be unsupported.",
                         "research_requirement": f"Commission or ingest studies on {', '.join(missing)}."})
        else:
            gaps.append({"kind": "insufficient_research", "severity": "high",
                         "what": f"Only {len(res)} relevant source(s) were found.",
                         "why": "One or no studies cannot establish a finding or reveal disagreement."})
        return {"insufficient": True, "sources": res, "sentences": [], "checked": 0, "dropped": 0, "matrix": [],
                "conflicts": [], "term_coverage": round(cov, 2), "missing_terms": missing, "abstracts": {}, "gaps": gaps,
                "mode": "none"}
    sentences = _extractive(question, res, abstracts)
    kept, dropped = verify(sentences, abstracts)
    matrix = evidence_matrix(res)
    confl = conflicts(matrix)
    covered = sorted({s for r in res for s in (r.get("states") or [])})
    if not any(m["method"] in CAUSAL_METHODS for m in matrix):
        gaps.append({"kind": "weak_evidence", "severity": "medium",
                     "what": "None of the retrieved studies uses a causal design (quasi-experimental or randomised).",
                     "why": "The literature can describe associations but cannot establish that the policy caused the outcome.",
                     "research_requirement": "A quasi-experimental evaluation (e.g. staggered roll-out difference-in-differences)."})
    if len(covered) <= 3:
        gaps.append({"kind": "missing_geography", "severity": "medium",
                     "what": f"The retrieved studies cover {len(covered)} state(s)" + (f" ({', '.join(covered)})" if covered else "") + ".",
                     "why": "Findings may not transfer to states with different tenure systems and administrative capacity.",
                     "research_requirement": "Studies in under-covered states (see the Gap Radar)."})
    if confl:
        gaps.append({"kind": "conflicting_evidence", "severity": "medium", "what": confl[0]["summary"],
                     "why": "Sources disagree; " + "; ".join(confl[0]["possible_reasons"]) + "."})
    years = [m["year"] for m in matrix if m["year"]]
    if years and max(years) < 2018:
        gaps.append({"kind": "missing_time_period", "severity": "medium",
                     "what": f"The most recent retrieved study is from {max(years)}.",
                     "why": "Recent reforms (ULPIN, SVAMITVA, e-courts) are not reflected in the evidence."})
    return {"insufficient": not kept, "sources": res, "sentences": kept, "checked": len(sentences), "dropped": dropped,
            "matrix": matrix, "conflicts": confl, "term_coverage": round(cov, 2), "missing_terms": missing,
            "abstracts": abstracts, "states_covered": covered, "gaps": gaps, "mode": "extractive (offline)"}
