"""
BHOOMI research assistant: the full evidence-to-answer workflow.

    Question -> Query Router -> RAG / SQL-Analytics / Policy Digital Twin
             -> Evidence Verification -> Evidence Matrix -> Conflict + Uncertainty -> Evidence Gaps
             -> Synthesis -> Cited answer (sections, citations, traceability) -> Research / pilot loop

Never Question -> LLM -> Answer. Every number in the answer comes from a pipeline (a source sentence, a
database query or a simulation run), every claim is in the evidence matrix with its type and status, and the
wording layer (template by default; optional local or hosted LLM) can only rephrase verified claims.
"""
from __future__ import annotations

import re

import numpy as np

from ..core.db import one
from . import data_query, digital_twin, llm, query_router, sim, synthesis

TYPE_PREFIX = {"document": "D", "analytics": "A", "simulation": "S", "assumption": "M", "conflict": "X"}


# --------------------------------------------------------------------------- evidence verification

def _verify(doc: dict | None, data: dict | None, twin: dict | None) -> list[dict]:
    checks = []
    if doc is not None:
        checks.append({"check": "Source support", "status": "pass" if doc["sentences"] else "fail",
                       "detail": f"{doc['checked']} extracted sentences checked against their cited source; "
                                 f"{doc['dropped']} dropped as unsupported; {len(doc['sentences'])} kept."})
    if data is not None:
        ok, tested = 0, 0
        for a in data["analyses"]:
            if a["kind"] == "ranking" and a["rows"]:
                tested += 1
                lead = a["rows"][0]
                again = one("SELECT round(value, 3) AS v FROM district_metric WHERE metric = ? AND district_lgd = ?",
                            [a["indicator"], lead["district_lgd"]])
                ok += bool(again and again["v"] == lead["value"])
        checks.append({"check": "Data support", "status": "pass" if tested and ok == tested else "warn" if not tested else "fail",
                       "detail": f"{ok} of {tested} headline figures re-read from the source table and matched." if tested
                                 else "No ranked figure to re-check."})
    if twin is not None and twin.get("status") == "ok":
        r = twin["run"]
        again = sim.run(r["lever"], r["params"], r["seed"], r["draws"])
        key = digital_twin.IMPACT[r["lever"]][0]
        same = again["impact"][key] == r["impact"][key]
        checks.append({"check": "Simulation support", "status": "pass" if same else "fail",
                       "detail": f"Scenario re-run with the same inputs and seed ({r['draws']:,} draws) "
                                 + ("reproduced the stated distribution exactly." if same else "gave a different result.")})
        weak = [s for s in twin["sensitivity"] if s["grade"] in ("C", "user")]
        checks.append({"check": "Assumption validity", "status": "warn" if weak else "pass",
                       "detail": f"{len(weak)} of {len(twin['sensitivity'])} model coefficients are expert assumptions "
                                 f"(grade C) or user overrides; the simulated result depends on them explicitly."})
    conflicts = (doc or {}).get("conflicts") or []
    weak_corr = [a for a in (data or {}).get("analyses", []) if a["kind"] == "correlation" and a["result"]["p_value"] > 0.05]
    checks.append({"check": "Contradictions", "status": "warn" if conflicts or weak_corr else "pass",
                   "detail": (conflicts[0]["summary"] if conflicts else "No disagreement detected among the retrieved sources.")
                             + (" A tested correlation is not statistically significant." if weak_corr else "")})
    n_src = len((doc or {}).get("sources") or [])
    n_an = len((data or {}).get("analyses") or [])
    suff = (doc is None or (n_src >= 3 and not doc["insufficient"])) and (data is None or n_an > 0) and (twin is None or twin.get("status") == "ok")
    checks.append({"check": "Evidence sufficiency", "status": "pass" if suff else "warn",
                   "detail": f"{n_src} documents, {n_an} analyses, " + ("1 simulation." if twin and twin.get("status") == "ok" else "no simulation.")})
    causal = [m for m in (doc or {}).get("matrix", []) if m["method"] in synthesis.CAUSAL_METHODS]
    parts = []
    if doc is not None:
        parts.append(f"{len(causal)} of {len(doc.get('matrix', []))} studies use a causal design; the rest show association or description")
    if data is not None:
        parts.append("data analyses are descriptive or correlational, never causal")
    if twin is not None and twin.get("status") == "ok":
        parts.append("simulated effects are conditional on assumed effect sizes, not observed causation")
    if doc is not None and not doc.get("matrix"):
        parts[0] = "no study was retained, so causality cannot be assessed from documents"
    checks.append({"check": "Causality", "status": "warn" if not causal else "pass", "detail": "; ".join(parts) + "."})
    return checks


