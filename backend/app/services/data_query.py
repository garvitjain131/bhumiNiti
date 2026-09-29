"""
Data Query pipeline (SQL / Analytics) for the research assistant.

Answers the structured part of a question from the platform's district tables and the existing analytics
(trend, correlation). Every analysis keeps its provenance: dataset, indicator, geographic scope, time period,
method, result, the rows behind it, and the kind of evidence it is (OBSERVED / ESTIMATED / DESCRIPTIVE /
CORRELATIONAL). Nothing here is a model of cause and effect.
"""
from __future__ import annotations

import re

from fastapi import HTTPException

from ..core.db import one, rows

# Where each district metric comes from (dataset shown with every analytical claim).
METRIC_DATASETS = {
    "conflicts": "Land Conflict Watch (documented cases)",
    "conflict_people": "Land Conflict Watch (documented cases)",
    "built_km2_2020": "GHSL built-up surface (JRC)",
    "built_growth_2000_2020": "GHSL built-up surface (JRC)",
    "crops_change_2017_2025": "Dynamic World land cover (Google / WRI)",
    "built_share_change_2017_2025": "Dynamic World land cover (Google / WRI)",
    "cropland_change_2001_2023": "MODIS land cover (NASA)",
    "ntl_2025": "VIIRS night lights (NOAA)",
    "ntl_growth_2014_2025": "VIIRS night lights (NOAA)",
    "rain_mean": "CHIRPS rainfall",
    "rain_cv": "CHIRPS rainfall",
    "tree_cover": "MODIS vegetation continuous fields (via SHRUG)",
    "population_2011": "Census of India 2011",
    "landslides": "GSI national landslide inventory",
    "earthquakes_m4": "NGDR earthquake catalogue",
    "flood_share": "NDEM flood inundation 1998-2022",
    "climate_risk_index": "Composite of CHIRPS, NDEM, GSI and MODIS VCF",
}
# Count metrics are summed over an area; everything else is summarised by its median.
COUNT_METRICS = {"conflicts", "conflict_people", "landslides", "earthquakes_m4", "population_2011", "built_km2_2020"}
# District metric -> yearly indicator used for trend questions.
TREND_INDICATORS = {
    "crops_change_2017_2025": ("dw_crops", "Dynamic World cropland share", 100, "% of area"),
    "built_growth_2000_2020": ("ghsl_built_km2", "GHSL built-up area", 1, "km2"),
    "ntl_growth_2014_2025": ("viirs_ntl_mean", "VIIRS night-light radiance", 1, "nW/cm2/sr"),
    "rain_mean": ("chirps_rain_mm", "CHIRPS annual rainfall", 1, "mm"),
    "rain_cv": ("chirps_rain_mm", "CHIRPS annual rainfall", 1, "mm"),
    "tree_cover": ("vcf_mean", "MODIS tree cover", 1, "%"),
}
ASCENDING_WORDS = r"\b(lowest|least|fewest|bottom|loss|losing|decline|declining|shrink\w*|fall\w*)\b"


def _meta(metric: str) -> dict:
    m = one("SELECT metric, name, unit, theme, higher_is, method FROM metric_meta WHERE metric = ?", [metric]) or {}
    years = re.findall(r"(?:19|20)\d\d", m.get("name", ""))
    m["period"] = "-".join(years) if years else "latest available"
    m["dataset"] = METRIC_DATASETS.get(metric, "platform district metrics")
    return m


def _scope(states: list[str]) -> tuple[str, list, str]:
    if states:
        return "g.state_name IN (SELECT upper(unnest(?::VARCHAR[])))", [states], ", ".join(s.title() for s in states)
    return "TRUE", [], "India (all districts)"


def _fmt(v) -> str:
    if v is None:
        return "n/a"
    if abs(v) >= 100:
        return f"{v:,.0f}"
    return f"{v:,.2f}".rstrip("0").rstrip(".")


