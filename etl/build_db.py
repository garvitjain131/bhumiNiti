#!/usr/bin/env python3
"""
Build db/lpip.duckdb from the files fetched into data/.

Rebuilds from scratch every run (the database is derived data; data/ + manifest are the source
of truth). Requires: duckdb, pandas.  Run from the project root:

    python etl/build_db.py

Tables
  geo_state, geo_district     SOI boundaries (LGD codes) + Census-2011 crosswalk + simplified geometry
  indicator                   district x year x indicator, every row labelled OBSERVED / ESTIMATED
  dilrmp_state                DILRMP-MIS state progress (RoR, cadastral maps, ULPIN, SRO)
  evidence_item               13k+ papers / reports / documents, with land-relevance score + FTS index
  catalog                     one row per downloaded file: source, licence, hash (provenance)
"""
from __future__ import annotations

import csv
import json
import re
import sys
import time
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DB = ROOT / "db" / "lpip.duckdb"
SIMPLIFY_DISTRICT = 0.005   # degrees (~500 m): small enough for a web map
SIMPLIFY_STATE = 0.01

# --------------------------------------------------------------------------- helpers


def p(rel: str) -> str:
    return str((DATA / rel).as_posix())


def norm(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper().replace("&", "AND"))


def num(x) -> float | None:
    x = (x or "").replace(",", "").strip()
    try:
        return float(x)
    except ValueError:
        return None


def step(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# --------------------------------------------------------------------------- geography

def build_geo(con) -> None:
    step("geo_state / geo_district (Survey of India boundaries, LGD codes, Census-2011 crosswalk)")
    con.execute(f"""
        CREATE TABLE geo_state AS
        SELECT TRY_CAST(State_LGD AS INTEGER) AS state_lgd, STATE_C AS name, geometry AS geom,
               ST_SimplifyPreserveTopology(geometry, {SIMPLIFY_STATE}) AS geom_simple
        FROM read_parquet('{p("boundaries/states/SOI_States.parquet")}')
    """)
    # LGD_Districts carries the Census-2011 codes; one LGD district can span several polygons.
    con.execute(f"""
        CREATE TABLE geo_district AS
        WITH lgd AS (
            SELECT TRY_CAST(dist_lgd AS INTEGER) AS dist_lgd,
                   min(NULLIF(TRY_CAST(stcode11 AS INTEGER), 0)) AS pc11_state,
                   min(NULLIF(TRY_CAST(dtcode11 AS INTEGER), 0)) AS pc11_district
            FROM read_parquet('{p("boundaries/districts/LGD_Districts.parquet")}') GROUP BY 1
        ), soi AS (
            SELECT TRY_CAST(DISTRICT_L AS INTEGER) AS district_lgd, TRY_CAST(State_LGD AS INTEGER) AS state_lgd,
                   District_C AS name, STATE_C AS state_name, TRY_CAST(Shape_Area AS DOUBLE) / 1e6 AS area_km2, geometry
            FROM read_parquet('{p("boundaries/districts/SOI_Districts.parquet")}')
        )
        SELECT s.district_lgd, s.state_lgd, s.name, s.state_name, l.pc11_state, l.pc11_district,
               (s.district_lgd IS NULL OR s.state_name LIKE 'DISPUTED%') AS is_disputed,
               s.area_km2,   -- SOI Shape_Area (m2) / 1e6; ST_Area_Spheroid expects lat/lon axis order
               s.geometry AS geom,
               ST_SimplifyPreserveTopology(s.geometry, {SIMPLIFY_DISTRICT}) AS geom_simple
        FROM soi s LEFT JOIN lgd l ON l.dist_lgd = s.district_lgd
    """)
    n, dis = con.execute("SELECT count(*), count(*) FILTER (WHERE is_disputed) FROM geo_district").fetchone()
    step(f"  {n - dis} districts + {dis} disputed-area polygons (flagged, excluded from analysis)")


# --------------------------------------------------------------------------- indicators

# Human-readable names/units for the indicators the UI shows first. Everything else stays queryable
# under its raw SHRUG name.
KEY_INDICATORS = {
    "pc11_pca_tot_p": ("Population, Census 2011", "persons"),
    "pc11_pca_no_hh": ("Households, Census 2011", "households"),
    "pc11_pca_p_sc": ("Scheduled Caste population", "persons"),
    "pc11_pca_p_st": ("Scheduled Tribe population", "persons"),
    "pc11_pca_p_lit": ("Literate population", "persons"),
    "pc11_vd_area": ("Village area (Census village directory)", "ha"),
    "pc11_vd_land_fores": ("Forest land", "ha"),
    "pc11_vd_land_non_agri": ("Area not available for cultivation (non-agricultural use)", "ha"),
    "pc11_vd_land_uncult": ("Barren and uncultivable land", "ha"),
    "pc11_vd_land_pst_grz": ("Permanent pastures and grazing land", "ha"),
    "pc11_vd_land_misc_trcp": ("Miscellaneous tree crops and groves", "ha"),
    "pc11_vd_land_cult_waste": ("Culturable waste land", "ha"),
    "pc11_vd_land_fallow": ("Fallow land (other than current fallow)", "ha"),
    "pc11_vd_land_cur_fal": ("Current fallow", "ha"),
    "pc11_vd_land_nt_swn": ("Net area sown", "ha"),
    "pc11_vd_land_un_irr": ("Unirrigated land", "ha"),
    "land_own_share": ("Rural households owning land (SECC)", "share"),
    "viirs_annual_mean": ("Night-light radiance, annual mean", "nW/cm2/sr"),
    "vcf_mean": ("Tree cover (vegetation continuous fields), mean", "percent"),
    "pm25_mean": ("PM2.5, annual mean", "ug/m3"),
    "elevation_mean": ("Mean elevation", "m"),
}

# (file stem, year or None if the file has a year column, label, source note)
SHRUG_CROSS = [
    ("pc11_pca_clean_pc11dist", 2011, "OBSERVED", "Census 2011 Primary Census Abstract"),
    ("pc11_vd_clean_pc11dist", 2011, "OBSERVED", "Census 2011 Village Directory (aggregated to district)"),
    ("pc11_td_clean_pc11dist", 2011, "OBSERVED", "Census 2011 Town Directory (aggregated to district)"),
    ("ec13_pc11dist", 2013, "OBSERVED", "Economic Census 2013"),
    ("secc_rural_pc11dist", 2012, "OBSERVED", "SECC 2011-12 rural"),
    ("secc_urban_pc11dist", 2012, "OBSERVED", "SECC 2011-12 urban"),
    ("elevation_pc11dist", 0, "ESTIMATED", "Elevation (satellite-derived)"),
]
SHRUG_SERIES = [
    ("viirs_annual_pc11dist", "ESTIMATED", "Night lights (VIIRS/DMSP)"),
    ("vcf_pc11dist", "ESTIMATED", "Tree cover (MODIS VCF)"),
    ("pm25_pc11dist", "ESTIMATED", "PM2.5 (satellite-derived)"),
]


def _key_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns=str.strip)
    df["pc11_state"] = pd.to_numeric(df["pc11_state_id"], errors="coerce")
    df["pc11_district"] = pd.to_numeric(df["pc11_district_id"], errors="coerce")
    return df.dropna(subset=["pc11_state", "pc11_district"])