# --------------------------------------------------------------------------- evidence matrix

def _matrix(doc: dict | None, data: dict | None, twin: dict | None) -> list[dict]:
    claims, counter = [], {}

    def add(kind: str, claim: str, evidence: list[dict], support: str, status: str, label: str, numbers=()):
        counter[kind] = counter.get(kind, 0) + 1
        claims.append({"id": f"{TYPE_PREFIX[kind]}{counter[kind]}", "claim": claim, "evidence": evidence, "type": kind,
                       "support": support, "status": status, "label": label, "numbers": [float(n) for n in numbers if n is not None]})

    if doc:
        titles = {r["evidence_id"]: r["title"] for r in doc["sources"]}
        for s in doc["sentences"]:
            add("document", s["text"], [{"kind": "source", "ref": c, "title": titles.get(c, c)} for c in s["citations"]],
                f"Supporting passage; {int(s['support'] * 100)}% of its key terms appear in the cited source", "verified",
                "OBSERVED", re.findall(r"\d+(?:\.\d+)?", s["text"])[:6])
        for c in doc.get("conflicts", []):
            add("conflict", c["summary"] + " Possible reasons: " + "; ".join(c["possible_reasons"]) + ".",
                [{"kind": "source", "ref": e, "title": titles.get(e, e)} for e in c["supporting"] + c["opposing"]],
                "Directions tagged automatically from abstracts (heuristic)", "conflict", "DESCRIPTIVE")
    if data:
        for a in data["analyses"]:
            for c in a["claims"]:
                add("analytics", c["text"], [{"kind": "dataset", "ref": a["indicator"], "title": a["dataset"]}],
                    f"{a['method']} · {a['scope']} · {a['period']}",
                    "correlational" if a["label"] == "CORRELATIONAL" else "verified", a["label"], c["numbers"])
    if twin and twin.get("status") == "ok":
        for c in twin["claims"]:
            kind = "analytics" if c["type"] == "analytics" else c["type"]
            add(kind, c["text"], [{"kind": "model", "ref": twin["model_id"], "title": twin["lever_name"]}], c["support"],
                "verified" if kind == "analytics" else "assumption" if kind == "assumption" else "simulated",
                c["label"], c["numbers"])
    return claims


def _uncertainty(doc, data, twin) -> list[str]:
    out = []
    if twin and twin.get("status") == "ok":
        s, st = twin["simulation"], twin["stress_test"]
        out.append(f"Simulated {s['impact_name']}: P10 {s['impact']['p10']:,.1f} to P90 {s['impact']['p90']:,.1f} {s['impact_unit']} "
                   f"around a median of {s['impact']['p50']:,.1f}; stress tests show the result is {st['stability']}.")
    for a in (data or {}).get("analyses", []):
        if a["kind"] == "trend" and "slope_ci95" in a["result"]:
            lo, hi = a["result"]["slope_ci95"]
            out.append(f"{a['indicator_name']} trend: 95% confidence interval {lo:+.3g} to {hi:+.3g} {a['unit']} per year.")
        if a["kind"] == "correlation":
            out.append(f"Correlation {a['title']}: p = {a['result']['p_value']:.3g} (n = {a['result']['n']}).")
    if doc and doc["dropped"]:
        out.append(f"{doc['dropped']} of {doc['checked']} candidate source sentences were rejected by the verifier.")
    return out


