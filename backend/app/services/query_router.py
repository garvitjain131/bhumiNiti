"""
Query Router: "what does this question require?"

Every research-assistant question passes through here first. The router is rule-based and explains itself:
each route it picks comes with the words in the question that triggered it, so a researcher can see (and
override) why a question went to documents (RAG), structured data (SQL / analytics), the Policy Digital
Twin, or several of them at once.
"""
from __future__ import annotations

import re

from ..core.db import rows

# --------------------------------------------------------------------------- signals per route

DOCUMENT_SIGNALS = [
    r"\bresearch\b", r"\bstud(y|ies)\b", r"\bliterature\b", r"\bevidence\b", r"\bpapers?\b", r"\breports?\b",
    r"\bwhat (do|does) .{0,40}\b(say|find|show)\b", r"\bfound\b", r"\bexperience\b", r"\blessons?\b", r"\bwhy\b",
    r"\bhow (does|do|did)\b", r"\beffect of\b", r"\bimpact of\b", r"\bpolicy documents?\b", r"\blaw\b", r"\bact\b",
]
DATA_SIGNALS = [
    r"\bwhich (districts?|states?)\b", r"\b(highest|lowest|most|least|top|bottom|rank\w*)\b", r"\btrends?\b",
    r"\bover time\b", r"\bsince (19|20)\d\d\b", r"\bcompare\b", r"\bcomparison\b", r"\bhow many\b", r"\bpercent",
    r"\bshare of\b", r"\brate\b", r"\bcorrelat\w*\b", r"\brelationship between\b", r"\bassociat\w* with\b",
    r"\banomal\w*\b", r"\bdata (show|say|indicate)\b", r"\bdistrict[- ]level\b", r"\bcurrently\b", r"\bcurrent (risk|state|level)\b",
    r"\bhigh[- ]risk (districts?|states?)\b",
]
POLICY_SIGNALS = [
    r"\bwhat (could|would|will) happen\b", r"\bwhat if\b", r"\bif (the )?(government|state|we|policy|they)\b",
    r"\bif .{0,60}\b(increase[sd]?|reduced?|restrict\w*|introduc\w*|improv\w*|expand\w*|raise[sd]?|cut)\b",
    r"\b(increas|reduc|restrict|introduc|improv|expand|rais)\w* .{0,40}\b(capacity|coverage|compensation|consent|enforcement|zoning)\b",
    r"\bsimulat\w*\b", r"\bscenarios?\b", r"\bcounterfactual\b", r"\bintervention\b", r"\bpolicy (change|lever|option)s?\b",
    r"\b(would|could) .{0,40}\b(reduce|increase|affect|change|lower|raise)\b", r"\bsensitiv\w*\b", r"\bstress[- ]test\b",
    r"\bproposed\b", r"\bif .{0,40}\bwere\b",
]

# Policy levers the Digital Twin can model (services/sim.py), and the words that point to each.
LEVER_SIGNALS = {
    "dispute_pendency": [r"conflict[- ]resolution", r"dispute[- ]resolution", r"revenue[- ]courts?", r"pendency", r"pending cases",
                         r"disposal", r"rccms", r"ulpin coverage", r"case backlog", r"adjudicat\w*"],
    "acquisition_reform": [r"acquisition", r"acquir\w+ land", r"consent", r"compensation", r"social impact assessment",
                           r"\bsia\b", r"rfctlarr", r"displacement"],
    "agri_conversion": [r"conversion", r"zoning", r"farmland", r"agricultural land", r"cropland (protection|loss)",
                        r"urban expansion", r"built[- ]up", r"land[- ]use change", r"protect\w* cropland"],
}

# District metrics (district_metric) and the words that point to each.
METRIC_SIGNALS = {
    "conflicts": [r"land conflicts?", r"conflicts?", r"disputes?"],
    "conflict_people": [r"people affected", r"affected (people|persons|population)"],
    "climate_risk_index": [r"climate[- ]risk", r"climate (vulnerab\w*|exposure)", r"\brisk index\b"],
    "flood_share": [r"flood\w*"],
    "landslides": [r"landslides?"],
    "rain_cv": [r"rainfall variab\w*", r"drought"],
    "rain_mean": [r"\brainfall\b"],
    "tree_cover": [r"tree cover", r"forest\w*"],
    "crops_change_2017_2025": [r"cropland", r"agricultural land", r"farmland", r"crop (area|land)"],
    "built_growth_2000_2020": [r"urbani[sz]\w*", r"built[- ]up", r"urban expansion"],
    "ntl_growth_2014_2025": [r"night[- ]lights?", r"electrification", r"economic activity"],
    "population_2011": [r"population"],
}
# When a question names none of the metrics above, these stand in for "risk" and "land conflict".
DEFAULT_RISK_METRIC = "conflicts"


def _matches(text: str, patterns: list[str]) -> list[str]:
    hits = []
    for p in patterns:
        m = re.search(p, text, re.I)
        if m:
            hits.append(m.group(0))
    return hits


