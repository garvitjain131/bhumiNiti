#!/usr/bin/env python3
"""
SYNTHETIC land records for the anonymisation / RBAC demo.

Real parcel geometry (Dhamtari district cadastral map, NCOG) + entirely FAKE owners. Every row carries
`is_synthetic = true`; identifiers use obviously non-real formats (SYN-...), so nothing here can be
mistaken for, or matched to, a real citizen.

    python etl/build_synthetic.py        -> data/synthetic/dhamtari_land_records.parquet
"""
from __future__ import annotations

from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data/cadastral/chhattisgarh/NCOG_CG_Dhamtari_Cadastrals.parquet"
OUT = ROOT / "data/synthetic/dhamtari_land_records.parquet"
SEED = 20260928

FIRST_M = ["Ramesh", "Suresh", "Mahesh", "Dinesh", "Rajesh", "Mukesh", "Santosh", "Ashok", "Anil", "Sunil",
           "Vijay", "Manoj", "Rakesh", "Devendra", "Govind", "Bhagwat", "Ramlal", "Shyamlal", "Tularam", "Kunjbihari"]
FIRST_F = ["Sunita", "Geeta", "Savitri", "Kamla", "Rekha", "Sarita", "Lata", "Meena", "Pushpa", "Radha",
           "Sushila", "Janki", "Parvati", "Anita", "Kiran"]
LAST = ["Sahu", "Verma", "Yadav", "Netam", "Markam", "Dhruw", "Sinha", "Sharma", "Patel", "Nishad",
        "Kaushik", "Thakur", "Mandavi", "Sonkar", "Chandrakar", "Dewangan", "Tandon", "Banjare"]
BANKS = ["SBI", "Chhattisgarh Rajya Gramin Bank", "Bank of Baroda", "District Cooperative Central Bank", "Canara Bank"]


def main() -> None:
    rng = np.random.default_rng(SEED)
    con = duckdb.connect()
    con.execute("LOAD spatial")
    p = con.execute(f"""
        SELECT gid, vname AS village, tname AS tehsil, TRY_CAST(area_ha AS DOUBLE) AS area_ha,
               ST_X(ST_Centroid(geometry)) AS lon, ST_Y(ST_Centroid(geometry)) AS lat
        FROM read_parquet('{SRC.as_posix()}')""").fetchdf()
    n = len(p)
    female = rng.random(n) < 0.14          # women's land ownership is low; order of magnitude only
    first = np.where(female, rng.choice(FIRST_F, n), rng.choice(FIRST_M, n))
    last = rng.choice(LAST, n)
    father = rng.choice(FIRST_M, n)
    age = np.clip(rng.normal(48, 13, n).round(), 19, 92).astype(int)
    area = p["area_ha"].fillna(p["area_ha"].median()).clip(lower=0.001)
    irrigated = rng.random(n) < 0.55
    mortgaged = rng.random(n) < 0.18
    rec = pd.DataFrame({
        "record_id": [f"SYN-ROR-{i:07d}" for i in range(n)],
        "ulpin": [f"SYN{rng.integers(10**10, 10**11)}" for _ in range(n)],
        "parcel_gid": p["gid"].astype(str),
        "state": "Chhattisgarh", "district": "Dhamtari", "tehsil": p["tehsil"], "village": p["village"],
        "khasra_no": [f"{rng.integers(1, 900)}/{rng.integers(1, 12)}" for _ in range(n)],
        "area_ha": area.round(4),
        "land_class": np.where(irrigated, "Irrigated agricultural", rng.choice(
            ["Unirrigated agricultural", "Abadi (habitation)", "Grazing/common", "Fallow"], n, p=[.7, .12, .1, .08])),
        "owner_name": [f"{a} {b}" for a, b in zip(first, last)],
        "father_or_spouse": [f"{a} {b}" for a, b in zip(father, last)],
        "owner_gender": np.where(female, "F", "M"),
        "owner_age": age,
        "social_category": rng.choice(["General", "OBC", "SC", "ST"], n, p=[.18, .47, .12, .23]),
        "citizen_id": [f"SYN-{rng.integers(1000, 9999)}-{rng.integers(1000, 9999)}" for _ in range(n)],
        "phone": [f"SYN-PH-{rng.integers(10**6, 10**7)}" for _ in range(n)],
        "co_owners": rng.choice([0, 1, 2, 3], n, p=[.55, .25, .14, .06]),
        "mortgage_bank": np.where(mortgaged, rng.choice(BANKS, n), None),
        "mutation_pending": rng.random(n) < 0.06,
        "dispute_pending": rng.random(n) < 0.035,
        "last_transfer_year": rng.integers(1985, 2026, n),
        "circle_rate_lakh_per_ha": np.round(rng.lognormal(np.log(np.where(irrigated, 14, 9)), 0.35), 2),
        "lon": p["lon"].round(6), "lat": p["lat"].round(6),
        "is_synthetic": True,
    })
    OUT.parent.mkdir(parents=True, exist_ok=True)
    rec.to_parquet(OUT, index=False)
    print(f"{n:,} SYNTHETIC records -> {OUT} ({OUT.stat().st_size / 1e6:.1f} MB); "
          f"{rec.village.nunique()} villages, {female.mean():.0%} female owners")


if __name__ == "__main__":
    main()