# --------------------------------------------------------------------------- synthesis (template; optional LLM)

def _cites(claims: list[dict], kind: str) -> list[dict]:
    return [{"text": c["claim"], "cites": [c["id"]], "type": c["type"], "label": c["label"]} for c in claims if c["type"] == kind]


def _verify_llm(sentences: list[dict], claims: list[dict]) -> tuple[list[dict], int]:
    """Keep an LLM sentence only if it cites existing claims and every number it states appears in those claims."""
    by_id = {c["id"]: c for c in claims}
    kept, dropped = [], 0
    for s in sentences:
        cites = [c for c in s.get("citations", []) if c in by_id]
        allowed = [n for c in cites for n in by_id[c]["numbers"]]
        nums = [float(x.replace(",", "")) for x in re.findall(r"\d[\d,]*(?:\.\d+)?", s.get("text", ""))]
        ok_nums = all(any(abs(n - a) <= max(0.051, abs(a) * 0.005) for a in allowed) or n in (10, 50, 90) or 1900 <= n <= 2100
                      for n in nums)
        if cites and ok_nums:
            kept.append({"text": s["text"], "cites": cites, "type": "overview", "label": "SYNTHESIS"})
        else:
            dropped += 1
    return kept, dropped


def _compose(question: str, doc, data, twin, claims, uncertainty, gaps) -> tuple[list[dict], dict]:
    sections = []
    overview, synth = [], {"mode": "template (offline)", "dropped": 0}
    if llm.enabled() and claims:
        try:
            overview, dropped = _verify_llm(llm.overview(question, claims), claims)
            synth = {"mode": f"LLM wording ({llm.model_name()}) checked against the evidence matrix", "dropped": dropped}
        except llm.LLMUnavailable as e:
            synth = {"mode": "template (offline)", "dropped": 0, "llm_error": str(e)}
    if not overview:
        firsts = [next((c for c in claims if c["type"] == k), None) for k in ("document", "analytics", "simulation")]
        overview = [{"text": c["claim"], "cites": [c["id"]], "type": c["type"], "label": c["label"]} for c in firsts if c]
    if overview:
        sections.append({"key": "overview", "title": "Summary", "sentences": overview})

    doc_s = _cites(claims, "document")
    if doc is not None:
        sections.append({"key": "key_findings", "title": "Key findings from research", "sentences": doc_s or [
            {"text": "The repository does not contain enough verified evidence to state a finding for this question.",
             "cites": [], "type": "gap", "label": "GAP"}]})
    if data is not None:
        sections.append({"key": "data_findings", "title": "What the data shows", "sentences": _cites(claims, "analytics") or [
            {"text": "No platform indicator measures the quantities in this question.", "cites": [], "type": "gap", "label": "GAP"}]})
    if twin is not None:
        if twin.get("status") == "ok":
            p = twin["policy_lever"]
            sections.append({"key": "policy_scenario", "title": "Scenario tested", "sentences": [
                {"text": f"Lever simulated: {twin['lever_name']} ({twin['current_state']['scope']}). "
                         + ("Parameters taken from the question: " + "; ".join(p["mapped_from_question"]) + "." if p["mapped_from_question"]
                            else "Default parameters were used; adjust them to test other settings."),
                 "cites": [], "type": "simulation", "label": "SIMULATED"}]})
            sections.append({"key": "twin_result", "title": "Scenario result", "sentences": _cites(claims, "simulation")})
            sections.append({"key": "sensitivity", "title": "What matters most", "sentences": _cites(claims, "assumption") + [
                {"text": f"{s['parameter']}: {s['level']} sensitivity (evidence grade {s['grade']}).", "cites": [], "type": "assumption",
                 "label": "SIMULATED"} for s in twin["sensitivity"][1:4]]})
        else:
            sections.append({"key": "policy_scenario", "title": "Scenario tested", "sentences": [
                {"text": twin.get("message", "No scenario was simulated."), "cites": [], "type": "gap", "label": "GAP"}]})
    if uncertainty:
        sections.append({"key": "uncertainty", "title": "How certain this is",
                         "sentences": [{"text": u, "cites": [], "type": "uncertainty", "label": "UNCERTAINTY"} for u in uncertainty]})
    sections.append({"key": "conflicts", "title": "Where sources disagree", "sentences": _cites(claims, "conflict") or [
        {"text": "No disagreement was detected among the evidence used.", "cites": [], "type": "conflict", "label": "DESCRIPTIVE"}]})
    sections.append({"key": "evidence_gaps", "title": "What is still unknown",
                     "sentences": [{"text": f"{g['what']} {g['why']}", "cites": [], "type": "gap", "label": "GAP"} for g in gaps] or [
                         {"text": "No major evidence gap was detected for this question.", "cites": [], "type": "gap", "label": "GAP"}]})
    order = ["overview", "key_findings", "data_findings", "policy_scenario", "twin_result", "uncertainty", "sensitivity",
             "conflicts", "evidence_gaps"]
    sections.sort(key=lambda s: order.index(s["key"]))
    return sections, synth