def build_indicators(con) -> None:
    step("indicator (SHRUG district tables, long format, labelled OBSERVED / ESTIMATED)")
    parts = []
    for stem, year, label, src in SHRUG_CROSS:
        f = DATA / "shrug" / f"{stem}.csv"
        if not f.exists():
            step(f"  missing {f.name}, skipped")
            continue
        df = _key_cols(pd.read_csv(f, dtype=str))
        value_cols = [c for c in df.columns if c not in ("pc11_state_id", "pc11_district_id", "pc11_state", "pc11_district")]
        long = df.melt(id_vars=["pc11_state", "pc11_district"], value_vars=value_cols,
                       var_name="indicator", value_name="value")
        long["value"] = pd.to_numeric(long["value"], errors="coerce")
        long = long.dropna(subset=["value"])
        long["year"], long["label"], long["source"] = year, label, src
        parts.append(long)
    for stem, label, src in SHRUG_SERIES:
        f = DATA / "shrug" / f"{stem}.csv"
        if not f.exists():
            continue
        df = _key_cols(pd.read_csv(f))
        if "category" in df.columns:  # keep only one satellite product per file
            df = df[df["category"] == df["category"].iloc[0]]
        metric_cols = [c for c in df.columns if c.endswith(("_mean", "_sum")) and "num_cells" not in c]
        long = df.melt(id_vars=["pc11_state", "pc11_district", "year"], value_vars=metric_cols,
                       var_name="indicator", value_name="value").dropna(subset=["value"])
        long["label"], long["source"] = label, src
        parts.append(long)
    ind = pd.concat(parts, ignore_index=True)
    ind["pc11_state"], ind["pc11_district"] = ind["pc11_state"].astype(int), ind["pc11_district"].astype(int)
    ind["year"] = ind["year"].astype(int)
    con.register("ind_raw", ind)
    con.execute("""
        CREATE TABLE indicator AS
        SELECT g.district_lgd, i.indicator, i.year, i.value, i.label, i.source
        FROM ind_raw i JOIN geo_district g ON g.pc11_district = i.pc11_district AND NOT g.is_disputed
    """)
    con.execute("CREATE TABLE indicator_meta(indicator VARCHAR, name VARCHAR, unit VARCHAR)")
    con.executemany("INSERT INTO indicator_meta VALUES (?, ?, ?)", [(k, v[0], v[1]) for k, v in KEY_INDICATORS.items()])
    n, d, k = con.execute("SELECT count(*), count(DISTINCT district_lgd), count(DISTINCT indicator) FROM indicator").fetchone()
    dropped = len(ind) - n
    total = con.execute("SELECT count(*) FROM geo_district WHERE NOT is_disputed").fetchone()[0]
    step(f"  {n:,} observations, {k} indicators, {dropped:,} rows dropped (SHRUG districts missing from the crosswalk)")
    step(f"  Census-era indicators cover {d} of {total} current districts; the other {total - d} were created after "
         f"2011 and have none yet (fix later: inherit from parent via the district-splits table, labelled as such)")


