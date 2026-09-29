"""
Policy Digital Twin for the research assistant.

    Current state (baseline built from platform data)  +  policy lever  +  parameters
        -> scenario simulation (Monte Carlo, services/sim.py)
        -> impact distribution (P10 / P50 / P90), baseline vs scenario
        -> stress test (conservative / central / high-impact coefficient ranges)
        -> sensitivity (what matters most) -> evidence behind each assumption -> evidence gaps

The twin is a data-informed representation of the available system state, not a picture of reality: every
baseline figure names its dataset, every relationship names its evidence grade, and every outcome is labelled
SIMULATED and phrased as conditional on the stated assumptions.
"""
from __future__ import annotations

import re

import numpy as np

from ..core.db import one, rows
from . import search, sim

# What each lever's headline impact measures (the first key of sim output["impact"]).
IMPACT = {
    "agri_conversion": ("cropland_saved_km2", "cropland loss avoided", "km2"),
    "acquisition_reform": ("conflicts_avoided", "documented land conflicts avoided", "conflicts"),
    "dispute_pendency": ("pendency_reduction_pct", "reduction in pending revenue-court cases", "%"),
}
OUTCOME = {  # baseline / scenario series compared in the "baseline vs scenario" table
    "agri_conversion": ("cumulative_cropland_lost", "Cumulative cropland lost", "km2"),
    "acquisition_reform": ("cumulative_conflicts", "Cumulative documented land conflicts", "conflicts"),
    "dispute_pendency": ("pending_cases", "Pending revenue-court cases", "cases"),
}
TOPIC = {  # literature search context for each lever's relationships
    "agri_conversion": "agricultural land conversion zoning India",
    "acquisition_reform": "land acquisition conflict compensation consent India",
    "dispute_pendency": "land dispute revenue court records digitisation India",
}


def _final(v):
    return v[-1] if isinstance(v, list) else v


def _num(v, digits=3):
    return None if v is None else float(np.round(v, digits))


# --------------------------------------------------------------------------- current state

