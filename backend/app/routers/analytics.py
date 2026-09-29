"""
Advanced analytics & decision support (#11) and AI-assisted research tools (#14): trend analysis,
forecasting with prediction intervals and back-tests, emerging-trend/anomaly detection, correlation,
and a difference-in-differences policy evaluation. Every result states what kind of evidence it is.
"""
from __future__ import annotations

import numpy as np
from fastapi import APIRouter, HTTPException, Query
from scipy import stats

from ..core.db import one, rows

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics & decision support"])

SHARE = ("dw_", "modis_")  # shares of district area -> area-weighted mean when aggregating


def series(indicator: str, district_lgd: int | None = None, state: str | None = None) -> list[dict]:
    if district_lgd:
        return rows("SELECT year, value FROM indicator WHERE indicator = ? AND district_lgd = ? ORDER BY year",
                    [indicator, district_lgd])
    agg = ("sum(i.value * g.area_km2) / sum(g.area_km2)" if indicator.startswith(SHARE) or indicator in
           ("chirps_rain_mm", "vcf_mean", "viirs_ntl_mean", "viirs_annual_mean") else "sum(i.value)")
    return rows(f"""SELECT i.year, {agg} AS value FROM indicator i JOIN geo_district g USING (district_lgd)
                    WHERE i.indicator = ? AND (? IS NULL OR g.state_name = upper(?)) GROUP BY 1 ORDER BY 1""",
                [indicator, state, state])


def _ols(x, y):
    res = stats.linregress(x, y)
    n = len(x)
    tcrit = stats.t.ppf(0.975, max(n - 2, 1))
    return res, tcrit


@router.get("/trend")
def trend(indicator: str, district_lgd: int | None = None, state: str | None = None):
    """Linear trend with 95% confidence interval and Mann-Kendall-style monotonicity test. DESCRIPTIVE."""
    s = series(indicator, district_lgd, state)
    if len(s) < 3:
        raise HTTPException(404, "not enough years for this indicator/area")
    x, y = np.array([r["year"] for r in s], float), np.array([r["value"] for r in s], float)
    res, t = _ols(x, y)
    tau = stats.kendalltau(x, y)
    return {"indicator": indicator, "area": district_lgd or state or "India", "series": s,
            "slope_per_year": res.slope, "slope_ci95": [res.slope - t * res.stderr, res.slope + t * res.stderr],
            "r2": res.rvalue ** 2, "change_total": y[-1] - y[0], "change_pct": (y[-1] / y[0] - 1) * 100 if y[0] else None,
            "monotonic_trend": {"kendall_tau": tau.statistic, "p_value": tau.pvalue},
            "evidence_type": "DESCRIPTIVE", "method": "Ordinary least squares on annual values; Kendall's tau."}


