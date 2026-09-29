"""
Anonymisation of parcel-level land records.

Views by role:
  identified  (admin only, every access audited)          all fields
  masked      (officials; researchers with approved access) names/IDs partially masked, per-record browsing
  anonymised  (bulk export for researchers)                direct identifiers removed, stable pseudonym per owner,
                                                            quasi-identifiers generalised to k-anonymity (k >= 5)
  aggregate   (any signed-in user)                         village-level counts, cells < 5 suppressed
"""
from __future__ import annotations

import hashlib
import hmac

import pandas as pd

from ..core.config import SECRET

K = 5                     # k-anonymity threshold for bulk exports
SMALL_CELL = 5            # aggregates with fewer records are suppressed
DIRECT_IDENTIFIERS = ["record_id", "ulpin", "owner_name", "father_or_spouse", "citizen_id", "phone",
                      "khasra_no", "lon", "lat", "parcel_gid"]
QUASI_IDENTIFIERS = ["village", "owner_gender", "age_band", "social_category"]
SUPPRESSION_ORDER = ["social_category", "age_band", "owner_gender"]   # generalise these first when a group is < k

POLICY = {
    "k_anonymity": K, "small_cell_suppression": SMALL_CELL,
    "removed_fields": DIRECT_IDENTIFIERS,
    "pseudonymised": "owner -> HMAC-SHA256(platform secret, name|father/spouse|village), 12 hex chars; stable across "
                     "exports so researchers can link records, but not reversible without the secret",
    "generalised": {"owner_age": "10-15 year bands", "area_ha": "rounded to 0.05 ha",
                    "circle_rate_lakh_per_ha": "rounded to 1 lakh", "coordinates": "dropped (village kept)"},
    "quasi_identifiers": QUASI_IDENTIFIERS,
}


def pseudonym(*parts: str) -> str:
    return hmac.new(SECRET.encode(), "|".join(parts).encode(), hashlib.sha256).hexdigest()[:12]


def _mask_name(s: str) -> str:
    return " ".join(w[0] + "*" * (len(w) - 1) for w in str(s).split())


def mask(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["owner_name"] = out["owner_name"].map(_mask_name)
    out["father_or_spouse"] = out["father_or_spouse"].map(_mask_name)
    out["citizen_id"] = out["citizen_id"].str.replace(r"^(SYN)-\d{4}", r"\1-****", regex=True)
    out["phone"] = "hidden"
    return out


def age_band(a: int) -> str:
    return "18-29" if a < 30 else "30-44" if a < 45 else "45-59" if a < 60 else "60+"


def anonymise(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Bulk export: drop identifiers, pseudonymise owners, generalise, then enforce k-anonymity."""
    out = df.copy()
    out["village"] = out["village"].fillna("(unnamed)")
    out.insert(0, "owner_pseudonym", [pseudonym(str(a), str(b), str(c)) for a, b, c in
                                      zip(out["owner_name"], out["father_or_spouse"], out["village"])])
    out["age_band"] = out["owner_age"].map(age_band)
    out["area_ha"] = (out["area_ha"] / 0.05).round() * 0.05
    out["circle_rate_lakh_per_ha"] = out["circle_rate_lakh_per_ha"].round()
    out = out.drop(columns=[c for c in DIRECT_IDENTIFIERS + ["owner_age"] if c in out.columns])
    generalised = {c: 0 for c in SUPPRESSION_ORDER}
    for col in SUPPRESSION_ORDER:          # progressively generalise quasi-identifiers in small groups
        size = out.groupby(QUASI_IDENTIFIERS, dropna=False)["owner_pseudonym"].transform("size")
        small = size < K
        generalised[col] = int(small.sum())
        out.loc[small, col] = "*"
    size = out.groupby(QUASI_IDENTIFIERS, dropna=False)["owner_pseudonym"].transform("size")
    dropped = int((size < K).sum())        # still unique on village alone -> drop the row
    out = out[size >= K]
    report = {"rows_in": len(df), "rows_out": len(out), "rows_dropped_for_k": dropped,
              "cells_generalised": generalised, "k": K,
              "min_group_size": int(out.groupby(QUASI_IDENTIFIERS)["owner_pseudonym"].size().min()) if len(out) else 0}
    return out, report


def aggregate(df: pd.DataFrame, by: str) -> list[dict]:
    df = df.assign(**{by: df[by].fillna("(unnamed)")})
    g = df.groupby(by).agg(parcels=("record_id", "size"), area_ha=("area_ha", "sum"),
                           female_owner_share=("owner_gender", lambda s: (s == "F").mean()),
                           mortgaged_share=("mortgage_bank", lambda s: s.notna().mean()),
                           mutation_pending=("mutation_pending", "sum"), dispute_pending=("dispute_pending", "sum"))
    g = g.reset_index()
    small = g["parcels"] < SMALL_CELL
    g.loc[small, ["area_ha", "female_owner_share", "mortgaged_share", "mutation_pending", "dispute_pending"]] = None
    g["suppressed"] = small
    for c in ("area_ha", "female_owner_share", "mortgaged_share"):
        g[c] = g[c].astype(float).round(3)
    # small cells in counts of pending cases: suppress values 1-4 as well
    for c in ("mutation_pending", "dispute_pending"):
        g[c] = g[c].map(lambda v: None if v is None or pd.isna(v) or 0 < v < SMALL_CELL else int(v))
    g = g.astype(object)
    return g.where(g.notna(), None).to_dict("records")