def current_state(lever: str, p: dict) -> dict:
    """Baseline indicators relevant to this lever, each with dataset, period and evidence label."""
    ind, notes, assumed = [], [], []
    if lever == "agri_conversion":
        where, params = sim._geo_filter(p)
        b = one(f"""
            SELECT count(*) AS districts, sum(crop_km2) AS crop_km2, sum(area) AS area,
                   sum(b20) AS built2020, sum(b10) AS built2010, median(dcrop) AS crops_change_pp
            FROM (SELECT g.district_lgd, any_value(g.area_km2) AS area,
                         max(i.value) FILTER (WHERE i.indicator = 'dw_crops' AND i.year = 2025) * any_value(g.area_km2) AS crop_km2,
                         max(i.value) FILTER (WHERE i.indicator = 'ghsl_built_km2' AND i.year = 2020) AS b20,
                         max(i.value) FILTER (WHERE i.indicator = 'ghsl_built_km2' AND i.year = 2010) AS b10,
                         (SELECT value FROM district_metric m WHERE m.district_lgd = g.district_lgd
                          AND m.metric = 'crops_change_2017_2025') AS dcrop
                  FROM indicator i JOIN geo_district g USING (district_lgd) WHERE {where} GROUP BY 1)""", params) or {}
        growth = (b["built2020"] / b["built2010"]) ** 0.1 - 1 if b.get("built2010") else None
        ind += [
            {"name": "Districts in scope", "value": b.get("districts"), "unit": "districts", "dataset": "Survey of India / LGD", "period": "current", "label": "OBSERVED"},
            {"name": "Cropland area", "value": _num(b.get("crop_km2"), 0), "unit": "km2", "dataset": "Dynamic World", "period": "2025", "label": "ESTIMATED"},
            {"name": "Cropland share of area", "value": _num(100 * b["crop_km2"] / b["area"], 1) if b.get("area") else None, "unit": "%", "dataset": "Dynamic World", "period": "2025", "label": "ESTIMATED"},
            {"name": "Built-up area", "value": _num(b.get("built2020"), 0), "unit": "km2", "dataset": "GHSL", "period": "2020", "label": "ESTIMATED"},
            {"name": "Built-up growth", "value": _num(100 * growth, 2) if growth is not None else None, "unit": "% per year", "dataset": "GHSL", "period": "2010-2020", "label": "ESTIMATED"},
            {"name": "Median district cropland-share change", "value": _num(b.get("crops_change_pp"), 2), "unit": "percentage points", "dataset": "Dynamic World", "period": "2017-2025", "label": "ESTIMATED"},
        ]
        notes.append("Land cover is classified from satellite imagery (Dynamic World 10 m, GHSL); classification error is not modelled.")
        scope = "selected districts" if p.get("districts") else (p.get("state") or "India").title()
    elif lever == "acquisition_reform":
        state = p.get("state")
        b = one(f"""SELECT count(*) AS total, count(*) FILTER (WHERE year_started BETWEEN 2015 AND 2024) AS recent,
                           median(people_affected) AS people_median, sum(people_affected) AS people_total,
                           (SELECT count(*) FROM land_conflict WHERE (? IS NULL OR soi_state = upper(?))) AS all_conflicts
                    FROM land_conflict WHERE sector IN {sim.ACQ_SECTORS} AND (? IS NULL OR soi_state = upper(?))""",
                [state, state, state, state]) or {}
        ind += [
            {"name": "Documented acquisition-related conflicts", "value": b.get("total"), "unit": "cases", "dataset": "Land Conflict Watch", "period": "all years", "label": "OBSERVED"},
            {"name": "New cases per year (2015-2024 average)", "value": _num((b.get("recent") or 0) / 10, 1), "unit": "cases/yr", "dataset": "Land Conflict Watch", "period": "2015-2024", "label": "OBSERVED"},
            {"name": "Share of all documented land conflicts", "value": _num(100 * b["total"] / b["all_conflicts"], 1) if b.get("all_conflicts") else None, "unit": "%", "dataset": "Land Conflict Watch", "period": "all years", "label": "OBSERVED"},
            {"name": "Median people affected per conflict", "value": _num(b.get("people_median"), 0), "unit": "persons", "dataset": "Land Conflict Watch", "period": "all years", "label": "OBSERVED"},
        ]
        notes.append("Conflict counts are cases documented by Land Conflict Watch, not all disputes; under-reporting is modelled as +/-20%.")
        scope = (state or "India").title()
    else:  # dispute_pendency
        state = p.get("state")
        d = one("""SELECT sum(ror_computerised) / nullif(sum(ror_total), 0) * 100 AS ror_pct,
                          sum(ulpin_assigned) / nullif(sum(land_parcels), 0) * 100 AS ulpin_pct,
                          avg(georef_pct) AS georef_pct, avg(maps_digitised_pct) AS maps_pct
                   FROM dilrmp_state WHERE (? IS NULL OR soi_state_name = upper(?))""", [state, state]) or {}
        c = one("SELECT count(*) AS n FROM land_conflict WHERE (? IS NULL OR soi_state = upper(?))", [state, state]) or {}
        ind += [
            {"name": "Records of Rights computerised", "value": _num(d.get("ror_pct"), 1), "unit": "%", "dataset": "DILRMP-MIS", "period": "latest", "label": "OBSERVED"},
            {"name": "Parcels with a ULPIN", "value": _num(d.get("ulpin_pct"), 1), "unit": "%", "dataset": "DILRMP-MIS", "period": "latest", "label": "OBSERVED"},
            {"name": "Parcels geo-referenced (state average)", "value": _num(d.get("georef_pct"), 1), "unit": "%", "dataset": "DILRMP-MIS", "period": "latest", "label": "OBSERVED"},
            {"name": "Documented land conflicts", "value": c.get("n"), "unit": "cases", "dataset": "Land Conflict Watch", "period": "all years", "label": "OBSERVED"},
            {"name": "New revenue-court filings per year", "value": p.get("filings_per_year"), "unit": "cases/yr", "dataset": "Researcher input (no national RCCMS data on the platform)", "period": "assumed", "label": "ASSUMPTION"},
            {"name": "Average years to resolve a case", "value": p.get("years_to_resolve"), "unit": "years", "dataset": "Researcher input", "period": "assumed", "label": "ASSUMPTION"},
        ]
        assumed += ["new revenue-court filings per year", "average years to resolve a case"]
        notes.append("Revenue-court caseload is not in the platform: filings and disposal time are inputs, so the baseline "
                     "is illustrative until a state's RCCMS figures are loaded.")
        scope = (state or "India").title()
    return {"scope": scope, "indicators": ind, "data_quality": notes, "assumed_inputs": assumed,
            "statement": "A data-informed representation of the available system state, not a complete picture of reality; "
                         "it is only as good as the datasets listed."}