# --------------------------------------------------------------------------- satellite panel (Earth Engine)

# file stem -> (indicator prefix, label, human name, unit). Earth Engine writes one CSV per task with the
# district properties (incl. DISTRICT_L = LGD code) plus the reducer output columns and a `year` column.
SATELLITE = {
    "dw_landcover_share":    ("dw_",     "ESTIMATED", "Dynamic World land-cover share: {c}", "share of district"),
    "modis_landcover_share": ("modis_",  "ESTIMATED", "MODIS land-cover share: {c}", "share of district"),
    "ghsl_builtup_km2":      ("ghsl_",   "ESTIMATED", "GHSL built-up surface: {c}", "km2"),
    "viirs_nightlights":     ("viirs_",  "ESTIMATED", "VIIRS night lights: {c}", "nW/cm2/sr"),
    "chirps_rainfall":       ("chirps_", "ESTIMATED", "CHIRPS rainfall: {c}", "mm/year"),
}
RENAME = {"ghsl_sum": "ghsl_built_km2", "chirps_mean": "chirps_rain_mm",
          "viirs_mean": "viirs_ntl_mean", "viirs_sum": "viirs_ntl_sum"}
EE_META = {"system:index", ".geo", "District", "STATE", "REMARKS", "State_LGD", "DISTRICT_L", "Shape_Leng",
           "Shape_Area", "STATE_C", "District_C", "year"}


def build_satellite(con, folder: Path | None = None) -> None:
    folder = folder or DATA / "temporal"
    files = {f.stem: f for f in folder.glob("*.csv")} if folder.exists() else {}
    if not files:
        step("satellite panel: no CSVs in data/temporal yet (Earth Engine exports); skipped")
        return
    step("satellite panel (Earth Engine district x year exports)")
    for stem, (prefix, label, name_fmt, unit) in SATELLITE.items():
        f = files.get(stem)
        if f is None:
            step(f"  {stem}: not found, skipped")
            continue
        df = pd.read_csv(f)
        if "DISTRICT_L" not in df.columns or "year" not in df.columns:
            step(f"  {stem}: expected DISTRICT_L and year columns, found {list(df.columns)[:8]}; skipped")
            continue
        df["district_lgd"] = pd.to_numeric(df["DISTRICT_L"], errors="coerce")
        cols = [c for c in df.columns if c not in EE_META and c != "district_lgd"
                and pd.api.types.is_numeric_dtype(df[c])]
        long = df.melt(id_vars=["district_lgd", "year"], value_vars=cols, var_name="band", value_name="value")
        long = long.dropna(subset=["district_lgd", "value"])
        long["district_lgd"], long["year"] = long["district_lgd"].astype(int), long["year"].astype(int)
        long["indicator"] = (prefix + long["band"].astype(str)).replace(RENAME)
        long["label"] = label
        if stem == "ghsl_builtup_km2":  # GHSL epochs after 2020 are model projections, not observations
            long.loc[long["year"] > 2020, "label"] = "PREDICTED"
        long["source"] = f"Earth Engine: {stem}"
        con.register("sat_df", long[["district_lgd", "indicator", "year", "value", "label", "source"]])
        before = con.execute("SELECT count(*) FROM indicator").fetchone()[0]
        con.execute("INSERT INTO indicator SELECT * FROM sat_df WHERE district_lgd IN "
                    "(SELECT district_lgd FROM geo_district WHERE NOT is_disputed)")
        added = con.execute("SELECT count(*) FROM indicator").fetchone()[0] - before
        con.executemany("INSERT INTO indicator_meta VALUES (?, ?, ?)",
                        [(RENAME.get(prefix + c, prefix + c), name_fmt.format(c=c), unit) for c in cols])
        d = con.execute("SELECT count(DISTINCT district_lgd) FROM sat_df WHERE district_lgd IN "
                        "(SELECT district_lgd FROM geo_district)").fetchone()[0]
        step(f"  {stem}: {added:,} observations loaded, {d} districts, {len(cols)} indicators, "
             f"years {long['year'].min()}-{long['year'].max()}; {len(long) - added:,} rows skipped (not a current district)")

# --------------------------------------------------------------------------- DILRMP

# Column positions (0-based) in the DILRMP-MIS tables, verified against each report's Grand Total row.
DILRMP_MAP = {"districts": 2, "tehsils": 3, "cadastral_maps": 4, "maps_digitised_pct": 8,
              "land_parcels": 28, "georef_pct": 30, "ulpin_assigned": 31, "ulpin_pct": 32}
DILRMP_CLR = {"ror_total": 5, "ror_computerised": 6, "ror_pct": 7, "villages_clr_done_pct": 11}
DILRMP_SRO = {"sro_total": 3, "sro_online": 4}


def _dilrmp_rows(name: str, cols: dict[str, int]) -> dict[str, dict]:
    path = DATA / "land_records" / f"dilrmp_{name}_state_0.csv"
    out: dict[str, dict] = {}
    for row in csv.reader(open(path, encoding="utf-8")):
        if len(row) < 8 or not row[1].strip():
            continue
        label = row[1].strip()
        if label != "Grand Total" and (not row[0].strip().isdigit() or label.isdigit()):
            continue  # skip header / column-number rows
        out[label] = {k: num(row[i]) if i < len(row) else None for k, i in cols.items()}
    return out