def _gaps(doc, data, twin) -> list[dict]:
    seen, out = set(), []
    for g in (doc or {}).get("gaps", []) + (data or {}).get("gaps", []) + (twin or {}).get("gaps", []):
        key = g["what"]
        if key in seen:
            continue
        seen.add(key)
        out.append({"severity": "medium", "research_requirement": None, **g})
    rank = {"high": 0, "medium": 1, "low": 2}
    out.sort(key=lambda g: rank.get(g["severity"], 1))
    return out


# --------------------------------------------------------------------------- entry point

def answer(question: str, state: str | None = None, lever: str | None = None, params: dict | None = None,
           routes: list[str] | None = None) -> dict:
    routing = query_router.route(question, lever, routes)
    if state:
        routing["entities"]["states"] = [state] + [s for s in routing["entities"]["states"] if s.upper() != state.upper()]
    chosen = {r["route"] for r in routing["routes"]}
    ents = routing["entities"]

    doc_question = routing["sub_questions"]["document"] if routing["multi_domain"] else question
    doc = synthesis.document_evidence(doc_question, state) if "document" in chosen else None
    if doc is not None:
        doc["query"] = doc_question
    data = data_query.run(question, ents) if "data" in chosen else None
    twin = digital_twin.run(question, ents, params, (data or {}).get("high_risk_districts")) if "policy" in chosen else None

    checks = _verify(doc, data, twin)
    claims = _matrix(doc, data, twin)
    conflicts = (doc or {}).get("conflicts", [])
    uncertainty = _uncertainty(doc, data, twin)
    gaps = _gaps(doc, data, twin)
    sections, synth = _compose(question, doc, data, twin, claims, uncertainty, gaps)
    insufficient = not claims

    cited = {e["ref"] for c in claims for e in c["evidence"]}
    sources = [{"ref": r["evidence_id"], "kind": "document", "title": r["title"], "year": r.get("year"),
                "type_group": r.get("type_group"), "used": r["evidence_id"] in cited}
               for r in (doc or {}).get("sources", [])]
    sources += [{"ref": a["indicator"], "kind": "dataset", "title": a["dataset"], "detail": f"{a['indicator_name']} · {a['period']}"}
                for a in (data or {}).get("analyses", [])]
    if twin and twin.get("status") == "ok":
        sources.append({"ref": twin["model_id"], "kind": "model", "title": f"Policy Digital Twin: {twin['lever_name']}",
                        "detail": f"seed {twin['simulation']['seed']}, {twin['simulation']['draws']:,} draws, hash {twin['simulation']['hash'][:12]}"})

    trace = [{"step": "Query router", "detail": ", ".join(r["pipeline"] for r in routing["routes"])}]
    if doc is not None:
        trace.append({"step": "RAG", "detail": f"{len(doc['sources'])} sources retrieved (BM25 + semantic, reciprocal rank fusion)"})
    if data is not None:
        trace.append({"step": "SQL / Analytics", "detail": f"{len(data['analyses'])} analyses: " + ", ".join(a["kind"] for a in data["analyses"])})
    if twin is not None:
        trace.append({"step": "Policy Digital Twin", "detail": twin.get("lever_name", twin.get("message", ""))})
    trace += [{"step": "Evidence verification", "detail": f"{sum(c['status'] == 'pass' for c in checks)} of {len(checks)} checks passed"},
              {"step": "Evidence matrix", "detail": f"{len(claims)} claims"},
              {"step": "Conflict + uncertainty", "detail": f"{len(conflicts)} conflicts, {len(uncertainty)} uncertainty notes"},
              {"step": "Evidence gaps", "detail": f"{len(gaps)} gaps"},
              {"step": "Synthesis", "detail": synth["mode"]}]
    policy_trace = None
    if twin and twin.get("status") == "ok":
        s = twin["simulation"]
        policy_trace = [
            {"step": "Policy result", "detail": f"median {s['impact']['p50']:,.1f} {s['impact_unit']} ({s['impact_name']})"},
            {"step": "Scenario", "detail": twin["lever_name"]},
            {"step": "Policy parameters", "detail": ", ".join(f"{k}={v}" for k, v in twin["policy_lever"]["parameters"].items()
                                                             if v not in (None, [], {}) and k != "coef_overrides")},
            {"step": "Baseline state", "detail": "; ".join(twin["evidence_behind"]["baseline_datasets"])},
            {"step": "Simulation", "detail": f"{s['draws']:,} Monte Carlo draws, seed {s['seed']}, hash {s['hash'][:12]}"},
            {"step": "Outcome distribution", "detail": f"P10 {s['impact']['p10']:,.1f} · P50 {s['impact']['p50']:,.1f} · P90 {s['impact']['p90']:,.1f}"},
            {"step": "Sensitivity", "detail": ", ".join(f"{x['parameter']} ({x['level']})" for x in twin["sensitivity"][:3])},
            {"step": "Supporting evidence", "detail": f"{sum(len(r['literature']) for r in twin['evidence_behind']['relationships'])} related "
                                                      f"studies; coefficient grades " + ", ".join(sorted({x['grade'] for x in twin['sensitivity']}))},
        ]

    doc_out = None
    if doc is not None:
        doc_out = {k: v for k, v in doc.items() if k not in ("abstracts", "gaps")}
    data_out = None if data is None else {"analyses": data["analyses"], "high_risk_districts": data["high_risk_districts"]}
    twin_out = None if twin is None else {k: v for k, v in twin.items() if k not in ("claims", "gaps")}

    return _json_safe({
        "question": question, "router": routing,
        "document": doc_out, "data": data_out, "twin": twin_out,
        "verification": checks, "evidence_matrix": claims, "conflicts": conflicts, "uncertainty": uncertainty,
        "evidence_gaps": gaps, "answer_sections": sections, "synthesis": synth, "sources": sources,
        "traceability": {"answer": trace, "policy": policy_trace},
        "insufficient_evidence": insufficient,
        "answer": None if not insufficient else "Insufficient evidence for a reliable conclusion. " + " ".join(
            f"{g['what']} {g['why']}" for g in gaps[:3]),
        # document-pipeline fields kept at the top level for existing API clients
        "mode": (doc or {}).get("mode", "none"),
        "sentences": (doc or {}).get("sentences", []),
        "matrix": (doc or {}).get("matrix", []),
        "verifier": {"checked": (doc or {}).get("checked", 0), "dropped_unsupported": (doc or {}).get("dropped", 0)},
        "evidence_labels": sorted({c["label"] for c in claims}),
    })


def _json_safe(o):
    if isinstance(o, dict):
        return {k: _json_safe(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_json_safe(v) for v in o]
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    return o