# --------------------------------------------------------------------------- parameters from the question

def parameters(lever: str, question: str, entities: dict, overrides: dict | None, high_risk: list[int]) -> tuple[dict, list[str]]:
    """Map what the question says onto lever parameters; everything mapped is listed so the researcher can check it."""
    spec = sim.LEVERS[lever]
    p, mapped = dict(spec["params"]), []
    states = entities.get("states") or []
    pct = entities.get("percent")
    if states and "state" in p:
        p["state"] = states[0]
        mapped.append(f"state = {states[0].title()} (named in the question)")
    if lever == "agri_conversion":
        if pct is not None:
            p["strength"] = pct
            mapped.append(f"strength = {pct:.0%} (from the question)")
        if high_risk and re.search(r"high[- ]risk|these districts|those districts|identified|most affected|targeted?", question, re.I):
            p["districts"] = high_risk
            p["state"] = None
            mapped.append(f"districts = {len(high_risk)} highest-ranked districts from the data query (geographic targeting)")
    elif lever == "acquisition_reform":
        if pct is not None and re.search(r"consent", question, re.I):
            p["consent_threshold"] = int(round(pct * 100))
            mapped.append(f"consent_threshold = {p['consent_threshold']}% (from the question)")
        m = re.search(r"(\d(?:\.\d)?)\s*(x|times)", question, re.I)
        if m and re.search(r"compensation", question, re.I):
            p["compensation_multiplier"] = float(m.group(1))
            mapped.append(f"compensation_multiplier = {m.group(1)}x (from the question)")
    elif lever == "dispute_pendency":
        if pct is not None:
            p["rccms_coverage"] = min(pct, 1.0)
            mapped.append(f"rccms_coverage = {min(pct, 1.0):.0%} (from the question)")
    for k, v in (overrides or {}).items():
        if k in p and v is not None:
            p[k] = v
            mapped.append(f"{k} = {v} (set by the researcher)")
    return p, mapped


# --------------------------------------------------------------------------- stress test and sensitivity

def _stress(lever: str, p: dict, central: dict) -> dict:
    """Re-run with every coefficient restricted to its least favourable third (conservative) and its most
    favourable third (high-impact); 'favourable' is read from the one-at-a-time tornado."""
    key, _, unit = IMPACT[lever]
    by_name = {c["name"]: c for c in central["coefficients"]}
    cons, high = {}, {}
    for t in central["tornado"]:
        c = by_name.get(t["parameter"])
        if not c or c["high"] <= c["low"]:
            continue
        w = (c["high"] - c["low"]) / 3
        low_third, high_third = [c["low"], c["low"] + w], [c["high"] - w, c["high"]]
        low_is_weaker = t["low"] <= t["high"]
        cons[c["key"]] = low_third if low_is_weaker else high_third
        high[c["key"]] = high_third if low_is_weaker else low_third
    out = []
    for label, ov in (("Conservative", cons), ("Central (full ranges)", None), ("High-impact", high)):
        r = central if ov is None else sim.run(lever, {**p, "coef_overrides": {**(p.get("coef_overrides") or {}), **ov}},
                                               central["seed"], central["draws"])
        imp = r["impact"][key]
        out.append({"scenario": label, "p10": _final(imp["p10"]), "p50": _final(imp["p50"]), "p90": _final(imp["p90"]), "unit": unit})
    c50 = out[1]["p50"]
    spread = (out[2]["p50"] - out[0]["p50"]) / abs(c50) if c50 else None
    stability = ("unknown" if spread is None else "highly sensitive" if spread > 1.0 else
                 "moderately sensitive" if spread > 0.5 else "relatively stable")
    return {"scenarios": out, "relative_spread": None if spread is None else round(spread, 2), "stability": stability,
            "method": "Each coefficient restricted to the third of its range that gives the smallest (conservative) or "
                      "largest (high-impact) effect, same seed and draws as the central run."}


def _sensitivity(run: dict) -> list[dict]:
    by_name = {c["name"]: c for c in run["coefficients"]}
    top = max((t["swing"] for t in run["tornado"]), default=0) or 1
    out = []
    for t in run["tornado"]:
        share = t["swing"] / top
        c = by_name.get(t["parameter"], {})
        out.append({"parameter": t["parameter"], "key": c.get("key"), "swing": t["swing"], "low": t["low"], "high": t["high"],
                    "level": "high" if share >= 0.5 else "medium" if share >= 0.2 else "low",
                    "grade": c.get("grade"), "source": c.get("source"), "range": [c.get("low"), c.get("high")], "unit": c.get("unit")})
    return out