def ranking(metric: str, states: list[str], ascending: bool, limit: int = 10) -> dict:
    meta = _meta(metric)
    where, params, scope = _scope(states)
    order = "ASC" if ascending else "DESC"
    top = rows(f"""SELECT g.name, g.state_name, g.district_lgd, round(d.value, 3) AS value, d.label
                   FROM district_metric d JOIN geo_district g USING (district_lgd)
                   WHERE d.metric = ? AND d.value IS NOT NULL AND {where}
                   ORDER BY d.value {order} LIMIT ?""", [metric, *params, limit])
    agg = "sum(d.value)" if metric in COUNT_METRICS else "median(d.value)"
    summary = one(f"""SELECT count(*) FILTER (WHERE d.value IS NOT NULL) AS with_data, count(*) AS districts,
                             {agg} AS aggregate
                      FROM geo_district g LEFT JOIN district_metric d ON d.district_lgd = g.district_lgd AND d.metric = ?
                      WHERE {where}""", [metric, *params])
    label = top[0]["label"] if top else "OBSERVED"
    unit = meta.get("unit") or ""
    unit_word = "" if unit == "count" else f" {unit}"
    agg_word = "total" if metric in COUNT_METRICS else "median"
    claims = []
    if top:
        lead = top[0]
        claims.append({
            "text": f"In {scope}, the district with the {'lowest' if ascending else 'highest'} {meta['name'].lower()} is "
                    f"{lead['name'].title()} ({lead['state_name'].title()}), with {_fmt(lead['value'])}{unit_word}.",
            "numbers": [lead["value"]]})
        claims.append({
            "text": f"The next districts are " + "; ".join(f"{r['name'].title()} ({_fmt(r['value'])})" for r in top[1:5]) + ".",
            "numbers": [r["value"] for r in top[1:5]]})
    if summary and summary["aggregate"] is not None:
        claims.append({
            "text": f"The {agg_word} across the {summary['with_data']} districts with data in {scope} is "
                    f"{_fmt(summary['aggregate'])}{unit_word}.",
            "numbers": [summary["aggregate"], summary["with_data"]]})
    return {
        "kind": "ranking", "title": f"{'Lowest' if ascending else 'Highest'} {meta.get('name', metric).lower()} by district",
        "dataset": meta["dataset"], "indicator": metric, "indicator_name": meta.get("name"), "unit": unit,
        "scope": scope, "period": meta["period"], "method": f"Ranking of districts on '{meta.get('name')}'; {meta.get('method')}",
        "label": label, "rows": top,
        "result": {"aggregate": summary["aggregate"] if summary else None, "aggregate_kind": agg_word,
                   "districts_with_data": summary["with_data"] if summary else 0,
                   "districts_in_scope": summary["districts"] if summary else 0},
        "claims": claims,
    }


def correlation(x: str, y: str) -> dict | None:
    from ..routers import analytics
    try:
        c = analytics.correlate(x, y)
    except HTTPException:
        return None
    mx, my = _meta(x), _meta(y)
    strength = abs(c["spearman_rho"])
    word = "strong" if strength >= 0.5 else "moderate" if strength >= 0.3 else "weak"
    return {
        "kind": "correlation", "title": f"{mx['name']} vs {my['name']}",
        "dataset": f"{mx['dataset']}; {my['dataset']}", "indicator": f"{x} ~ {y}",
        "indicator_name": f"{mx['name']} / {my['name']}", "unit": "Spearman rho", "scope": "India (districts with both metrics)",
        "period": f"{mx['period']} / {my['period']}", "method": "Spearman rank correlation across districts",
        "label": "CORRELATIONAL", "rows": [],
        "result": {"spearman_rho": round(c["spearman_rho"], 3), "p_value": c["p_value"], "n": c["n"]},
        "claims": [{"text": f"Across {c['n']} districts, {mx['name'].lower()} and {my['name'].lower()} show a {word} "
                            f"{'positive' if c['spearman_rho'] > 0 else 'negative'} association (Spearman rho "
                            f"{c['spearman_rho']:.2f}, p = {c['p_value']:.3g}); this is an association, not a cause.",
                    "numbers": [round(c["spearman_rho"], 2), c["n"]]}],
    }