@router.get("/forecast")
def forecast(indicator: str, district_lgd: int | None = None, state: str | None = None,
             to_year: int = Query(2030, le=2040), fit_years: int = Query(10, ge=4)):
    """Registered forecast model: linear trend on the most recent years with 80% and 95% prediction intervals,
    plus a back-test on the last 3 observed years. Output is labelled PREDICTED."""
    s = [r for r in series(indicator, district_lgd, state) if r["value"] is not None]
    if indicator == "ghsl_built_km2":
        s = [r for r in s if r["year"] <= 2020]  # GHSL 2025/2030 are themselves projections
    if len(s) < 5:
        raise HTTPException(404, "need at least 5 observed years")
    s = s[-fit_years:]
    x, y = np.array([r["year"] for r in s], float), np.array([r["value"] for r in s], float)

    def fit_predict(xf, yf, xp, level):
        res, _ = _ols(xf, yf)
        n, xm = len(xf), xf.mean()
        resid = yf - (res.intercept + res.slope * xf)
        se = np.sqrt((resid ** 2).sum() / max(n - 2, 1))
        tq = stats.t.ppf(0.5 + level / 2, max(n - 2, 1))
        half = tq * se * np.sqrt(1 + 1 / n + (xp - xm) ** 2 / ((xf - xm) ** 2).sum())
        mean = res.intercept + res.slope * xp
        return mean, mean - half, mean + half

    xp = np.arange(x[-1] + 1, to_year + 1, dtype=float)
    mean, lo80, hi80 = fit_predict(x, y, xp, 0.8)
    _, lo95, hi95 = fit_predict(x, y, xp, 0.95)
    # back-test: fit without the last 3 years, predict them
    bt = None
    if len(x) >= 7:
        m3, l3, h3 = fit_predict(x[:-3], y[:-3], x[-3:], 0.8)
        mape = float(np.mean(np.abs((y[-3:] - m3) / np.where(y[-3:] == 0, np.nan, y[-3:]))) * 100)
        bt = {"held_out_years": x[-3:].astype(int).tolist(), "observed": y[-3:].tolist(), "predicted": m3.tolist(),
              "mape_pct": None if np.isnan(mape) else round(mape, 2),
              "inside_80pct_interval": int(((y[-3:] >= l3) & (y[-3:] <= h3)).sum())}
    return {"indicator": indicator, "area": district_lgd or state or "India", "observed": s,
            "forecast": [{"year": int(a), "p50": float(b), "p10": float(c), "p90": float(d), "p2_5": float(e),
                          "p97_5": float(f)} for a, b, c, d, e, f in zip(xp, mean, lo80, hi80, lo95, hi95)],
            "backtest": bt, "evidence_type": "PREDICTED",
            "model": {"id": "trend-forecast-v1", "method": "OLS linear trend on the last "
                      f"{len(s)} observed years; t-based prediction intervals",
                      "assumption": "the recent trend continues; no policy or shock changes it"}}


@router.get("/emerging")
def emerging(limit: int = 12):
    """Emerging trends: districts with the fastest land-use change, and statistical anomalies in the latest year."""
    def top(metric, order):
        return rows(f"""SELECT g.name, g.state_name, g.district_lgd, round(value, 2) AS value FROM district_metric d
                        JOIN geo_district g USING (district_lgd) WHERE metric = ? ORDER BY value {order} LIMIT ?""",
                    [metric, limit])
    anomalies = rows("""
        WITH yoy AS (
            SELECT district_lgd, year, value - lag(value) OVER (PARTITION BY district_lgd ORDER BY year) AS d
            FROM indicator WHERE indicator = 'dw_crops'),
        z AS (SELECT district_lgd, year, d, (d - avg(d) OVER (PARTITION BY year)) /
                     nullif(stddev(d) OVER (PARTITION BY year), 0) AS z FROM yoy WHERE d IS NOT NULL)
        SELECT g.name, g.state_name, z.district_lgd, z.year, round(100 * z.d, 1) AS change_pp, round(z.z, 2) AS z_score
        FROM z JOIN geo_district g USING (district_lgd)
        WHERE z.year = (SELECT max(year) FROM z) AND abs(z.z) >= 2.5 ORDER BY abs(z.z) DESC LIMIT ?""", [limit])
    return {"fastest_built_up_growth": top("built_growth_2000_2020", "DESC"),
            "largest_cropland_loss": top("crops_change_2017_2025", "ASC"),
            "fastest_night_light_growth": top("ntl_growth_2014_2025", "DESC"),
            "anomalies": {"indicator": "Dynamic World cropland share, change since the previous observed year",
                          "rule": "|z| >= 2.5 across districts", "items": anomalies,
                          "note": "An anomaly is a statistical outlier to investigate, not evidence of wrongdoing."},
            "evidence_type": "DESCRIPTIVE"}


