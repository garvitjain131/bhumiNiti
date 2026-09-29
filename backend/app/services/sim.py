"""
Policy simulation engine (#12). Each lever is a small transparent model:
  baseline (from platform data) + policy effect (graded coefficients with ranges) -> Monte Carlo -> P10/P50/P90,
  plus a one-at-a-time sensitivity (tornado). Evidence grades: A = Indian quasi-experimental study,
  B = estimated from this platform's data or international evidence, C = expert assumption (widest range).
Results are SIMULATED scenarios ("what the evidence suggests"), never predictions.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

import numpy as np

from ..core.db import one, rows


@dataclass
class Coef:
    name: str
    low: float
    high: float
    grade: str
    source: str
    unit: str = ""

    def draw(self, rng, n):
        return rng.uniform(self.low, self.high, n)

    @property
    def mid(self):
        return (self.low + self.high) / 2


def _geo_filter(geo: dict) -> tuple[str, list]:
    if geo.get("districts"):
        return "g.district_lgd IN (SELECT unnest(?::INTEGER[]))", [geo["districts"]]
    if geo.get("state"):
        return "g.state_name = upper(?)", [geo["state"]]
    return "TRUE", []


def _override(coefs: dict, p: dict) -> dict:
    """Users may replace any coefficient range after reading its source; the change is recorded in the run."""
    for k, rng_ in (p.get("coef_overrides") or {}).items():
        if k in coefs and isinstance(rng_, (list, tuple)) and len(rng_) == 2 and rng_[0] <= rng_[1]:
            c = coefs[k]
            coefs[k] = Coef(c.name, float(rng_[0]), float(rng_[1]), "user", f"Overridden by user (was {c.low}-{c.high}; "
                            f"{c.source})", c.unit)
    return coefs


def _pct(a: np.ndarray, axis=0) -> dict:
    p = np.percentile(a, [10, 50, 90], axis=axis)
    return {"p10": p[0].tolist(), "p50": p[1].tolist(), "p90": p[2].tolist()}


# =========================================================================== lever 1: agricultural conversion

def _conversion_coefficient() -> Coef:
    """Share of new built-up land that replaced cropland, estimated from Dynamic World 2017->2025 per district."""
    r = rows("""
        WITH d AS (
            SELECT district_lgd,
                   max(value) FILTER (WHERE indicator = 'dw_crops' AND year = 2025) - max(value) FILTER (WHERE indicator = 'dw_crops' AND year = 2017) AS dc,
                   max(value) FILTER (WHERE indicator = 'dw_built' AND year = 2025) - max(value) FILTER (WHERE indicator = 'dw_built' AND year = 2017) AS db
            FROM indicator WHERE indicator IN ('dw_crops', 'dw_built') GROUP BY 1)
        SELECT quantile_cont(least(greatest(-dc / db, 0), 1), 0.25) AS q25,
               quantile_cont(least(greatest(-dc / db, 0), 1), 0.75) AS q75, count(*) AS n
        FROM d WHERE db > 0.002 AND dc < 0""")[0]
    lo, hi = (r["q25"] or 0.3), (r["q75"] or 0.8)
    return Coef("share of new built-up land taken from cropland", round(lo, 3), round(max(hi, lo + 0.05), 3), "B",
                f"Estimated on this platform: -change in cropland share / change in built-up share, Dynamic World "
                f"2017-2025, interquartile range across {r['n']} districts where both moved", "fraction")


def sim_agri_conversion(p: dict, rng, n: int) -> dict:
    where, params = _geo_filter(p)
    base = one(f"""
        SELECT sum(b20) AS built2020, sum(b10) AS built2010, sum(crop_km2) AS crop_km2, count(*) AS districts
        FROM (SELECT g.district_lgd,
                     max(i.value) FILTER (WHERE i.indicator = 'ghsl_built_km2' AND i.year = 2020) AS b20,
                     max(i.value) FILTER (WHERE i.indicator = 'ghsl_built_km2' AND i.year = 2010) AS b10,
                     max(i.value) FILTER (WHERE i.indicator = 'dw_crops' AND i.year = 2025) * any_value(g.area_km2) AS crop_km2
              FROM indicator i JOIN geo_district g USING (district_lgd) WHERE {where} GROUP BY 1)""", params)
    if not base or not base["built2020"]:
        raise ValueError("no data for the selected geography")
    growth_obs = (base["built2020"] / base["built2010"]) ** (1 / 10) - 1
    coefs = {
        "growth": Coef("built-up growth per year", max(growth_obs * 0.7, 0), growth_obs * 1.3, "B",
                       f"GHSL 2010-2020 compound growth in the selected area ({growth_obs:.2%}/yr), +/-30%", "per year"),
        "phi": _conversion_coefficient(),
        "compliance": Coef("enforcement compliance", max(p["compliance"] - 0.15, 0), min(p["compliance"] + 0.15, 1), "C",
                           "User setting +/-15 points (enforcement capacity is uncertain)", "fraction"),
        "leakage": Coef("leakage to non-restricted land", 0.1, 0.4, "C",
                        "Expert assumption: part of blocked conversion moves to other farmland or districts", "fraction"),
    }
    coefs = _override(coefs, p)
    years = np.arange(2026, p["to_year"] + 1)
    t = years - 2025
    built0 = base["built2020"] * (1 + growth_obs) ** 5            # carry GHSL 2020 to 2025 at observed growth

    def run(draw: dict) -> tuple[np.ndarray, np.ndarray]:
        g, phi, comp, leak = (draw[k][:, None] for k in ("growth", "phi", "compliance", "leakage"))
        new_built = built0 * ((1 + g) ** t - (1 + g) ** (t - 1))          # km2 added each year
        loss_base = new_built * phi
        started = (years >= p["start_year"])[None, :]
        avoided = loss_base * p["strength"] * comp * (1 - leak) * started
        return np.cumsum(loss_base, axis=1), np.cumsum(loss_base - avoided, axis=1)

    draws = {k: c.draw(rng, n) for k, c in coefs.items()}
    cum_base, cum_pol = run(draws)
    saved = cum_base - cum_pol
    torn = []
    for k, c in coefs.items():
        vals = []
        for v in (c.low, c.high):
            d = {kk: np.full(1, cc.mid) for kk, cc in coefs.items()}
            d[k] = np.full(1, v)
            b, pol = run(d)
            vals.append(float((b - pol)[0, -1]))
        torn.append({"parameter": c.name, "low": vals[0], "high": vals[1], "swing": abs(vals[1] - vals[0])})
    torn.sort(key=lambda x: -x["swing"])
    return {
        "unit": "km2 of cropland", "years": years.tolist(),
        "baseline": {"cumulative_cropland_lost": _pct(cum_base)},
        "scenario": {"cumulative_cropland_lost": _pct(cum_pol)},
        "impact": {"cropland_saved_km2": _pct(saved), "saved_share_of_baseline_loss_pct":
                   float(np.median(saved[:, -1] / np.maximum(cum_base[:, -1], 1e-9) * 100))},
        "context": {"districts": base["districts"], "cropland_2025_km2": base["crop_km2"],
                    "built_2020_km2": base["built2020"], "observed_builtup_growth_per_year": growth_obs},
        "coefficients": coefs, "tornado": torn,
        "headline": f"By {years[-1]}, the rule avoids a median {np.median(saved[:, -1]):,.0f} km2 of cropland loss "
                    f"(P10-P90: {np.percentile(saved[:, -1], 10):,.0f} to {np.percentile(saved[:, -1], 90):,.0f} km2).",
    }


# =========================================================================== lever 2: land-acquisition reform

ACQ_SECTORS = ("Infrastructure", "Industry", "Power", "Mining")


def sim_acquisition(p: dict, rng, n: int) -> dict:
    where, params = ("TRUE", [])
    if p.get("state"):
        where, params = "soi_state = upper(?)", [p["state"]]
    base = one(f"""
        SELECT count(*) FILTER (WHERE year_started BETWEEN 2015 AND 2024) / 10.0 AS per_year,
               median(people_affected) AS people_median, count(*) AS total
        FROM land_conflict WHERE sector IN {ACQ_SECTORS} AND {where}""", params)
    if not base or not base["per_year"]:
        raise ValueError("no documented acquisition-related conflicts for this geography")
    consent_on = p["consent_threshold"] >= 50
    coefs = {
        "consent_effect": Coef("conflict reduction from prior-consent rule", 0.10 if consent_on else 0,
                               0.35 if consent_on else 0, "C",
                               "Expert assumption informed by RFCTLARR 2013 consent provisions (70%/80%); no Indian "
                               "quasi-experimental estimate yet - a research gap", "fraction"),
        "comp_elasticity": Coef("conflict reduction per +1x compensation", 0.03, 0.10, "C",
                                "Expert assumption; compensation disputes are a leading cause in LCW records", "per 1x"),
        "sia_effect": Coef("conflict reduction from mandatory social impact assessment", 0.05 if p["sia"] else 0,
                           0.15 if p["sia"] else 0, "C", "Expert assumption", "fraction"),
        "delay_consent": Coef("added project delay from consent process", 3 if consent_on else 0,
                              9 if consent_on else 0, "C", "Expert assumption", "months"),
        "baseline_noise": Coef("baseline conflict rate uncertainty", 0.8, 1.2, "B",
                               f"LCW documented cases 2015-2024 ({base['per_year']:.1f}/yr), +/-20% (under-reporting)",
                               "multiplier"),
    }
    coefs = _override(coefs, p)
    years = np.arange(2026, p["to_year"] + 1)
    comp_add = max(p["compensation_multiplier"] - 2.0, 0)  # RFCTLARR baseline: up to 2x rural (factor) - simplified

    def run(d):
        red = 1 - np.clip(d["consent_effect"] + d["comp_elasticity"] * comp_add + d["sia_effect"], 0, 0.8)
        rate_b = base["per_year"] * d["baseline_noise"]
        return rate_b, rate_b * red, d["delay_consent"]

    draws = {k: c.draw(rng, n) for k, c in coefs.items()}
    rb, rp, delay = run(draws)
    cum_b, cum_p = np.outer(rb, np.ones(len(years))).cumsum(1), np.outer(rp, np.ones(len(years))).cumsum(1)
    people = float(base["people_median"] or 0)
    torn = []
    for k, c in coefs.items():
        vals = []
        for v in (c.low, c.high):
            d = {kk: np.full(1, cc.mid) for kk, cc in coefs.items()}
            d[k] = np.full(1, v)
            b, pol, _ = run(d)
            vals.append(float((b - pol)[0] * len(years)))
        torn.append({"parameter": c.name, "low": vals[0], "high": vals[1], "swing": abs(vals[1] - vals[0])})
    torn.sort(key=lambda x: -x["swing"])
    avoided = cum_b[:, -1] - cum_p[:, -1]
    return {
        "unit": "documented land conflicts", "years": years.tolist(),
        "baseline": {"cumulative_conflicts": _pct(cum_b)}, "scenario": {"cumulative_conflicts": _pct(cum_p)},
        "impact": {"conflicts_avoided": _pct(avoided), "people_spared_median_estimate": float(np.median(avoided) * people),
                   "added_project_delay_months": _pct(delay), "compensation_cost_index": p["compensation_multiplier"] / 2.0},
        "context": {"baseline_conflicts_per_year": base["per_year"], "median_people_per_conflict": people,
                    "documented_cases_in_scope": base["total"], "sectors": ACQ_SECTORS},
        "coefficients": coefs, "tornado": torn,
        "headline": f"Over {len(years)} years, a median {np.median(avoided):,.1f} fewer documented conflicts "
                    f"(P10-P90 {np.percentile(avoided, 10):,.1f}-{np.percentile(avoided, 90):,.1f}), at the cost of "
                    f"~{np.median(delay):.0f} months added project delay.",
    }


# =========================================================================== lever 3: revenue-court pendency

def sim_pendency(p: dict, rng, n: int) -> dict:
    coefs = {
        "disposal_speedup": Coef("reduction in average disposal time from RCCMS computerisation",
                                 0.2 * p["rccms_coverage"], 0.4 * p["rccms_coverage"], "C",
                                 "Expert assumption; calibrate with state RCCMS disposal data", "fraction"),
        "filing_reduction": Coef("fewer new filings from ULPIN-linked clear titles", 0.0, 0.10 * p["ulpin_coverage"], "C",
                                 "Expert assumption: fewer boundary/identity disputes where parcels have a ULPIN",
                                 "fraction"),
        "filing_noise": Coef("filing volume uncertainty", 0.9, 1.1, "C", "+/-10% on the user-supplied baseline",
                             "multiplier"),
    }
    coefs = _override(coefs, p)
    years = np.arange(2026, p["to_year"] + 1)

    def run(d):
        F = p["filings_per_year"] * d["filing_noise"]
        T0 = p["years_to_resolve"]
        pend_b = (F * T0)[:, None].repeat(len(years), 1)  # steady state: P = F x T
        Fp, Tp = F * (1 - d["filing_reduction"]), T0 * (1 - d["disposal_speedup"])
        P, out = F * T0, []
        for _ in years:  # dynamic adjustment towards the new steady state
            P = P + Fp - P / Tp
            out.append(P)
        return pend_b, np.stack(out, axis=1)

    draws = {k: c.draw(rng, n) for k, c in coefs.items()}
    b, s = run(draws)
    torn = []
    for k, c in coefs.items():
        vals = []
        for v in (c.low, c.high):
            d = {kk: np.full(1, cc.mid) for kk, cc in coefs.items()}
            d[k] = np.full(1, v)
            bb, ss = run(d)
            vals.append(float(bb[0, -1] - ss[0, -1]))
        torn.append({"parameter": c.name, "low": vals[0], "high": vals[1], "swing": abs(vals[1] - vals[0])})
    torn.sort(key=lambda x: -x["swing"])
    red = (b[:, -1] - s[:, -1]) / b[:, -1] * 100
    return {
        "unit": "pending revenue-court cases", "years": years.tolist(),
        "baseline": {"pending_cases": _pct(b)}, "scenario": {"pending_cases": _pct(s)},
        "impact": {"pendency_reduction_pct": _pct(red)},
        "context": {"formula": "Pending cases = New filings per year x Average years to resolve (Little's law)",
                    "baseline_note": "Filings and disposal time are user inputs; load the pilot state's RCCMS figures."},
        "coefficients": coefs, "tornado": torn,
        "headline": f"Pendency falls a median {np.median(red):.0f}% by {years[-1]} (P10-P90 "
                    f"{np.percentile(red, 10):.0f}-{np.percentile(red, 90):.0f}%).",
    }


LEVERS = {
    "agri_conversion": {
        "name": "Agricultural land conversion control (zoning)",
        "question": "If conversion of farmland to built-up use is restricted, how much cropland is saved?",
        "fn": sim_agri_conversion, "model_id": "sim-agri-conversion-v1",
        "params": {"state": None, "districts": None, "strength": 0.5, "compliance": 0.7, "start_year": 2027, "to_year": 2035},
        "param_help": {"strength": "share of cropland conversion the rule blocks (0-1)",
                       "compliance": "share of the rule actually enforced (0-1)",
                       "start_year": "first year the rule applies", "state": "SOI state name, or omit for India",
                       "districts": "list of LGD district codes (overrides state)"}},
    "acquisition_reform": {
        "name": "Land-acquisition rules (consent, compensation, social impact assessment)",
        "question": "If acquisition needs prior consent and pays more, how many land conflicts are avoided, and at what delay?",
        "fn": sim_acquisition, "model_id": "sim-acquisition-reform-v1",
        "params": {"state": None, "consent_threshold": 70, "compensation_multiplier": 2.0, "sia": True, "to_year": 2035},
        "param_help": {"consent_threshold": "% of land owners whose consent is required (0 = none)",
                       "compensation_multiplier": "compensation as a multiple of market value (RFCTLARR baseline ~2x)",
                       "sia": "mandatory social impact assessment"}},
    "dispute_pendency": {
        "name": "Revenue-court computerisation and ULPIN coverage",
        "question": "If revenue courts are computerised and parcels get ULPINs, how much does pendency fall?",
        "fn": sim_pendency, "model_id": "sim-dispute-pendency-v1",
        "params": {"filings_per_year": 100000, "years_to_resolve": 2.5, "rccms_coverage": 1.0, "ulpin_coverage": 1.0,
                   "to_year": 2032},
        "param_help": {"filings_per_year": "new revenue-court cases per year (baseline, from state RCCMS)",
                       "years_to_resolve": "average time to dispose a case today",
                       "rccms_coverage": "share of courts computerised (0-1)", "ulpin_coverage": "share of parcels with ULPIN (0-1)"}},
}


def run(lever: str, params: dict, seed: int = 42, draws: int = 2000) -> dict:
    spec = LEVERS[lever]
    p = {**spec["params"], **{k: v for k, v in params.items() if v is not None}}
    rng = np.random.default_rng(seed)
    out = spec["fn"](p, rng, draws)
    out["coefficients"] = [{"key": k, "name": c.name, "low": c.low, "high": c.high, "grade": c.grade, "source": c.source,
                            "unit": c.unit} for k, c in out["coefficients"].items()]
    out.update({"lever": lever, "lever_name": spec["name"], "model_id": spec["model_id"], "params": p, "seed": seed,
                "draws": draws, "evidence_type": "SIMULATED",
                "disclaimer": "Scenario, not a forecast: shows what the listed assumptions imply. Override any "
                              "coefficient range after reviewing its source and grade."})
    out["hash"] = hashlib.sha256(json.dumps({"lever": lever, "params": p, "seed": seed, "draws": draws,
                                             "model": spec["model_id"]}, sort_keys=True, default=str).encode()).hexdigest()
    return out