def _states(text: str) -> list[str]:
    names = [r["name"] for r in rows("SELECT name FROM geo_state")]
    found = []
    for n in names:
        variants = {n, n.replace(" & ", " and "), n.replace("&", "and")}
        if any(re.search(rf"\b{re.escape(v)}\b", text, re.I) for v in variants):
            found.append(n)
    return found


def _percent(text: str) -> float | None:
    m = re.search(r"(\d{1,3})\s*(%|percent|per cent)", text, re.I)
    return int(m.group(1)) / 100 if m else None


_CLAUSE_START = r"(?=(?:what|which|how|where|why|is|are|do|does|could|would|if)\b)"
CLAUSE_SPLIT = re.compile(rf"(?<=[?.;])\s+|,\s*(?:and\s+)?{_CLAUSE_START}|\s+and\s+{_CLAUSE_START}", re.I)
# Phrasing about the evidence itself, removed so retrieval searches for the topic ("land conflict"), not the frame.
FRAMING = [r"^\s*(and\s+)?what (do|does) (the )?(existing |previous |available )?(research|literature|studies|evidence|reports?)"
           r"( \w+)? (say|show|find|found|suggest)( about| on)?", r"^\s*(and\s+)?what (policy )?(interventions|policies|measures) "
           r"(have|has) (previous |existing )?(studies|research) found (useful|effective) (for|in)", r"^\s*according to (the )?research,?"]


def sub_questions(question: str) -> dict[str, str]:
    """Split a multi-part question into clauses and give each pipeline the part that concerns it."""
    clauses = [c.strip(" ,;") for c in CLAUSE_SPLIT.split(question) if c and c.strip(" ,;") and len(c.strip()) > 3]
    parts: dict[str, list[str]] = {"document": [], "data": [], "policy": []}
    for c in clauses:
        if _matches(c, POLICY_SIGNALS):
            parts["policy"].append(c)
        elif _matches(c, DATA_SIGNALS):
            parts["data"].append(c)
        else:
            parts["document"].append(c)
    out = {k: " ".join(v) for k, v in parts.items() if v}
    doc = out.get("document", question)
    for f in FRAMING:
        doc = re.sub(f, "", doc, flags=re.I)
    out["document"] = doc.strip(" ,?") or question
    return out


def route(question: str, lever: str | None = None, forced: list[str] | None = None) -> dict:
    """Decide which pipelines a question needs. Returns the routes, why each was chosen, and the entities found."""
    q = question.strip()
    doc_hits, data_hits, policy_hits = _matches(q, DOCUMENT_SIGNALS), _matches(q, DATA_SIGNALS), _matches(q, POLICY_SIGNALS)
    lever_hits = {k: _matches(q, v) for k, v in LEVER_SIGNALS.items()}
    detected_lever = max(lever_hits, key=lambda k: len(lever_hits[k])) if any(lever_hits.values()) else None
    metrics = [m for m, pats in METRIC_SIGNALS.items() if _matches(q, pats)]
    # "risk" on its own, or conflict questions without a metric, read as documented land conflicts
    if data_hits and not metrics and re.search(r"\brisk\b|\bconflict", q, re.I):
        metrics = [DEFAULT_RISK_METRIC]

    routes: list[dict] = []
    if policy_hits or lever:
        routes.append({"route": "policy", "pipeline": "Policy Digital Twin",
                       "why": "asks what could happen under an intervention" + (f" ({', '.join(policy_hits[:3])})" if policy_hits else "")
                              + ("; lever chosen by the researcher" if lever else "")})
    if data_hits and (metrics or re.search(r"\bdistrict|\bstate", q, re.I)):
        routes.append({"route": "data", "pipeline": "SQL / Analytics",
                       "why": f"asks for structured figures ({', '.join(data_hits[:3])})"})
    # documents are consulted whenever the question asks about evidence, and by default when nothing else fits
    if doc_hits or not routes:
        routes.append({"route": "document", "pipeline": "RAG",
                       "why": f"asks what is known ({', '.join(doc_hits[:3])})" if doc_hits else
                              "no data or policy signal: answered from the evidence repository"})
    if forced:
        kept = [r for r in routes if r["route"] in forced]
        for f in forced:
            if not any(r["route"] == f for r in kept):
                kept.append({"route": f, "pipeline": {"document": "RAG", "data": "SQL / Analytics",
                                                      "policy": "Policy Digital Twin"}[f], "why": "selected by the researcher"})
        routes = kept
    order = {"document": 0, "data": 1, "policy": 2}
    routes.sort(key=lambda r: order[r["route"]])

    return {
        "routes": routes,
        "sub_questions": sub_questions(q),
        "multi_domain": len(routes) > 1,
        "entities": {
            "states": _states(q),
            "metrics": metrics,
            "lever": lever or detected_lever,
            "lever_signals": lever_hits.get(lever or detected_lever or "", []),
            "percent": _percent(q),
        },
        "method": "Rule-based router: phrase patterns for documents, data and policy questions (shown under 'why').",
    }