def _relationship_evidence(lever: str, sens: list[dict]) -> list[dict]:
    """For the assumptions that matter most, look for literature in the repository (RAG) and say whether any exists."""
    out = []
    for s in sens:
        if s["level"] == "low":
            continue
        res = search.hybrid(f"{s['parameter']} {TOPIC[lever]}", min_relevance=4, limit=3)["results"]
        out.append({"parameter": s["parameter"], "grade": s["grade"],
                    "literature": [{"evidence_id": r["evidence_id"], "title": r["title"], "year": r.get("year")} for r in res],
                    "note": "Related studies found; none is used as a calibrated effect size." if res else
                            "No study in the repository addresses this relationship."})
    return out


# --------------------------------------------------------------------------- the twin

def run(question: str, entities: dict, overrides: dict | None = None, high_risk: list[int] | None = None) -> dict:
    lever = entities.get("lever")
    if not lever or lever not in sim.LEVERS:
        return {"status": "no_lever",
                "message": "The question asks about an intervention the Digital Twin does not model yet.",
                "available_levers": [{"id": k, "name": v["name"], "question": v["question"]} for k, v in sim.LEVERS.items()],
                "claims": [], "gaps": [{"kind": "unvalidated_relationship", "severity": "high",
                                        "what": "No modelled policy lever matches this intervention.",
                                        "why": "Without a model linking the intervention to outcomes, no scenario can be simulated; "
                                               "a lever needs a baseline dataset and graded effect sizes.",
                                        "research_requirement": "Estimate the effect of this intervention on land outcomes "
                                                                "(ideally quasi-experimental) so it can be added as a lever."}]}
    spec = sim.LEVERS[lever]
    p, mapped = parameters(lever, question, entities, overrides, high_risk or [])
    try:
        central = sim.run(lever, p)
    except ValueError as e:
        return {"status": "error", "message": str(e), "claims": [], "gaps": [
            {"kind": "missing_dataset", "severity": "high", "what": f"No baseline data for this geography: {e}.",
             "why": "The twin cannot establish a current state, so no scenario is simulated."}]}
    state = current_state(lever, central["params"])
    key, impact_name, impact_unit = IMPACT[lever]
    out_key, out_name, out_unit = OUTCOME[lever]
    imp = central["impact"][key]
    last_year = central["years"][-1]
    b, s = central["baseline"][out_key], central["scenario"][out_key]
    comparison = [{
        "indicator": f"{out_name} by {last_year}", "unit": out_unit,
        "baseline_p50": _final(b["p50"]), "scenario_p50": _final(s["p50"]),
        "absolute_change": _final(s["p50"]) - _final(b["p50"]),
        "relative_change_pct": (_final(s["p50"]) / _final(b["p50"]) - 1) * 100 if _final(b["p50"]) else None,
        "scenario_p10": _final(s["p10"]), "scenario_p90": _final(s["p90"]), "label": "SIMULATED"}]
    stress = _stress(lever, p, central)
    sens = _sensitivity(central)
    relationships = _relationship_evidence(lever, sens)

    def fmt(v: float) -> str:
        return (f"{v:,.1f}".removesuffix(".0")) if abs(v) < 100 else f"{v:,.0f}"
    claims = [
        {"text": f"Baseline ({state['scope']}): " + "; ".join(f"{i['name'].lower()} {fmt(i['value'])} {i['unit']}" if isinstance(i['value'], (int, float)) else f"{i['name'].lower()} n/a"
                                                          for i in state["indicators"][:4]) + ".",
         "type": "analytics", "label": "OBSERVED", "numbers": [i["value"] for i in state["indicators"][:4] if isinstance(i["value"], (int, float))],
         "support": "Values read from the platform datasets listed in the current-state table."},
        {"text": f"Under the modelled assumptions, the simulated scenarios indicate a median {impact_name} of "
                 f"{fmt(_final(imp['p50']))} {impact_unit} by {last_year}, with a P10-P90 range of {fmt(_final(imp['p10']))} "
                 f"to {fmt(_final(imp['p90']))} {impact_unit} across {central['draws']:,} Monte Carlo draws.",
         "type": "simulation", "label": "SIMULATED", "numbers": [_final(imp["p50"]), _final(imp["p10"]), _final(imp["p90"])],
         "support": f"Model {central['model_id']}, seed {central['seed']}, hash {central['hash'][:12]}."},
        {"text": f"The result is {stress['stability']} to the assumptions: the conservative stress test gives a median of "
                 f"{fmt(stress['scenarios'][0]['p50'])} and the high-impact test {fmt(stress['scenarios'][2]['p50'])} {impact_unit}.",
         "type": "simulation", "label": "SIMULATED", "numbers": [stress["scenarios"][0]["p50"], stress["scenarios"][2]["p50"]],
         "support": stress["method"]},
    ]
    top = sens[0] if sens else None
    if top:
        claims.append({"text": f"The outcome depends most on '{top['parameter']}' (evidence grade {top['grade']}): moving it across "
                               f"its range changes the result by {fmt(top['swing'])} {central['unit']}.",
                       "type": "assumption", "label": "SIMULATED", "numbers": [top["swing"]], "support": top["source"]})

    gaps = []
    for srow in sens:
        if srow["level"] in ("high", "medium") and srow["grade"] in ("C", "user"):
            rel = next((r for r in relationships if r["parameter"] == srow["parameter"]), None)
            gaps.append({"kind": "unvalidated_relationship", "severity": "high" if srow["level"] == "high" else "medium",
                         "what": f"The simulation is {srow['level']}ly sensitive to '{srow['parameter']}', but this value is an "
                                 f"expert assumption (grade {srow['grade']}) with no Indian quasi-experimental estimate.",
                         "why": "Its range drives much of the spread in the outcome, so the result cannot be narrowed until "
                                "it is measured." + (f" The repository has {len(rel['literature'])} related studies, none giving "
                                                     f"an effect size." if rel and rel["literature"] else " No study in the repository addresses it."),
                         "research_requirement": f"Estimate '{srow['parameter']}' for Indian districts (e.g. a pilot with a "
                                                 f"comparison group) to narrow the simulated range."})
    for a in state["assumed_inputs"]:
        gaps.append({"kind": "missing_dataset", "severity": "high", "what": f"The baseline '{a}' is a researcher input, not platform data.",
                     "why": "The current state is illustrative until real caseload data are loaded.",
                     "research_requirement": "Obtain state RCCMS filing and disposal statistics."})
    if stress["stability"] == "highly sensitive":
        gaps.append({"kind": "weak_evidence", "severity": "medium",
                     "what": "The simulated impact changes substantially between conservative and high-impact assumptions.",
                     "why": "Decision-makers should treat the median as one point in a wide range."})
    if re.search(r"district", question, re.I) and lever != "agri_conversion" and high_risk:
        gaps.append({"kind": "missing_geography", "severity": "medium",
                     "what": f"The '{spec['name']}' lever is modelled at state/national level, not for individual districts.",
                     "why": "District-level targeting cannot be simulated for this lever with the data available."})

    return {
        "status": "ok", "lever": lever, "lever_name": spec["name"], "lever_question": spec["question"], "model_id": spec["model_id"],
        "current_state": state,
        "policy_lever": {"parameters": central["params"], "mapped_from_question": mapped, "defaults": spec["params"],
                         "param_help": spec["param_help"],
                         "statement": "The intervention is kept separate from the baseline: Baseline state + policy lever + parameters -> scenario."},
        "simulation": {"draws": central["draws"], "seed": central["seed"], "hash": central["hash"], "years": central["years"],
                       "impact_name": impact_name, "impact_unit": impact_unit,
                       "impact": {"p10": _final(imp["p10"]), "p50": _final(imp["p50"]), "p90": _final(imp["p90"])},
                       "headline": central["headline"], "label": "SIMULATED"},
        "comparison": comparison, "stress_test": stress, "sensitivity": sens,
        "evidence_behind": {
            "baseline_datasets": sorted({i["dataset"] for i in state["indicators"]}),
            "indicators_used": [i["name"] for i in state["indicators"]],
            "assumptions": [{"name": c["name"], "range": [c["low"], c["high"]], "unit": c["unit"], "grade": c["grade"], "source": c["source"]}
                            for c in central["coefficients"]],
            "relationships": relationships,
            "simulated_parts": ["future outcome paths", "policy effect sizes (drawn from the ranges above)", "stress-test scenarios"],
        },
        "run": central, "claims": claims, "gaps": gaps,
    }