def build_dilrmp(con) -> None:
    step("dilrmp_state (DILRMP-MIS physical progress, state level)")
    maps, clr, sro = _dilrmp_rows("map", DILRMP_MAP), _dilrmp_rows("clr", DILRMP_CLR), _dilrmp_rows("sro", DILRMP_SRO)
    # sanity: the report's own grand totals must match what the site headlines
    gt = maps.get("Grand Total", {})
    step(f"  check Grand Total: maps digitised {gt.get('maps_digitised_pct')}% (expect 97.45), "
         f"ULPIN {gt.get('ulpin_pct')}% (expect 69.32), RoR {clr.get('Grand Total', {}).get('ror_pct')}% (expect 99.90)")
    states = {norm(r[0]): r[0] for r in con.execute("SELECT name FROM geo_state").fetchall()}
    alias = {"ANDAMANANDNICOBARISLANDS": "ANDAMANANDNICOBAR"}
    rows, unmatched = [], []
    for label in maps:
        if label == "Grand Total":
            continue
        n = norm(label)
        soi = states.get(n) or states.get(alias.get(n, ""))
        if not soi:
            unmatched.append(label)
        rows.append((label.title(), soi, *(maps[label][k] for k in DILRMP_MAP),
                     *(clr.get(label, {}).get(k) for k in DILRMP_CLR), *(sro.get(label, {}).get(k) for k in DILRMP_SRO)))
    cols = ["dilrmp_name", "soi_state_name", *DILRMP_MAP, *DILRMP_CLR, *DILRMP_SRO]
    df = pd.DataFrame(rows, columns=cols)
    con.register("dilrmp_df", df)
    con.execute("CREATE TABLE dilrmp_state AS SELECT * FROM dilrmp_df")
    step(f"  {len(df)} states/UTs; unmatched to SOI names: {unmatched or 'none'}")


# --------------------------------------------------------------------------- evidence

LAND_TERMS = re.compile(
    r"\b(land|lands|tenure|cadastr\w*|parcel\w*|property|titl(e|ing|es)|acquisition|eviction|resettlement|"
    r"agricultur\w*|watershed|peri-?urban|urban\w*|forest\w*|farm\w*|revenue|mutation|registration|"
    r"ulpin|dilrmp|svamitva|abadi|zoning|slum|commons?|tenan\w*|lease\w*|pastoral\w*|wasteland)\b", re.I)
CORE = re.compile(r"\bland\b|\bcadastr\w*|\btenure\b|\bproperty (rights?|records?)\b", re.I)


def land_score(title: str, abstract: str) -> int:
    t, a = title or "", abstract or ""
    score = 3 * len({m.group(0).lower() for m in LAND_TERMS.finditer(t)}) + len({m.group(0).lower() for m in LAND_TERMS.finditer(a)})
    return score + (3 if CORE.search(t) else 0) + (1 if CORE.search(a) else 0)


LEGAL = re.compile(r"\b(Act|Acts|Rules|Ordinance|Bill|Regulations?|Amendment)\b|in Lok Sabha|RFCTLARR|"
                   r"Removal of Difficulties", re.I)
GUIDE = re.compile(r"\b(Guidelines?|Circular|Advisory|Operational|Framework|Manual|SOP)\b", re.I)
STATE_TITLES = ["Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa", "Gujarat", "Haryana",
                "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur",
                "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu",
                "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal", "Jammu and Kashmir", "Ladakh",
                "Delhi", "Puducherry"]


def type_group(t: str | None) -> str:
    """Collapse ~100 raw document types (World Bank labels etc.) into repository categories."""
    t = (t or "").lower()
    if t in ("legal_document",):
        return "Legal document"
    if t == "case_study":
        return "Case study"
    if t in ("guideline",):
        return "Guideline"
    if t in ("dataset", "data-paper"):
        return "Dataset"
    if t in ("government_document", "government_report", "annual report"):
        return "Government document"
    if re.search(r"agreement|letter|procurement|disbursement|tranche|minutes|agenda|audit|financial|board|"
                 r"memorandum|safeguard|datasheet|data sheet|notice|transcript", t):
        return "Project administration"
    if re.search(r"plan|framework|assessment|appraisal|implementation|completion|project|program|inspection|"
                 r"evaluation|ieg|review summary", t):
        return "Project document"
    if re.search(r"research_paper|article|book|chapter|conference|thesis|dissertation|review|preprint|"
                 r"reference|editorial|paratext|peer|erratum|retraction|software|supplementary", t):
        return "Research publication"
    return "Policy report"


def _manifest() -> list[dict]:
    f = DATA / "manifest.jsonl"
    recs = {}
    for line in open(f, encoding="utf-8") if f.exists() else []:
        r = json.loads(line)
        recs[r["path"]] = r  # latest record per path
    return list(recs.values())