@router.get("/correlate")
def correlate(x: str, y: str):
    """Correlation between two district metrics (Spearman). CORRELATIONAL, never causal."""
    d = rows("""SELECT g.name, g.state_name, max(value) FILTER (WHERE metric = ?) AS x,
                       max(value) FILTER (WHERE metric = ?) AS y
                FROM district_metric JOIN geo_district g USING (district_lgd) GROUP BY ALL""", [x, y])
    d = [r for r in d if r["x"] is not None and r["y"] is not None]
    if len(d) < 10:
        raise HTTPException(404, "too few districts have both metrics")
    rho = stats.spearmanr([r["x"] for r in d], [r["y"] for r in d])
    return {"x": x, "y": y, "n": len(d), "spearman_rho": rho.statistic, "p_value": rho.pvalue, "points": d,
            "evidence_type": "CORRELATIONAL",
            "caveat": "Association only. Confounders (geography, population, economy) are not controlled for."}


@router.get("/evaluate")
def evaluate(treatment: str = Query("ulpin_pct>=90", description="state-level rule on DILRMP: field>=value or field<=value"),
             outcome: str = Query("dw_built", description="time-series indicator"),
             pre: str = "2017-2019", post: str = "2023-2025", boot: int = Query(500, le=2000)):
    """Policy-effectiveness example: difference-in-differences between districts in states that did / did not
    reach a DILRMP milestone, with a state-clustered bootstrap CI. Treatment timing is not observed, so this
    is ILLUSTRATIVE (correlational), and the response says so."""
    field, op, val = None, None, None
    for o in (">=", "<="):
        if o in treatment:
            field, val = treatment.split(o)
            op = o
    if field not in ("ulpin_pct", "georef_pct", "maps_digitised_pct", "ror_pct"):
        raise HTTPException(400, "treatment must be like ulpin_pct>=90 on ulpin_pct|georef_pct|maps_digitised_pct|ror_pct")
    p0, p1 = (int(v) for v in pre.split("-"))
    q0, q1 = (int(v) for v in post.split("-"))
    d = rows(f"""
        SELECT g.district_lgd, g.state_name, (d.{field} {op} ?) AS treated,
               avg(i.value) FILTER (WHERE i.year BETWEEN ? AND ?) AS pre,
               avg(i.value) FILTER (WHERE i.year BETWEEN ? AND ?) AS post
        FROM indicator i JOIN geo_district g USING (district_lgd) JOIN dilrmp_state d ON d.soi_state_name = g.state_name
        WHERE i.indicator = ? AND d.{field} IS NOT NULL GROUP BY ALL""", [float(val), p0, p1, q0, q1, outcome])
    d = [r for r in d if r["pre"] is not None and r["post"] is not None]
    if not d:
        raise HTTPException(404, "no data for this outcome/period")
    diff = np.array([r["post"] - r["pre"] for r in d])
    tr = np.array([bool(r["treated"]) for r in d])
    if tr.all() or (~tr).all():
        raise HTTPException(400, "rule puts every district in one group; change the threshold")
    did = diff[tr].mean() - diff[~tr].mean()
    states = np.array([r["state_name"] for r in d])
    uniq = np.unique(states)
    rng, est = np.random.default_rng(0), []
    for _ in range(boot):
        pick = rng.choice(uniq, len(uniq), replace=True)
        idx = np.concatenate([np.where(states == s)[0] for s in pick])
        t_, d_ = tr[idx], diff[idx]
        if t_.any() and (~t_).any():
            est.append(d_[t_].mean() - d_[~t_].mean())
    lo, hi = np.percentile(est, [2.5, 97.5]) if est else (None, None)
    return {"treatment": treatment, "outcome": outcome, "pre": pre, "post": post,
            "treated_districts": int(tr.sum()), "control_districts": int((~tr).sum()),
            "treated_states": sorted(set(states[tr])), "change_treated": diff[tr].mean(), "change_control": diff[~tr].mean(),
            "did_estimate": did, "ci95_state_bootstrap": [lo, hi],
            "significant_at_5pct": bool(lo is not None and (lo > 0 or hi < 0)),
            "evidence_type": "CORRELATIONAL (illustrative difference-in-differences)",
            "caveats": ["Treatment is today's DILRMP status, not the year it was reached: timing is not observed.",
                        "States self-select into faster progress; parallel pre-trends are not tested here.",
                        "Use a staggered-adoption estimator (Callaway & Sant'Anna) once rollout dates are compiled."]}