def trend(metric: str, states: list[str]) -> dict | None:
    state = states[0] if states else None
    scope = state.title() if state else "India"
    if metric in ("conflicts", "conflict_people"):
        series = rows("""SELECT year_started::INT AS year, count(*) AS value FROM land_conflict
                         WHERE year_started BETWEEN 2000 AND 2024 AND (? IS NULL OR soi_state = upper(?))
                         GROUP BY 1 ORDER BY 1""", [state, state])
        if len(series) < 3:
            return None
        recent = sum(r["value"] for r in series if r["year"] >= 2015)
        earlier = sum(r["value"] for r in series if 2005 <= r["year"] < 2015)
        return {
            "kind": "trend", "title": "Documented land conflicts by start year", "dataset": METRIC_DATASETS["conflicts"],
            "indicator": "land_conflict.year_started", "indicator_name": "New documented conflicts per year", "unit": "cases",
            "scope": scope, "period": f"{series[0]['year']}-{series[-1]['year']}", "method": "Count of documented cases by start year",
            "label": "OBSERVED", "rows": series, "result": {"cases_2015_2024": recent, "cases_2005_2014": earlier},
            "claims": [{"text": f"In {scope}, {recent} documented conflicts started in 2015-2024, against {earlier} in 2005-2014 "
                                f"(documented cases only; reporting has grown over time).", "numbers": [recent, earlier]}],
        }
    if metric not in TREND_INDICATORS:
        return None
    from ..routers import analytics
    indicator, name, scale, unit = TREND_INDICATORS[metric]
    try:
        t = analytics.trend(indicator, None, state)
    except HTTPException:
        return None
    s = t["series"]
    first, last = s[0], s[-1]
    lo, hi = (v * scale for v in t["slope_ci95"])
    return {
        "kind": "trend", "title": f"{name} over time", "dataset": METRIC_DATASETS.get(metric, ""), "indicator": indicator,
        "indicator_name": name, "unit": unit, "scope": scope, "period": f"{first['year']}-{last['year']}",
        "method": t["method"], "label": "DESCRIPTIVE", "rows": s,
        "result": {"slope_per_year": t["slope_per_year"] * scale, "slope_ci95": [lo, hi],
                   "kendall_tau": t["monotonic_trend"]["kendall_tau"], "p_value": t["monotonic_trend"]["p_value"]},
        "claims": [{"text": f"{name} in {scope} moved from {_fmt(first['value'] * scale)} to {_fmt(last['value'] * scale)} {unit} "
                            f"between {first['year']} and {last['year']} (trend {t['slope_per_year'] * scale:+.3g} {unit} per year, "
                            f"95% CI {lo:+.3g} to {hi:+.3g}).",
                    "numbers": [first["value"] * scale, last["value"] * scale]}],
    }


def run(question: str, entities: dict) -> dict:
    """Run the analyses the question asks for; return them with their provenance and any data gaps."""
    metrics = entities.get("metrics") or []
    states = entities.get("states") or []
    analyses, gaps = [], []
    if not metrics:
        gaps.append({"kind": "missing_indicator", "what": "No platform indicator matches the quantities in this question.",
                     "why": "Without a measured indicator the data pipeline cannot test the claim; the answer relies on "
                            "documents only.", "severity": "medium"})
        return {"analyses": [], "gaps": gaps, "high_risk_districts": []}

    wants_corr = re.search(r"correlat|relationship|associat|linked|related to", question, re.I) and len(metrics) >= 2
    wants_trend = re.search(r"trend|over time|since (19|20)\d\d|changing|increas\w* over|growth over", question, re.I)
    ascending = bool(re.search(ASCENDING_WORDS, question, re.I)) and metrics[0] in (
        "crops_change_2017_2025", "cropland_change_2001_2023", "tree_cover", "rain_mean")

    if wants_corr:
        c = correlation(metrics[0], metrics[1])
        if c:
            analyses.append(c)
    if wants_trend:
        t = trend(metrics[0], states)
        if t:
            analyses.append(t)
        else:
            gaps.append({"kind": "missing_time_series", "what": f"No yearly series for '{_meta(metrics[0]).get('name', metrics[0])}'.",
                         "why": "The trend cannot be measured; only a single-period value is available.", "severity": "medium"})
    for m in metrics[:2]:
        analyses.append(ranking(m, states, ascending if m == metrics[0] else False))

    # data-coverage gaps (geography) for every ranked metric
    for a in analyses:
        if a["kind"] != "ranking":
            continue
        r = a["result"]
        share = r["districts_with_data"] / max(r["districts_in_scope"], 1)
        if a["indicator"] in ("conflicts", "conflict_people"):
            gaps.append({"kind": "weak_evidence", "what": f"Land-conflict figures are documented cases only ({r['districts_with_data']} "
                                                          f"of {r['districts_in_scope']} districts have at least one).",
                         "why": "Districts without media or civil-society reporting look conflict-free; official revenue-court "
                                "dispute data would give complete coverage.", "severity": "high"})
        elif share < 0.9:
            gaps.append({"kind": "missing_geography", "what": f"{a['indicator_name']} covers {r['districts_with_data']} of "
                                                              f"{r['districts_in_scope']} districts in {a['scope']}.",
                         "why": "Rankings and totals exclude districts without data.", "severity": "medium"})
    risk = next((a for a in analyses if a["kind"] == "ranking" and a["indicator"] == metrics[0]), None)
    return {"analyses": analyses, "gaps": gaps,
            "high_risk_districts": [r["district_lgd"] for r in (risk["rows"] if risk else [])]}