def _extra_documents(manifest: list[dict]) -> list[dict]:
    """Downloaded national reports that are not in any harvested index (Wastelands Atlas, DST assessment)."""
    out = []
    for r in manifest:
        if r["job"] not in ("reports", "wasteland_atlas") or not r["path"].endswith(".pdf"):
            continue
        title = r.get("title") or Path(r["path"]).stem
        org = "Department of Land Resources & NRSC" if r["job"] == "wasteland_atlas" else "Department of Science & Technology"
        out.append({"evidence_id": "doc:" + r["sha256"][:12], "source": r["job"], "type": "government_report",
                    "title": title, "abstract": f"{title}. Official national report ({org}).",
                    "source_organization": org, "publication_date": "2019-01-01" if r["job"] == "wasteland_atlas" else None,
                    "geography": {"states_mentioned": [s for s in STATE_TITLES if s.lower() in title.lower()]},
                    "policy_domain": ["wasteland_degradation"] if r["job"] == "wasteland_atlas" else ["climate_land"],
                    "citation": {"url": r["url"]}, "pdf_url": r["url"], "license": r.get("license"),
                    "quality_status": "official", "_path": r["path"]})
    return out


def _doc_files(manifest: list[dict], ids: set[str]) -> list[tuple[str, str]]:
    """evidence_id -> local PDF path, from provenance notes (papers, World Bank) or file-name suffix (DoLR)."""
    pairs, dolr_suffix = [], {}
    for r in manifest:
        p = r["path"]
        if not p.endswith(".pdf"):
            continue
        note = (r.get("notes") or "").strip()
        if note in ids:
            pairs.append((note, p))
        elif p.startswith("policy/dolr_pdfs/"):
            dolr_suffix[Path(p).stem[-6:]] = p
    for eid in ids:
        if eid.startswith("dolr:") and eid[-6:] in dolr_suffix:
            pairs.append((eid, dolr_suffix[eid[-6:]]))
    return pairs


def build_evidence(con) -> None:
    step("evidence_item (papers, reports, legal & government documents, case studies) + full-text index")
    manifest = _manifest()
    extra = _extra_documents(manifest)
    seen, rows = set(), []
    lines = (json.loads(line) for line in open(DATA / "evidence_items.jsonl", encoding="utf-8"))
    for e in [*lines, *extra]:
        if e["evidence_id"] in seen:
            continue
        seen.add(e["evidence_id"])
        if e["source"] == "dolr":  # classify government documents by title
            t = e.get("title") or ""
            e["type"] = "legal_document" if LEGAL.search(t) else "guideline" if GUIDE.search(t) else "government_document"
        cit = e.get("citation") or {}
        date = (e.get("publication_date") or "")[:10] or None
        year = int(date[:4]) if date and date[:4].isdigit() else None
        title, abstract = (e.get("title") or "").strip(), (e.get("abstract") or "").strip()
        rows.append({
            "evidence_id": e["evidence_id"], "source": e["source"], "type": e.get("type"), "title": title,
            "abstract": abstract, "source_org": e.get("source_organization"), "pub_date": date, "year": year,
            "states": (e.get("geography") or {}).get("states_mentioned") or [],
            "themes": e.get("policy_domain") or [], "authors": e.get("authors") or [],
            "doi": cit.get("doi"), "url": e.get("landing_url") or cit.get("url"), "pdf_url": e.get("pdf_url"),
            "license": e.get("license"), "cited_by": cit.get("cited_by"), "quality_status": e.get("quality_status"),
            "land_score": land_score(title, abstract), "type_group": type_group(e.get("type")),
        })
    df = pd.DataFrame(rows)
    df["pub_date"] = pd.to_datetime(df["pub_date"], errors="coerce").dt.date
    con.register("ev_df", df)
    con.execute("""
        CREATE TABLE evidence_item AS
        SELECT * REPLACE (CAST(authors AS VARCHAR[]) AS authors, CAST(states AS VARCHAR[]) AS states,
                          CAST(themes AS VARCHAR[]) AS themes) FROM ev_df
    """)
    con.execute("PRAGMA create_fts_index('evidence_item', 'evidence_id', 'title', 'abstract', "
                "stemmer='english', stopwords='english', overwrite=1)")
    extra_paths = [(e["evidence_id"], e["_path"]) for e in extra]
    con.execute("CREATE TABLE doc_file (evidence_id VARCHAR PRIMARY KEY, path VARCHAR)")
    pairs = dict(_doc_files(manifest, seen) + extra_paths)
    con.executemany("INSERT INTO doc_file VALUES (?, ?)", [(k, v) for k, v in pairs.items() if (DATA / v).exists()])
    n, hi = con.execute("SELECT count(*), count(*) FILTER (WHERE land_score >= 4) FROM evidence_item").fetchone()
    types = dict(con.execute("SELECT type_group, count(*) FROM evidence_item GROUP BY 1 ORDER BY 2 DESC").fetchall())
    files = con.execute("SELECT count(*) FROM doc_file").fetchone()[0]
    step(f"  {n:,} items; {hi:,} clearly land-relevant (land_score >= 4); {files} with a local PDF")
    step(f"  types: {types}")


def build_land_records(con) -> None:
    f = DATA / "synthetic" / "dhamtari_land_records.parquet"
    if not f.exists():
        step("land_record: synthetic records not built (python etl/build_synthetic.py); skipped")
        return
    con.execute(f"CREATE TABLE land_record AS SELECT * FROM read_parquet('{f.as_posix()}')")
    step(f"  land_record: {con.execute('SELECT count(*) FROM land_record').fetchone()[0]:,} SYNTHETIC parcel records "
         f"(restricted dataset)")