@router.get("/models")
def model_registry():
    """Registry of every analytical model the platform runs: purpose, method, data, limits."""
    n_ev = one("SELECT count(*) AS n FROM evidence_item")["n"]
    return [
        {"id": "trend-forecast-v1", "purpose": "Forecast district/state indicators to 2030", "method": "OLS trend, "
         "t prediction intervals, 3-year back-test", "data": "Earth Engine district panel; Census/SHRUG",
         "output_label": "PREDICTED", "limitations": "Assumes the recent trend continues; no causal structure."},
        {"id": "sim-agri-conversion-v1", "purpose": "Simulate zoning / conversion-control policy", "method":
         "Trend baseline + policy effect on conversion rate, Monte Carlo (P10/P50/P90), tornado sensitivity",
         "data": "GHSL built-up, Dynamic World cropland", "output_label": "SIMULATED",
         "limitations": "Effect sizes are graded assumptions (see lever spec)."},
        {"id": "sim-acquisition-reform-v1", "purpose": "Simulate land-acquisition rule changes", "method":
         "Conflict incidence baseline x graded elasticities, Monte Carlo", "data": "Land Conflict Watch",
         "output_label": "SIMULATED", "limitations": "Conflict counts are documented cases, not all disputes."},
        {"id": "sim-dispute-pendency-v1", "purpose": "Revenue-court pendency under faster disposal / ULPIN",
         "method": "Little's law steady state, Monte Carlo", "data": "User-supplied or state RCCMS baseline",
         "output_label": "SIMULATED", "limitations": "Needs state filing/disposal data for calibration."},
        {"id": "climate-risk-index-v1", "purpose": "Screen districts for climate exposure", "method":
         "Mean percentile of rainfall variability, flood exposure, landslides, low tree cover",
         "data": "CHIRPS, NDEM, GSI, MODIS VCF", "output_label": "ESTIMATED",
         "limitations": "Screening index; not a substitute for the DST vulnerability assessment."},
        {"id": "semantic-search-lsa-v1", "purpose": "Semantic retrieval and recommendations", "method":
         "TF-IDF + truncated SVD (256 dims), fused with BM25 by reciprocal rank", "data": f"{n_ev:,} evidence items",
         "output_label": "n/a", "limitations": "English only; replace with multilingual embeddings for Hindi."},
        {"id": "query-router-v1", "purpose": "Research assistant: decide whether a question needs documents, data or "
         "a policy simulation", "method": "Rule-based phrase patterns; multi-part questions split into clauses per pipeline",
         "data": "question text", "output_label": "n/a", "limitations": "Unusual phrasing can be mis-routed; the researcher "
         "can force pipelines and the lever."},
        {"id": "policy-digital-twin-v1", "purpose": "Research assistant: current state + policy lever -> scenario, "
         "stress test, sensitivity, evidence gaps", "method": "Baseline from platform tables; sim-* levers (Monte Carlo); "
         "conservative/central/high-impact coefficient thirds; tornado ranking", "data": "DILRMP-MIS, Land Conflict Watch, "
         "GHSL, Dynamic World", "output_label": "SIMULATED", "limitations": "Only three levers are modelled; grade C "
         "coefficients are expert assumptions and are reported as evidence gaps."},
        {"id": "evidence-synthesis-v1", "purpose": "Research assistant: cited answer from the verified evidence matrix",
         "method": "Template synthesis (offline); optional LLM wording whose sentences must cite claims and may only "
         "repeat their numbers", "data": "evidence matrix", "output_label": "per claim",
         "limitations": "Template wording is plain; LLM wording is off unless LPIP_LLM is set."},
        {"id": "evidence-classifier-v1", "purpose": "Method and direction-of-effect tags for the evidence matrix",
         "method": "Rule-based patterns on titles/abstracts", "data": "abstracts", "output_label": "heuristic",
         "limitations": "Coarse; always shown with the sources for checking."},
    ]