STATE_ALIAS = {"ORISSA": "ODISHA", "PONDICHERRY": "PUDUCHERRY", "UTTARANCHAL": "UTTARAKHAND",
               "ANDAMANANDNICOBARISLANDS": "ANDAMANANDNICOBAR", "DADRAANDNAGARHAVELI": "DADRAANDNAGARHAVELIANDDAMANANDDIU",
               "DAMANANDDIU": "DADRAANDNAGARHAVELIANDDAMANANDDIU", "NCTOFDELHI": "DELHI"}


# renamed districts and names too different for fuzzy matching (normalised: A-Z0-9 only)
DISTRICT_ALIAS = {"KUTCH": "KACHCHH", "ALLAHABAD": "PRAYAGRAJ", "FAIZABAD": "AYODHYA", "MOHALI": "SASNAGAR",
                  "NUH": "MEWAT", "KANKER": "UTTARBASTARKANKER",
                  "DANTEWADA": "DAKSHINBASTARDANTEWADA", "AGARTALA": "WESTTRIPURA", "KAMRUP": "KAMRUPRURAL",
                  "BANGALORE": "BENGALURUURBAN", "BANGALOREURBAN": "BENGALURUURBAN", "BELGAUM": "BELAGAVI",
                  "BELLARY": "BALLARI", "GULBARGA": "KALABURAGI", "MYSORE": "MYSURU", "SHIMOGA": "SHIVAMOGGA",
                  "BIJAPUR": "VIJAYAPURA", "MUMBAISUBURBAN": "SUBURBANMUMBAI", "AURANGABAD": "AURANGABAD",
                  "NORTH24PARGANAS": "NORTHTWENTYFOURPARGANAS", "SOUTH24PARGANAS": "SOUTHTWENTYFOURPARGANAS",
                  "SERAIKELAKHARSAWAN": "SARAIKELAKHARSAWAN", "DARJEELING": "DARJILING",
                  "KUTCCH": "KACHCHH", "RAIGADH": "RAYGAD", "THOOTHUKUDI": "TUTICORIN", "NARSINGHPUR": "NARSHIMAPURA",
                  "NARMADAPURAM": "HOSHANGABAD", "KHARGONE": "WESTNIMAR", "KHANDWA": "EASTNIMAR"}


def build_disputes(con) -> None:
    """Land Conflict Watch conflicts -> land_conflict, matched to SOI districts by name within state."""
    f = DATA / "disputes" / "lcw_conflicts.csv"
    if not f.exists():
        step("land_conflict: data/disputes/lcw_conflicts.csv not found (run fetch.py --only land_conflicts); skipped")
        return
    step("land_conflict (Land Conflict Watch, matched to districts)")
    df = pd.read_csv(f, dtype=str).fillna("")
    for c in ("people_affected", "households_affected", "land_area_ha", "investment_crore", "year_started"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    states = {norm(n): n for (n,) in con.execute("SELECT name FROM geo_state").fetchall()}
    dists = con.execute("SELECT district_lgd, name, state_name FROM geo_district WHERE NOT is_disputed").fetchall()
    import difflib
    by_state: dict[str, dict[str, int]] = {}
    for lgd, name, st in dists:
        for variant in [name, *re.findall(r"\(([^)]+)\)", name), re.sub(r"\(.*?\)", "", name)]:
            by_state.setdefault(st, {})[norm(variant)] = lgd  # SOI writes alternates as "BOLANGIR (BALANGIR)"

    def match(row) -> tuple:
        s = norm(row["state"])
        soi_state = states.get(s) or states.get(STATE_ALIAS.get(s, ""))
        if not soi_state:
            return None, None
        d = norm(row["district"])
        d = DISTRICT_ALIAS.get(d, d)
        table = by_state.get(soi_state, {})
        if not d:
            return soi_state, None
        if d in table:
            return soi_state, table[d]
        stripped = re.sub(r"(DELHI|DISTRICT|METROPOLITAN)$", lambda m: "METRO" if m.group(1) == "METROPOLITAN" else "", d)
        if stripped in table:
            return soi_state, table[stripped]
        contained = {v for k, v in table.items() if len(d) >= 5 and (d in k or k in d)}
        if len(contained) == 1:
            return soi_state, contained.pop()
        close = difflib.get_close_matches(d, table, n=1, cutoff=0.8)  # spelling variants: TUMKUR/TUMAKURU
        return soi_state, table[close[0]] if close else None

    m = df.apply(match, axis=1, result_type="expand")
    df["soi_state"], df["district_lgd"] = m[0], pd.to_numeric(m[1], errors="coerce").astype("Int64")
    df["ended"] = df["ended"].str.lower().map({"yes": True, "no": False})
    con.register("lcw_df", df)
    con.execute("CREATE TABLE land_conflict AS SELECT * FROM lcw_df")
    n, s_ok, d_ok, ppl, area = con.execute("""
        SELECT count(*), count(soi_state), count(district_lgd), sum(people_affected), sum(land_area_ha)
        FROM land_conflict""").fetchone()
    step(f"  {n:,} conflicts; {s_ok:,} matched to a state, {d_ok:,} to a district; "
         f"{(ppl or 0) / 1e6:.1f} M people and {(area or 0) / 1e6:.2f} M ha affected (as reported)")


def build_derived(con) -> None:
    """District map metrics: change over time, hazard exposure, conflicts, and a composite climate-risk index."""
    step("district_metric (change, hazard exposure, conflicts, climate-risk index)")
    con.execute("""CREATE TABLE district_metric (district_lgd INTEGER, metric VARCHAR, value DOUBLE,
                   label VARCHAR, PRIMARY KEY (district_lgd, metric))""")
    con.execute("""CREATE TABLE metric_meta (metric VARCHAR PRIMARY KEY, name VARCHAR, unit VARCHAR, theme VARCHAR,
                   higher_is VARCHAR, method VARCHAR)""")

    def add(metric, name, unit, theme, higher_is, method, sql, label="ESTIMATED"):
        con.execute(f"INSERT INTO district_metric SELECT district_lgd, '{metric}', v, '{label}' FROM ({sql}) "
                    "WHERE district_lgd IS NOT NULL AND v IS NOT NULL AND isfinite(v)")
        con.execute("INSERT INTO metric_meta VALUES (?,?,?,?,?,?)", [metric, name, unit, theme, higher_is, method])

    def val(ind, year):
        return f"max(value) FILTER (WHERE indicator = '{ind}' AND year = {year})"

    add("built_km2_2020", "Built-up area 2020", "km2", "Land use", "neutral", "GHSL built-up surface, sum per district",
        f"SELECT district_lgd, {val('ghsl_built_km2', 2020)} AS v FROM indicator GROUP BY 1")
    add("built_growth_2000_2020", "Built-up growth 2000-2020", "%", "Land use", "pressure",
        "GHSL built-up 2020 vs 2000", f"""SELECT district_lgd, 100 * ({val('ghsl_built_km2', 2020)} /
            nullif({val('ghsl_built_km2', 2000)}, 0) - 1) AS v FROM indicator GROUP BY 1""")
    add("crops_change_2017_2025", "Cropland share change 2017-2025", "percentage points", "Land use", "neutral",
        "Dynamic World annual modal class, 2025 minus 2017", f"""SELECT district_lgd, 100 * ({val('dw_crops', 2025)} -
            {val('dw_crops', 2017)}) AS v FROM indicator GROUP BY 1""")
    add("built_share_change_2017_2025", "Built-up share change 2017-2025", "percentage points", "Land use",
        "pressure", "Dynamic World, 2025 minus 2017", f"""SELECT district_lgd, 100 * ({val('dw_built', 2025)} -
            {val('dw_built', 2017)}) AS v FROM indicator GROUP BY 1""")
    add("cropland_change_2001_2023", "Cropland share change 2001-2023", "percentage points", "Land use", "neutral",
        "MODIS IGBP cropland class, 2023 minus 2001", f"""SELECT district_lgd, 100 * ({val('modis_cropland', 2023)} -
            {val('modis_cropland', 2001)}) AS v FROM indicator GROUP BY 1""")
    add("ntl_2025", "Night-light radiance 2025", "nW/cm2/sr", "Infrastructure", "neutral",
        "VIIRS monthly composites, annual mean", f"SELECT district_lgd, {val('viirs_ntl_mean', 2025)} AS v FROM indicator GROUP BY 1")
    add("ntl_growth_2014_2025", "Night-light growth 2014-2025", "%", "Infrastructure", "good",
        "VIIRS annual mean radiance, 2025 vs 2014 (economic activity and electrification proxy)",
        f"""SELECT district_lgd, 100 * ({val('viirs_ntl_mean', 2025)} / nullif({val('viirs_ntl_mean', 2014)}, 0) - 1) AS v
            FROM indicator GROUP BY 1""")
    add("rain_mean", "Mean annual rainfall 2001-2025", "mm", "Climate", "neutral", "CHIRPS",
        "SELECT district_lgd, avg(value) AS v FROM indicator WHERE indicator = 'chirps_rain_mm' GROUP BY 1")
    add("rain_cv", "Rainfall variability 2001-2025", "coefficient of variation %", "Climate", "risk",
        "CHIRPS annual totals: standard deviation / mean",
        "SELECT district_lgd, 100 * stddev(value) / nullif(avg(value), 0) AS v FROM indicator "
        "WHERE indicator = 'chirps_rain_mm' GROUP BY 1")
    add("tree_cover", "Tree cover (latest)", "%", "Climate", "good", "MODIS VCF via SHRUG, latest year",
        "SELECT district_lgd, arg_max(value, year) AS v FROM indicator WHERE indicator = 'vcf_mean' GROUP BY 1")
    add("population_2011", "Population (Census 2011)", "persons", "Socio-economic", "neutral", "Census 2011 PCA",
        "SELECT district_lgd, max(value) AS v FROM indicator WHERE indicator = 'pc11_pca_tot_p' GROUP BY 1", "OBSERVED")

    # hazard exposure: point/area layers joined to district polygons
    hz = DATA / "hazards"
    ls = hz / "landslides" / "GSI_Landslide_Inventory.parquet"
    if ls.exists():
        add("landslides", "Recorded landslides (GSI inventory)", "count", "Climate", "risk",
            "GSI national landslide inventory points inside the district", f"""
            SELECT g.district_lgd, count(*)::DOUBLE AS v FROM read_parquet('{ls.as_posix()}') p
            JOIN geo_district g ON ST_Intersects(g.geom, p.geometry) GROUP BY 1""", "OBSERVED")
    eq = hz / "earthquakes" / "NGDR_Earthquakes.parquet"
    if eq.exists():
        add("earthquakes_m4", "Earthquakes M4+ recorded", "count", "Climate", "risk",
            "NGDR earthquake catalogue, magnitude >= 4, epicentre inside the district", f"""
            SELECT g.district_lgd, count(*)::DOUBLE AS v FROM read_parquet('{eq.as_posix()}') p
            JOIN geo_district g ON ST_Intersects(g.geom, p.geometry)
            WHERE greatest(TRY_CAST(p.magmb AS DOUBLE), TRY_CAST(p.mw AS DOUBLE)) >= 4 GROUP BY 1""", "OBSERVED")
    fl = hz / "floods" / "NDEM_All_India_Flood_Innundation_1998_to_2022.parquet"
    if fl.exists():
        add("flood_share", "Flood exposure 1998-2022", "index 0-100", "Climate", "risk",
            "NDEM flood-inundation polygons 1998-2022 assigned to districts by centroid; cumulative inundated area "
            "(overlapping years counted again) as % of district area, capped at 100", f"""
            SELECT g.district_lgd, least(100, 100 * sum(ST_Area_Spheroid(ST_FlipCoordinates(p.geometry))) / 1e6
                   / any_value(g.area_km2)) AS v
            FROM read_parquet('{fl.as_posix()}') p JOIN geo_district g ON ST_Contains(g.geom, ST_Centroid(p.geometry))
            GROUP BY 1""", "OBSERVED")
    # conflicts
    add("conflicts", "Documented land conflicts", "count", "Disputes", "risk", "Land Conflict Watch",
        "SELECT district_lgd, count(*)::DOUBLE AS v FROM land_conflict WHERE district_lgd IS NOT NULL GROUP BY 1",
        "OBSERVED")
    add("conflict_people", "People affected by land conflicts", "persons", "Disputes", "risk",
        "Land Conflict Watch, as reported", "SELECT district_lgd, sum(people_affected) AS v FROM land_conflict "
        "WHERE district_lgd IS NOT NULL GROUP BY 1", "OBSERVED")

    # composite climate-risk index: mean percentile rank of available risk components (0-100)
    con.execute("""
        INSERT INTO district_metric
        SELECT district_lgd, 'climate_risk_index', round(100 * avg(pr), 1), 'ESTIMATED' FROM (
            SELECT district_lgd, metric,
                   CASE WHEN metric = 'tree_cover' THEN 1 - percent_rank() OVER (PARTITION BY metric ORDER BY value)
                        ELSE percent_rank() OVER (PARTITION BY metric ORDER BY value) END AS pr
            FROM district_metric WHERE metric IN ('rain_cv', 'flood_share', 'landslides', 'tree_cover'))
        GROUP BY 1""")
    con.execute("INSERT INTO metric_meta VALUES ('climate_risk_index', 'Climate-risk index (composite)', '0-100', "
                "'Climate', 'risk', 'Mean percentile of rainfall variability, flood exposure, landslides and low tree "
                "cover; missing components are skipped. A screening index, not a vulnerability assessment.')")
    n = con.execute("SELECT count(DISTINCT metric), count(*) FROM district_metric").fetchone()
    step(f"  {n[0]} metrics, {n[1]:,} district values")


def build_catalog(con) -> None:
    step("catalog (provenance: source, licence, hash per file)")
    con.execute(f"""
        CREATE TABLE catalog AS
        SELECT job, path, MB, prd_modules, license, url, retrieved_at, sha256
        FROM read_csv('{p("catalog.csv")}', header=true)
    """)
    step(f"  {con.execute('SELECT count(*) FROM catalog').fetchone()[0]} files catalogued")


# --------------------------------------------------------------------------- main

def main() -> None:
    if not (DATA / "evidence_items.jsonl").exists():
        sys.exit("data/ is empty: run  python pipelines/fetch.py --out data  first")
    DB.parent.mkdir(exist_ok=True)
    DB.unlink(missing_ok=True)
    con = duckdb.connect(str(DB))
    con.execute("INSTALL spatial; LOAD spatial; INSTALL fts; LOAD fts;")
    t0 = time.time()
    build_geo(con)
    build_indicators(con)
    build_satellite(con)
    build_dilrmp(con)
    build_disputes(con)
    build_evidence(con)
    build_land_records(con)
    build_derived(con)
    build_catalog(con)
    con.execute("CHECKPOINT")
    con.close()
    print(f"\ndone in {time.time() - t0:.0f}s -> {DB} ({DB.stat().st_size / 1e6:.0f} MB)")


if __name__ == "__main__":
    main()
