#!/usr/bin/env python3
"""
LPIP national data bootstrap (SIH26019).

Pulls a pan-India, multi-source seed corpus in one parallel run and writes:

  data/<domain>/...            raw files, grouped by domain
  data/manifest.jsonl          one provenance record per file, hash-chained
  data/catalog.csv             human-readable dataset catalog
  data/evidence_items.jsonl    documents normalised to the evidence schema

Stdlib only. Optional: py7zr (extract LGD tables), pandas (SHRUG .dta -> .csv).

  python pipelines/fetch.py --list
  python pipelines/fetch.py --out data                      # core tier (~2.5 GB)
  python pipelines/fetch.py --out data --tier full          # + villages, OSM, CRZ (~6 GB more)
  python pipelines/fetch.py --out data --only boundaries,lgd_codes
  python pipelines/fetch.py --out data --register data/manual

Env vars (all optional, all free): GITHUB_TOKEN, OPENALEX_API_KEY, DATAGOV_API_KEY
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import csv
import datetime as dt
import hashlib
import html
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

UA = "LPIP-data-bootstrap/1.0 (SIH26019 research prototype)"
GH = "https://api.github.com"
ADMIN = "ramSeraph/indian_admin_boundaries"
LIC_MIRROR = ("Open mirror of Indian govt portal data (SOI/LGD/Bhuvan/NDEM/etc.) by ramSeraph; "
              "cite the original portal and check its terms before redistribution")

STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa", "Gujarat",
    "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh",
    "Maharashtra", "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab", "Rajasthan",
    "Sikkim", "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal",
    "Andaman and Nicobar", "Chandigarh", "Dadra and Nagar Haveli", "Daman and Diu", "Delhi",
    "Jammu and Kashmir", "Ladakh", "Lakshadweep", "Puducherry",
]
STATE_RE = re.compile(r"\b(" + "|".join(re.escape(s) for s in STATES) + r"|Orissa|Pondicherry)\b", re.I)


# --------------------------------------------------------------------------- http

def to_uri(url: str) -> str:
    """Percent-encode non-ASCII paths (gov.in sites use Devanagari slugs)."""
    u = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((u.scheme, u.netloc, urllib.parse.quote(u.path, safe="/%:@!$&'()*+,;=-._~"),
                                    urllib.parse.quote(u.query, safe="=&%+/:,;@!$'()*-._~"), ""))


def _headers(url: str, extra: dict | None = None) -> dict:
    h = {"User-Agent": UA}
    if url.startswith(GH) and os.environ.get("GITHUB_TOKEN"):
        h["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    return {**h, **(extra or {})}


def http_get(url: str, params: dict | None = None, timeout: int = 90, retries: int = 4) -> bytes:
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    url = to_uri(url)
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=_headers(url)), timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 403 and url.startswith(GH):
                raise  # GitHub rate limit: waiting will not help within this run
            if e.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(min(int(e.headers.get("Retry-After") or 0) or 3 * 2 ** attempt, 60))
                continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if attempt < retries - 1:
                time.sleep(3 * 2 ** attempt)
                continue
            raise


def get_json(url: str, params: dict | None = None):
    return json.loads(http_get(url, params))


def download(url: str, dest: Path, retries: int = 4) -> None:
    """Stream to dest with .part + HTTP Range resume."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    url = to_uri(url)
    for attempt in range(retries):
        have = part.stat().st_size if part.exists() else 0
        extra = {"Range": f"bytes={have}-"} if have else {}
        try:
            req = urllib.request.Request(url, headers=_headers(url, extra))
            with urllib.request.urlopen(req, timeout=120) as r:
                mode = "ab" if have and r.status == 206 else "wb"
                with open(part, mode) as f:
                    while chunk := r.read(1 << 20):
                        f.write(chunk)
            part.replace(dest)
            return
        except urllib.error.HTTPError as e:
            if e.code == 416:  # already complete
                part.replace(dest)
                return
            if attempt == retries - 1 or e.code in (401, 403, 404):
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if attempt == retries - 1:
                raise
        time.sleep(3 * 2 ** attempt)


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while chunk := f.read(1 << 22):
            h.update(chunk)
    return h.hexdigest()


# ------------------------------------------------------------------ provenance

class Manifest:
    """Append-only, hash-chained provenance log: each record carries the hash of the previous one."""

    def __init__(self, path: Path):
        self.path, self.lock = path, threading.Lock()
        self.prev, self.paths = "0" * 64, set()
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                rec = json.loads(line)
                self.prev = rec["record_hash"]
                self.paths.add(rec["path"])

    def add(self, force: bool = False, **rec) -> None:
        with self.lock:
            if rec["path"] in self.paths and not force:
                return
            rec["retrieved_at"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
            rec["prev_record_hash"] = self.prev
            rec["record_hash"] = hashlib.sha256(json.dumps(rec, sort_keys=True).encode()).hexdigest()
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            self.prev = rec["record_hash"]
            self.paths.add(rec["path"])


class Ctx:
    def __init__(self, args):
        self.args = args
        self.out = Path(args.out)
        self.out.mkdir(parents=True, exist_ok=True)
        self.manifest = Manifest(self.out / "manifest.jsonl")
        self.pool = cf.ThreadPoolExecutor(max_workers=args.workers)
        self.futures: list[cf.Future] = []
        self.log_lock = threading.Lock()
        self.errors: list[str] = []

    def log(self, job: str, msg: str) -> None:
        with self.log_lock:
            print(f"[{dt.datetime.now():%H:%M:%S}] {job:<20} {msg}", flush=True)

    def fetch(self, job: str, url: str, rel: str, *, license: str, prd: str, title: str = "",
              notes: str = "", max_mb: float | None = None, size: int | None = None) -> cf.Future:
        """Queue a file download; records provenance on success."""
        def run():
            dest = self.out / rel
            if dest.exists() and rel in self.manifest.paths:
                return dest
            if max_mb and size and size > max_mb * 1e6:
                self.log(job, f"skip {rel} ({size / 1e6:.0f} MB > {max_mb} MB cap)")
                return None
            if not dest.exists():
                self.log(job, f"GET  {rel}" + (f" ({size / 1e6:.1f} MB)" if size else ""))
                try:
                    download(url, dest)
                except Exception as e:  # keep going; report at the end
                    self.errors.append(f"{job}: {url} -> {e}")
                    self.log(job, f"FAIL {rel}: {e}")
                    return None
            self.manifest.add(job=job, title=title or dest.name, url=url, path=rel,
                              bytes=dest.stat().st_size, sha256=sha256_file(dest),
                              license=license, prd_modules=prd, geography="India",
                              access_level="public", notes=notes)
            return dest
        fut = self.pool.submit(run)
        self.futures.append(fut)
        return fut

    def record(self, job: str, rel: str, *, url: str, license: str, prd: str, title: str = "", notes: str = ""):
        """Provenance for a file this script generated itself (API harvests, manual files)."""
        dest = self.out / rel
        self.manifest.add(force=True, job=job, title=title or dest.name, url=url, path=rel,
                          bytes=dest.stat().st_size, sha256=sha256_file(dest), license=license,
                          prd_modules=prd, geography="India", access_level="public", notes=notes)


# ------------------------------------------------------------------ helpers

_asset_cache: dict[tuple, list] = {}


def gh_assets(repo: str, tag: str) -> list[dict]:
    key = (repo, tag)
    if key not in _asset_cache:
        rel = get_json(f"{GH}/repos/{repo}/releases/tags/{tag}")
        if len(rel.get("assets", [])) < 100:  # embedded list is complete; saves API calls
            _asset_cache[key] = rel["assets"]
        else:
            assets, page = [], 1
            while True:
                batch = get_json(f"{GH}/repos/{repo}/releases/{rel['id']}/assets", {"per_page": 100, "page": page})
                assets += batch
                if len(batch) < 100:
                    break
                page += 1
            _asset_cache[key] = assets
    return _asset_cache[key]


def gh_release_files(ctx: Ctx, job: str, repo: str, tag: str, patterns: list[str], subdir: str, *,
                     prd: str, license: str = LIC_MIRROR, max_mb: float | None = None):
    try:
        assets = gh_assets(repo, tag)
    except urllib.error.HTTPError as e:
        if e.code == 403:
            raise RuntimeError("GitHub API rate limit hit: set GITHUB_TOKEN (free) or wait an hour, then re-run") from e
        raise
    for a in assets:
        if any(re.search(p, a["name"]) for p in patterns):
            ctx.fetch(job, a["browser_download_url"], f"{subdir}/{tag}/{a['name']}", license=license,
                      prd=prd, size=a["size"], max_mb=max_mb, notes=f"github.com/{repo} release '{tag}'")


def abstract_from_index(inv: dict | None) -> str:
    if not inv:
        return ""
    pos = {i: w for w, idxs in inv.items() for i in idxs}
    return " ".join(pos[i] for i in sorted(pos))


def states_in(text: str) -> list[str]:
    alias = {"orissa": "Odisha", "pondicherry": "Puducherry"}
    return sorted({alias.get(m.lower()) or next(s for s in STATES if s.lower() == m.lower())
                   for m in STATE_RE.findall(text or "")})


def write_jsonl(path: Path, rows) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            n += 1
    return n


def safe_name(s: str, n: int = 80) -> str:
    return re.sub(r'[<>:"/\\|?*\x00-\x1f\s]+', "_", s).strip("_. ")[:n] or "file"


class TableParser(HTMLParser):
    """Minimal <table> -> rows extractor (no lxml/bs4 needed)."""

    def __init__(self):
        super().__init__()
        self.tables, self._row, self._cell, self._in_cell = [], None, [], False

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.tables.append([])
        elif tag == "tr" and self.tables:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._in_cell, self._cell = True, []

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._in_cell:
            self._row.append(" ".join("".join(self._cell).split()))
            self._in_cell = False
        elif tag == "tr" and self._row is not None:
            if self._row and self.tables:
                self.tables[-1].append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._in_cell:
            self._cell.append(data)


# ======================================================================= JOBS

def job_boundaries(ctx: Ctx):
    """Survey of India + LGD admin boundaries, Census-2011 / SHRUG polygons, historical districts 1941-2001."""
    j, prd = "boundaries", "Spatial Intelligence; Geography Domain"
    want = {
        "states": [r"^(SOI|LGD)_States\.parquet$"],
        "districts": [r"^(SOI|LGD)_Districts\.parquet$"],
        "subdistricts": [r"^(SOI|LGD)_Subdistricts\.parquet$"],
        "blocks": [r"^LGD_Blocks\.parquet$"],
        "census-2011": [r"^(Districts_2011|SubDistricts_2011|shrug-(district|subdistrict)-pc11)\.parquet$"],
        "historical": [r"\.csv$", r"^India-State-Districts-\d{4}\.parquet$"],
        "villages": [r"^SOI_VILLAGE_POINT\.parquet$"],
    }
    for tag, pats in want.items():
        gh_release_files(ctx, j, ADMIN, tag, pats, "boundaries", prd=prd)


def job_lgd_codes(ctx: Ctx):
    """Local Government Directory code tables (the join key for every Indian dataset), latest daily snapshot."""
    j, prd = "lgd_codes", "Geography Domain; Metadata Catalog"
    wanted = ["states", "districts", "subdistricts", "blocks", "villages", "pri_local_bodies",
              "statewise_ulbs_coverage", "district_panchayats", "gp_mapping", "pincode_villages",
              "invalidated_census_villages"]
    latest: dict[str, tuple] = {}
    try:
        assets = gh_assets("ramSeraph/opendata", "lgd-latest")
    except urllib.error.HTTPError as e:
        raise RuntimeError("GitHub API rate limit hit: set GITHUB_TOKEN (free) or wait an hour, then re-run") from e
    for a in assets:
        m = re.match(r"^([a-z_]+)\.(\d{2}[A-Za-z]{3}\d{4})\.csv\.7z$", a["name"])
        if m and m.group(1) in wanted:
            d = dt.datetime.strptime(m.group(2), "%d%b%Y")
            if m.group(1) not in latest or d > latest[m.group(1)][0]:
                latest[m.group(1)] = (d, a)
    futs = [ctx.fetch(j, a["browser_download_url"], f"lgd/{a['name']}", prd=prd, size=a["size"],
                      license="LGD (lgdirectory.gov.in), GODL-India; mirror github.com/ramSeraph/opendata")
            for _, a in latest.values()]
    try:
        import py7zr
    except ImportError:
        ctx.log(j, "py7zr not installed; leaving .7z files (pip install py7zr to auto-extract)")
        return
    for f in futs:
        p = f.result()
        if p and not p.with_suffix("").exists():
            with py7zr.SevenZipFile(p) as z:
                z.extractall(p.parent)


def job_shrug(ctx: Ctx):
    """SHRUG district-level tables: Census 2011 PCA/VD/TD, Economic Census, SECC, night lights, forest cover, PM2.5..."""
    j, prd = "shrug_district", "Socioeconomic indicators; Temporal Intelligence; Policy Analytics"
    ds = get_json("https://dataverse.harvard.edu/api/datasets/:persistentId/",
                  {"persistentId": "doi:10.7910/DVN/DPESAK"})["data"]["latestVersion"]
    ext = {"text/csv": "csv", "text/tab-separated-values": "tsv", "application/x-stata": "dta",
           "application/x-stata-14": "dta", "application/x-stata-13": "dta"}
    futs = []
    for f in ds["files"]:
        df = f["dataFile"]
        name = df["filename"]
        if name.startswith("shrug_v2.0") or not re.search(r"pc11dist|pop_area_key", name):
            continue
        fmt = ext.get(df.get("originalFileFormat", ""), name.rsplit(".", 1)[-1])
        futs.append(ctx.fetch(j, f"https://dataverse.harvard.edu/api/access/datafile/{df['id']}?format=original",
                              f"shrug/{name.rsplit('.', 1)[0]}.{fmt}", prd=prd,
                              license="CC BY-NC-SA 4.0 - Development Data Lab SHRUG (cite Asher et al. 2021)",
                              notes=f"Dataverse doi:10.7910/DVN/DPESAK v{ds['versionNumber']}"))
    try:
        import pandas as pd
    except ImportError:
        ctx.log(j, "pandas not installed; leaving Stata .dta files")
        return
    for f in futs:  # Stata -> CSV so the rest of the team doesn't need Stata
        p = f.result()
        if p and p.suffix == ".dta" and not p.with_suffix(".csv").exists():
            pd.read_stata(p, convert_categoricals=False).to_csv(p.with_suffix(".csv"), index=False)


def job_hazards(ctx: Ctx):
    """Climate/disaster layers: flood inundation 1998-2022 (NDEM), landslides (GSI/Bhuvan), cyclone tracks, earthquakes."""
    try:
        rels = get_json(f"{GH}/repos/ramSeraph/india_natural_disasters/releases", {"per_page": 50})
    except urllib.error.HTTPError as e:
        raise RuntimeError("GitHub API rate limit hit: set GITHUB_TOKEN (free) or wait an hour, then re-run") from e
    # core: national layers only; --tier full adds the per-state NDEM flood inundation files (~1.4 GB)
    pats = [r"\.parquet$"] if ctx.args.tier == "full" else [r"^(?!NDEM_[A-Z]{2}_).*\.parquet$"]
    for rel in rels:
        gh_release_files(ctx, "hazards", "ramSeraph/india_natural_disasters", rel["tag_name"], pats,
                         "hazards", prd="Spatial Intelligence (climate vulnerability layer)", max_mb=300)


def job_protected_land(ctx: Ctx):
    """Forests, eco-sensitive zones, wildlife reserves, mining leases: land-use constraint layers."""
    prd = "Spatial Intelligence (land-use constraints)"
    gh_release_files(ctx, "protected_land", ADMIN, "forests",
                     [r"^.*(Eco_Sensitive|Wildlife).*\.parquet$", r"^SOI_Forests\.parquet$"], "land_constraints",
                     prd=prd, max_mb=200)
    gh_release_files(ctx, "protected_land", "ramSeraph/indian_land_features", "mining", [r"\.parquet$"],
                     "land_constraints", prd=prd)


def job_ghsl(ctx: Ctx):
    """GHSL Urban Centre Database 2024: every Indian urban centre with built-up/population series 1975-2030."""
    ctx.fetch("ghsl_ucdb", "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/GHS_UCDB_GLOBE_R2024A/"
              "GHS_UCDB_GLOBE_R2024A/V1-1/GHS_UCDB_GLOBE_R2024A_V1_1.zip", "urban/GHS_UCDB_GLOBE_R2024A_V1_1.zip",
              prd="Urban expansion; Temporal Intelligence", license="CC BY 4.0 - European Commission JRC",
              notes="Global file; filter CTR_MN_ISO == 'IND'")


def job_nfhs5(ctx: Ctx):
    """NFHS-5 (2019-21) district & state factsheet indicators (socioeconomic context), incl. women's land ownership."""
    for name in ("NFHS-5-Districts.csv", "NFHS-5-States.csv"):  # raw URLs: no GitHub API call needed
        ctx.fetch("nfhs5", f"https://raw.githubusercontent.com/pratapvardhan/NFHS-5/master/{name}",
                  f"socioeconomic/nfhs5/{name}", prd="Socioeconomic indicators",
                  license="MoHFW/IIPS NFHS-5 factsheets, compiled by pratapvardhan")


def job_research_openalex(ctx: Ctx):
    """Scholarly literature on Indian land governance (OpenAlex): metadata, abstracts, OA PDF links."""
    j = "research_openalex"
    queries = {
        "land_records": '("land records" OR "record of rights" OR cadastral OR "land registration") AND India',
        "dilrmp_modernisation": '(DILRMP OR "Digital India Land Records" OR "land records modernisation" OR "land records modernization" OR "land record computerisation")',
        "svamitva_abadi": '(SVAMITVA OR "property card" OR "abadi" OR "drone survey") AND India',
        "land_titling": '("land title" OR titling OR "conclusive title" OR "tenure security") AND India',
        "land_acquisition": '("land acquisition" OR RFCTLARR OR "compulsory acquisition" OR "eminent domain") AND India',
        "land_disputes": '("land dispute" OR "land conflict" OR "land litigation" OR "property dispute") AND India',
        "tenancy_leasing": '(tenancy OR "land leasing" OR sharecropping OR "tenant farmer") AND India',
        "land_reform": '("land reform" OR "land ceiling" OR "land redistribution" OR "surplus land") AND India',
        "fragmentation_holdings": '("land fragmentation" OR "operational holdings" OR "landholding" OR consolidation) AND India',
        "agri_land_conversion": '("agricultural land" AND (conversion OR loss OR diversion)) AND India',
        "urban_expansion": '("urban expansion" OR "urban sprawl" OR "peri-urban" OR periurban OR "urban growth") AND India',
        "lulc_change": '("land use change" OR "land cover change" OR LULC OR "land use/land cover") AND India',
        "land_pooling": '("land pooling" OR "land readjustment" OR "town planning scheme" OR "transferable development rights") AND India',
        "land_markets_valuation": '("land market" OR "land price" OR "land value" OR "circle rate" OR "stamp duty" OR "guidance value") AND India',
        "forest_rights": '("Forest Rights Act" OR "forest rights" OR "community forest resource" OR "forest land diversion") AND India',
        "tribal_land": '(PESA OR "tribal land" OR "Scheduled Area" OR "land alienation" OR Adivasi) AND land AND India',
        "gender_land": '(women OR gender) AND ("land rights" OR "land ownership" OR "land title") AND India',
        "commons": '("common land" OR "common property" OR "village commons" OR "grazing land" OR "gauchar") AND India',
        "wasteland_degradation": '(wasteland OR "land degradation" OR desertification OR "degraded land") AND India',
        "watershed": '(watershed AND (development OR programme OR management)) AND India',
        "climate_land": '("climate vulnerability" OR "climate risk" OR drought OR flood) AND (land OR agriculture) AND India AND district',
        "land_governance": '("land governance" OR "land administration" OR "land policy" OR "land management") AND India',
        "geospatial_cadastre": '("remote sensing" OR satellite OR GIS OR drone) AND (cadastral OR "land records" OR parcel) AND India',
        "urban_tenure": '("informal settlement" OR slum OR "urban land") AND (tenure OR "property rights" OR title) AND India',
        "land_credit": '("land record" OR "land title" OR collateral OR "land ownership") AND (credit OR loan OR investment) AND India',
        "infra_land": '("land acquisition" OR "land use") AND (highway OR "industrial corridor" OR SEZ OR "special economic zone" OR "smart city") AND India',
        "mining_displacement": '(mining OR dam OR project) AND (displacement OR resettlement OR rehabilitation) AND land AND India',
        "policy_evaluation": '("difference-in-differences" OR "impact evaluation" OR "natural experiment" OR randomized) AND (land OR property OR tenure) AND India',
        "urban_land_records": '(NAKSHA OR "urban land record" OR "property tax" OR "urban property") AND India',
        "ulpin_landstack": '(ULPIN OR "unique land parcel" OR "Bhu-Aadhaar" OR "land stack" OR "land parcel identification") AND India',
    }
    base = {"select": "id,doi,title,publication_year,publication_date,type,authorships,primary_location,"
                      "open_access,best_oa_location,abstract_inverted_index,topics,keywords,cited_by_count,language",
            "per-page": 200}
    if key := os.environ.get("OPENALEX_API_KEY"):
        base["api_key"] = key
    works: dict[str, dict] = {}
    exhausted = False
    for tag, q in queries.items():
        cursor, pages = "*", 0
        while cursor and pages < ctx.args.openalex_pages and not exhausted:
            try:
                d = get_json("https://api.openalex.org/works",
                             {**base, "filter": f"title_and_abstract.search:{q}", "cursor": cursor})
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    ctx.log(j, "OpenAlex daily budget exhausted; set OPENALEX_API_KEY (free) and re-run")
                    exhausted = True
                    break
                raise
            for w in d["results"]:
                works.setdefault(w["id"], {**w, "_topics": []})["_topics"].append(tag)
            cursor, pages = d["meta"].get("next_cursor"), pages + 1
        ctx.log(j, f"{tag:<24} total={len(works)}")

    raw, ev = [], []
    for w in works.values():
        abstract = abstract_from_index(w.pop("abstract_inverted_index", None))
        w["abstract"] = abstract
        raw.append(w)
        loc = w.get("primary_location") or {}
        src = (loc.get("source") or {})
        oa = w.get("best_oa_location") or {}
        ev.append({
            "evidence_id": "openalex:" + w["id"].rsplit("/", 1)[-1],
            "title": w.get("title"),
            "type": {"article": "research_paper", "preprint": "research_paper", "book-chapter": "research_paper",
                     "report": "report", "dissertation": "thesis"}.get(w.get("type"), w.get("type")),
            "source_organization": src.get("host_organization_name") or src.get("display_name"),
            "authors": [a["author"]["display_name"] for a in w.get("authorships", [])][:25],
            "institutions": sorted({i["display_name"] for a in w.get("authorships", []) for i in a.get("institutions", [])}),
            "publication_date": w.get("publication_date"),
            "geography": {"country": "India", "states_mentioned": states_in(f"{w.get('title')} {abstract}")},
            "time_period": None,
            "policy_domain": w["_topics"],
            "access_level": "public",
            "methodology": None,
            "citation": {"doi": w.get("doi"), "openalex": w["id"], "cited_by": w.get("cited_by_count")},
            "license": oa.get("license"),
            "pdf_url": oa.get("pdf_url"),
            "landing_url": oa.get("landing_page_url") or loc.get("landing_page_url"),
            "abstract": abstract,
            "version": 1,
            "quality_status": "unreviewed",
            "source": "openalex",
        })
    rel = "research/openalex_works.jsonl"
    write_jsonl(ctx.out / rel, raw)
    ctx.record(j, rel, url="https://api.openalex.org/works", prd="Evidence Intelligence; Research Domain",
               license="OpenAlex metadata CC0; abstracts/PDFs remain under publisher terms",
               notes=f"{len(raw)} works from {len(queries)} topic queries" + (" (budget-truncated)" if exhausted else ""))
    write_jsonl(ctx.out / "research/openalex_evidence.jsonl", ev)

    n = 0
    for e in sorted(ev, key=lambda e: -(e["citation"]["cited_by"] or 0)):
        if n >= ctx.args.pdf_cap:
            break
        if e["pdf_url"]:
            ctx.fetch(j, e["pdf_url"], f"research/pdfs/{safe_name(e['evidence_id'])}.pdf",
                      title=e["title"] or "", prd="Evidence Intelligence",
                      license=e["license"] or "open access (see source)", notes=e["evidence_id"])
            n += 1


def job_policy_worldbank(ctx: Ctx):
    """World Bank documents on India land administration/tenure/acquisition/urban land (reports + PDFs)."""
    j = "policy_worldbank"
    terms = ["land records", "land administration", "land acquisition", "land tenure", "urban land",
             "land use planning", "land reform", "property rights", "watershed", "land governance",
             "resettlement", "cadastral survey"]
    docs: dict[str, dict] = {}
    for t in terms:
        for os_ in (0, 100):
            d = get_json("https://search.worldbank.org/api/v3/wds",
                         {"format": "json", "qterm": t, "count_exact": "India", "rows": 100, "os": os_,
                          "fl": "display_title,docdt,docty,majdocty,pdfurl,url,count,abstracts,repnme,lang"})
            batch = [v for v in d["documents"].values() if isinstance(v, dict) and "id" in v]
            for v in batch:
                docs.setdefault(v["id"], {**v, "_topics": []})["_topics"].append(t)
            if len(batch) < 100:
                break
    ev = [{
        "evidence_id": f"worldbank:{v['id']}",
        "title": v.get("display_title"),
        "type": (v.get("docty") or "report").lower(),
        "source_organization": "World Bank",
        "authors": [],
        "publication_date": (v.get("docdt") or "")[:10],
        "geography": {"country": "India", "states_mentioned": states_in(
            f"{v.get('display_title')} {(v.get('abstracts') or {}).get('cdata!', '')}")},
        "policy_domain": v["_topics"],
        "access_level": "public",
        "citation": {"url": v.get("url")},
        "license": "World Bank documents: CC BY 3.0 IGO unless stated",
        "pdf_url": v.get("pdfurl"),
        "abstract": (v.get("abstracts") or {}).get("cdata!", ""),
        "version": 1, "quality_status": "unreviewed", "source": "worldbank",
    } for v in docs.values()]
    rel = "policy/worldbank_evidence.jsonl"
    write_jsonl(ctx.out / rel, ev)
    ctx.record(j, rel, url="https://search.worldbank.org/api/v3/wds", prd="Evidence Intelligence; Policy Domain",
               license="World Bank", notes=f"{len(ev)} documents")
    ctx.log(j, f"{len(ev)} documents indexed")
    for e in sorted(ev, key=lambda e: e["publication_date"], reverse=True)[:ctx.args.pdf_cap]:
        if e["pdf_url"]:
            ctx.fetch(j, e["pdf_url"].replace("http://", "https://"),
                      f"policy/worldbank_pdfs/{safe_name(e['evidence_id'])}.pdf", title=e["title"] or "",
                      prd="Evidence Intelligence", license=e["license"], notes=e["evidence_id"])


CRAWL_SEEDS = {
    # name: (seed urls, allowed page hosts)
    "dolr": (["https://dolr.gov.in/en/", "https://dolr.gov.in/"], {"dolr.gov.in"}),
}

NOISE = re.compile(r"advertis|auction|recruit|vacanc|tender|posting|deputation|contract(ual)? basis|procurement|"
                   r"hindi (diwas|fortnight|pakhwada)|\bRTI\b|empanel|quotation", re.I)


def job_policy_govdocs(ctx: Ctx):
    """Polite crawl of DoLR (guidelines, circulars, annual reports, Wasteland Atlas, scheme docs) for PDFs."""
    j = "policy_govdocs"
    link_re = re.compile(r'<a\s[^>]*href="([^"#]+)"[^>]*>(.*?)</a>', re.I | re.S)
    for name, (seeds, hosts) in CRAWL_SEEDS.items():
        seen, queue, later, pdfs = set(), [(u, 0) for u in seeds], [], {}
        while (queue or later) and len(seen) < ctx.args.crawl_pages:
            url, depth = (queue or later).pop(0)
            if url in seen:
                continue
            seen.add(url)
            try:
                page = http_get(url, timeout=45).decode("utf-8", "replace")
            except Exception as e:
                ctx.log(j, f"skip page {url}: {e}")
                continue
            for href, text in link_re.findall(page):
                u = urllib.parse.urljoin(url, html.unescape(href))
                label = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", text)).split())
                label = re.sub(r"\s+New$", "", label)
                host = urllib.parse.urlparse(u).netloc
                if u.lower().split("?")[0].endswith(".pdf"):
                    if NOISE.search(label):  # admin notices, not evidence
                        continue
                    if u not in pdfs or (label and not pdfs[u]["title"]):
                        pdfs[u] = {"title": label, "found_on": url}
                elif host in hosts and depth < 2 and not re.search(r"wp-admin|wp-login|\.(jpg|png|zip|mp4)$", u):
                    # English pages first; Hindi mirrors (/hi/, Devanagari slugs) only if budget remains
                    (later if "/hi/" in u or not u.isascii() else queue).append((u.split("#")[0], depth + 1))
            time.sleep(0.4)
        ctx.log(j, f"{name}: crawled {len(seen)} pages, {len(pdfs)} PDFs")
        ev = []
        for i, (u, m) in enumerate(pdfs.items()):
            if i >= ctx.args.pdf_cap * 3:
                break
            eid = f"{name}:{hashlib.sha1(u.encode()).hexdigest()[:12]}"
            ctx.fetch(j, u, f"policy/{name}_pdfs/{safe_name(m['title'] or eid, 60)}_{eid[-6:]}.pdf",
                      title=m["title"], prd="Evidence Intelligence; Policy Domain",
                      license="Government of India (GODL-India)", notes=f"found on {m['found_on']}")
            ev.append({"evidence_id": eid, "title": m["title"], "type": "government_document",
                       "source_organization": "Department of Land Resources, MoRD" if name == "dolr" else name,
                       "geography": {"country": "India", "states_mentioned": states_in(m["title"])},
                       "access_level": "public", "citation": {"url": u, "found_on": m["found_on"]},
                       "license": "GODL-India", "pdf_url": u, "version": 1, "quality_status": "unreviewed",
                       "source": name})
        write_jsonl(ctx.out / f"policy/{name}_evidence.jsonl", ev)


def job_dilrmp_progress(ctx: Ctx):
    """DILRMP state-level physical progress (RoR computerisation, map digitisation, SRO) - may need an Indian IP."""
    j = "dilrmp_progress"
    for part in ("clr", "map", "sro"):
        url = f"https://dilrmp.gov.in/physicalProgressReports/{part}/state-level"
        try:
            page = http_get(url, timeout=60, retries=2).decode("utf-8", "replace")
        except Exception as e:
            ctx.log(j, f"{part}: unreachable ({e}); download manually from {url}")
            continue
        (ctx.out / "land_records").mkdir(parents=True, exist_ok=True)
        (ctx.out / f"land_records/dilrmp_{part}_state.html").write_text(page, encoding="utf-8")
        p = TableParser()
        p.feed(page)
        for k, rows in enumerate(t for t in p.tables if len(t) > 3):
            rel = f"land_records/dilrmp_{part}_state_{k}.csv"
            with open(ctx.out / rel, "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerows(rows)
            ctx.record(j, rel, url=url, prd="Policy Analytics (DILRMP performance); Dashboards",
                       license="Government of India (GODL-India)")
        ctx.log(j, f"{part}: {len(p.tables)} tables")


def job_datagov(ctx: Ctx):
    """data.gov.in resources listed in datagov_resources.txt (needs free DATAGOV_API_KEY)."""
    j = "datagov"
    key, ids_file = os.environ.get("DATAGOV_API_KEY"), Path(__file__).with_name("datagov_resources.txt")
    ids = [l.split("#")[0].strip() for l in ids_file.read_text().splitlines()] if ids_file.exists() else []
    ids = [i for i in ids if i]
    if not key or not ids:
        ctx.log(j, "skipped: set DATAGOV_API_KEY and add resource IDs to pipelines/datagov_resources.txt")
        return
    for rid in ids:
        rows, off, title = [], 0, rid
        while True:
            d = get_json(f"https://api.data.gov.in/resource/{rid}",
                         {"api-key": key, "format": "json", "offset": off, "limit": 1000})
            title = d.get("title", title)
            rows += d.get("records", [])
            off += 1000
            if off >= int(d.get("total", 0)) or not d.get("records"):
                break
        if not rows:
            continue
        rel = f"datagov/{safe_name(title, 90)}__{rid[:8]}.csv"
        (ctx.out / "datagov").mkdir(parents=True, exist_ok=True)
        with open(ctx.out / rel, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        ctx.record(j, rel, url=f"https://data.gov.in/resource/{rid}", title=title,
                   prd="Policy Analytics; Dashboards", license="GODL-India")
        ctx.log(j, f"{title[:60]}: {len(rows)} rows")


LCW = "https://www.landconflictwatch.org"
LCW_FIELDS = {  # label on the page -> column name
    "Sector": "sector", "Reason/Cause of conflict": "cause", "Legal Status": "legal_status",
    "Region Classification": "region_type", "Type of Land": "land_type",
    "Demand/Contention of the Affected Community": "community_demand",
    "Significance of Land to Land Owners/Users": "land_significance",
    "Categories of Legislations Involved in the Conflict": "legislation_categories",
    "Legislations/Policies Involved": "legislations",
    "Legal Processes and Loopholes Enabling the Conflict:": "legal_loopholes",
    "Major Human Rights Violations Related to the Conflict:": "rights_violations",
    "Government Departments Involved in the Conflict:": "govt_departments",
    "PSUs Involved in the Conflict:": "psus", "Corporate Parties Involved in the Conflict:": "corporates",
    "Has the Conflict Ended?": "ended", "Type of investment:": "investment_type", "Status of Project": "project_status",
}
LCW_SECTIONS = {"Summary", "Fact Sheet", "Legal Data", "Additional Info", "Additional Information", "Criminal Law",
                "Key Insights", "JOIN", "Information on the use of criminal law", "Author", "Latest updates",
                "Conflict Status", "|", "Updated :", "Year of Estimation", "Original Project Deadline", "Source/Reference",
                "Whether the Project has been Delayed", "Whether the project was stalled due to land conflict",
                "Status of Case In Court", "Legal Supporting Documents", "Reported Details of the Violation:"}


def parse_lcw(page: str) -> dict:
    """Land Conflict Watch conflict page -> flat record. Labels are followed by their value lines."""
    title = html.unescape((re.search(r"<title>(.*?)</title>", page, re.S) or [None, ""])[1]).strip()
    body = re.sub(r"(?is)<(script|style|svg|noscript)[^>]*>.*?</\1>", " ", page)
    lines = [x for x in (html.unescape(t).strip() for t in re.split(r"<[^>]+>", body)) if x]
    labels = set(LCW_FIELDS) | LCW_SECTIONS

    def is_stop(x: str) -> bool:
        return x in labels or x.endswith("?") or (x.endswith(":") and len(x) > 12) or x.isdigit() and len(x) == 1

    def after(label: str, start: int = 0) -> str:
        try:
            i = lines.index(label, start)
        except ValueError:
            return ""
        vals = []
        for x in lines[i + 1:]:
            if is_stop(x):
                break
            vals.append(x)
        return "; ".join(vals)

    def before(label: str) -> str:
        for i, x in enumerate(lines):
            if x.lower() == label.lower() and i > 0:
                prev = lines[i - 1]
                return lines[i - 2] if prev in ("ha.", "acres") and i > 1 else prev
        return ""

    fact = lines.index("Fact Sheet", lines.index("Fact Sheet") + 1) if lines.count("Fact Sheet") > 1 else 0
    name, _, place = title.rpartition(" | ")
    parts = [p.strip() for p in place.split(",") if p.strip()]
    rec = {"title": name or title, "district": parts[0] if parts else "", "state": parts[-1] if parts else "",
           "published": after("Published :"),
           "households_affected": before("Households affected"), "people_affected": before("People affected"),
           "year_started": before("Year started"), "land_area_ha": before("Land area affected")}
    for label, col in LCW_FIELDS.items():
        v = after(label, fact) or after(label)
        rec[col] = "" if v in ("No items found.", "Select sector") else v
    inv = re.search(r"Total investment involved \(in Crores\):\s*₹?\s*([\d.,]+)", " ".join(lines))
    rec["investment_crore"] = inv.group(1).replace(",", "") if inv else ""
    try:
        i = next(k for k in range(1, len(lines)) if lines[k] == "Summary" and lines[k - 1] == "1")
        summ = []
        for x in lines[i + 1:]:
            if x == "Fact Sheet" or (x == "2" and len(summ) > 2):
                break
            summ.append(x)
        rec["summary"] = re.sub(r"\s+([,.;:])", r"\1", " ".join(summ))[:4000]
    except StopIteration:
        rec["summary"] = ""
    for k in ("households_affected", "people_affected", "year_started", "land_area_ha"):
        rec[k] = rec[k].replace(",", "") if re.fullmatch(r"[\d.,]+", rec[k] or "") else ""
    return rec


def job_land_conflicts(ctx: Ctx):
    """Land Conflict Watch: ~1,250 documented land conflicts (people/area affected, cause, sector, laws, status)."""
    import gzip
    j, raw = "land_conflicts", ctx.out / "disputes" / "lcw_pages"
    raw.mkdir(parents=True, exist_ok=True)
    sm = http_get(f"{LCW}/sitemap.xml").decode("utf-8", "replace")
    urls = sorted(set(re.findall(r"<loc>(https://www\.landconflictwatch\.org/conflicts/[^<]+)</loc>", sm)))
    ctx.log(j, f"{len(urls)} conflict pages in sitemap (cached pages are reused)")

    def grab(url: str):
        f = raw / (url.rsplit("/", 1)[-1][:150] + ".html.gz")
        if not f.exists():
            time.sleep(0.35)  # polite: ~3 requests/second across 3 workers
            try:
                page = http_get(url, timeout=45, retries=3)
            except Exception as e:
                return url, None, str(e)
            f.write_bytes(gzip.compress(page))
        return url, gzip.decompress(f.read_bytes()).decode("utf-8", "replace"), None

    recs, failed, done = [], [], 0
    with cf.ThreadPoolExecutor(max_workers=3) as pool:
        for url, page, err in pool.map(grab, urls):
            done += 1
            if done % 200 == 0:
                ctx.log(j, f"{done}/{len(urls)} pages")
            if page is None:
                failed.append(f"{url}: {err}")
                continue
            r = parse_lcw(page)
            r["url"] = url
            recs.append(r)
    if not recs:
        raise RuntimeError("no Land Conflict Watch pages could be fetched")
    cols = ["url", "title", "state", "district", "year_started", "people_affected", "households_affected",
            "land_area_ha", "investment_crore", "published", *LCW_FIELDS.values(), "summary"]
    rel = "disputes/lcw_conflicts.csv"
    with open(ctx.out / rel, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(recs)
    lic = "Land Conflict Watch (landconflictwatch.org) - cite LCW; check their terms before redistribution"
    ctx.record(j, rel, url=f"{LCW}/all-conflicts", license=lic, prd="Dashboards (land disputes); Gap Radar; case studies",
               notes=f"{len(recs)} conflicts parsed, {len(failed)} pages failed")
    months = {m: i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct",
                                          "Nov", "Dec"], 1)}
    ev = []
    for r in recs:
        m = re.match(r"([A-Z][a-z]{2})\w*\s+(\d{4})", r["published"] or "")
        ev.append({"evidence_id": "lcw:" + hashlib.sha1(r["url"].encode()).hexdigest()[:12], "title": r["title"],
                   "type": "case_study", "source_organization": "Land Conflict Watch",
                   "publication_date": f"{m.group(2)}-{months.get(m.group(1), 1):02d}-01" if m else None,
                   "geography": {"country": "India", "states_mentioned": states_in(r["state"]) or states_in(r["title"])},
                   "policy_domain": ["land_disputes"] + ([r["sector"].lower().replace(" ", "_")] if r["sector"] else []),
                   "access_level": "public", "citation": {"url": r["url"]}, "license": lic, "pdf_url": None,
                   "landing_url": r["url"], "abstract": r["summary"], "version": 1, "quality_status": "unreviewed",
                   "source": "landconflictwatch"})
    write_jsonl(ctx.out / "disputes/lcw_evidence.jsonl", ev)
    ctx.errors.extend(f"{j}: {x}" for x in failed[:20])
    ctx.log(j, f"{len(recs)} conflicts -> {rel}; {len(failed)} failed")


def job_wasteland_atlas(ctx: Ctx):
    """DoLR/NRSC Wastelands Atlas of India 2019: state chapters with district-wise wasteland change 2008-09 to 2015-16."""
    page_url = "https://dolr.gov.in/en/wasteland-atlas-of-india-2019/"
    page = http_get(page_url).decode("utf-8", "replace")
    rows = re.findall(r"<tr>\s*<td>\s*\d+\s*</td>\s*<td>(.*?)</td>\s*<td>\s*<a href=\"([^\"]+\.pdf)\"", page, re.S)
    for title, url in rows:
        title = html.unescape(re.sub(r"<[^>]+>", "", title)).strip()
        if title.lower().startswith("complete publication"):
            continue  # same content as the chapters, hosted on archive.org
        ctx.fetch("wasteland_atlas", url, f"wasteland_atlas/{safe_name(title, 70)}.pdf", title=f"Wastelands Atlas 2019: {title}",
                  prd="Climate resilience; land degradation", license="Government of India (DoLR, NRSC), GODL-India",
                  notes=f"listed on {page_url}")
    ctx.log("wasteland_atlas", f"{len(rows)} documents listed")


REPORTS = [  # (url, file name, title, licence)
    ("https://dst.gov.in/sites/default/files/Full%20Report%20%281%29.pdf", "dst_climate_vulnerability_assessment.pdf",
     "Climate Vulnerability Assessment for Adaptation Planning in India Using a Common Framework (DST)",
     "Government of India (DST), GODL-India"),
]


def job_cadastral_demo(ctx: Ctx):
    """Cadastral parcel maps for one demo district (Dhamtari, Chhattisgarh; NCOG): parcel geometry + map tiles."""
    gh_release_files(ctx, "cadastral_demo", "ramSeraph/indian_cadastrals", "chhattisgarh",
                     [r"^NCOG_CG_Dhamtari_Cadastrals\.(parquet|pmtiles)$"], "cadastral",
                     prd="Spatial Intelligence (cadastral overlay); anonymisation demo",
                     license="NCOG/BISAG-N cadastral data via open mirror github.com/ramSeraph/indian_cadastrals; "
                             "cite the original portal")


def job_reports(ctx: Ctx):
    """Individual national reports: DST district climate-vulnerability assessment."""
    for url, name, title, lic in REPORTS:
        ctx.fetch("reports", url, f"reports/{name}", title=title, license=lic,
                  prd="Climate vulnerability layer; Evidence Intelligence")


# --- full tier -------------------------------------------------------------

def job_villages(ctx: Ctx):
    """Village polygons (SOI ~0.7 GB, LGD ~0.55 GB) for village-level drill-down."""
    gh_release_files(ctx, "villages", ADMIN, "villages", [r"^(SOI_villages|LGD_Villages)\.parquet$"],
                     "boundaries", prd="Spatial Intelligence; Geography Domain")


def job_settlements(ctx: Ctx):
    """PMGSY habitations, SOI places, Sentinel-2 2023 built-up footprints."""
    gh_release_files(ctx, "settlements", ADMIN, "habitations",
                     [r"^(PMGSY_Habitations|SOI_places|ESRI_Sentinel2_10m_2023_Builtup_Area)\.parquet$"],
                     "urban", prd="Infrastructure; Urban expansion")


def job_coastal(ctx: Ctx):
    """CRZ 2019 coastal regulation zones (land-use constraint)."""
    gh_release_files(ctx, "coastal", ADMIN, "coastal", [r"^Bharatmaps_Parivesh_CRZ2019_Regulatory_Zones\.parquet$"],
                     "land_constraints", prd="Spatial Intelligence (land-use constraints)")


def job_osm(ctx: Ctx):
    """OpenStreetMap India: latest + 2014 snapshot (roads/infrastructure change over a decade)."""
    for snap in ("latest", "140101"):
        ctx.fetch("osm", f"https://download.geofabrik.de/asia/india-{snap}.osm.pbf", f"infrastructure/india-{snap}.osm.pbf",
                  prd="Infrastructure layer; Temporal Intelligence", license="ODbL 1.0 - (c) OpenStreetMap contributors")


JOBS = {
    "boundaries":        ("core", job_boundaries),
    "lgd_codes":         ("core", job_lgd_codes),
    "shrug_district":    ("core", job_shrug),
    "hazards":           ("core", job_hazards),
    "protected_land":    ("core", job_protected_land),
    "ghsl_ucdb":         ("core", job_ghsl),
    "nfhs5":             ("core", job_nfhs5),
    "research_openalex": ("core", job_research_openalex),
    "policy_worldbank":  ("core", job_policy_worldbank),
    "policy_govdocs":    ("core", job_policy_govdocs),
    "dilrmp_progress":   ("core", job_dilrmp_progress),
    "datagov":           ("core", job_datagov),
    "land_conflicts":    ("core", job_land_conflicts),
    "wasteland_atlas":   ("core", job_wasteland_atlas),
    "reports":           ("core", job_reports),
    "cadastral_demo":    ("core", job_cadastral_demo),
    "villages":          ("full", job_villages),
    "settlements":       ("full", job_settlements),
    "coastal":           ("full", job_coastal),
    "osm":               ("full", job_osm),
}


def finalize(ctx: Ctx):
    mf = ctx.out / "manifest.jsonl"
    lines = mf.read_text(encoding="utf-8").splitlines() if mf.exists() else []
    recs = list({(r := json.loads(l))["path"]: r for l in lines}.values())  # latest version per path
    with open(ctx.out / "catalog.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["job", "path", "MB", "prd_modules", "license", "url", "retrieved_at", "sha256"])
        for r in recs:
            w.writerow([r["job"], r["path"], round(r["bytes"] / 1e6, 2), r["prd_modules"], r["license"],
                        r["url"], r["retrieved_at"], r["sha256"]])
    n = 0
    with open(ctx.out / "evidence_items.jsonl", "w", encoding="utf-8") as out:
        for p in sorted(ctx.out.glob("*/*_evidence.jsonl")):
            for line in p.read_text(encoding="utf-8").splitlines():
                out.write(line + "\n")
                n += 1
    total = sum(r["bytes"] for r in recs) / 1e9
    print(f"\n== {len(recs)} files, {total:.2f} GB, {n} evidence items -> {ctx.out}/catalog.csv, evidence_items.jsonl")
    if ctx.errors:
        print(f"== {len(ctx.errors)} failures (re-run to resume):")
        for e in ctx.errors[:30]:
            print("   ", e)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tier", choices=["core", "full"], default="core")
    ap.add_argument("--only", help="comma-separated job names")
    ap.add_argument("--out", default="data")
    ap.add_argument("--workers", type=int, default=8, help="parallel downloads")
    ap.add_argument("--pdf-cap", type=int, default=80, help="max PDFs per document source")
    ap.add_argument("--openalex-pages", type=int, default=3, help="200-result pages per topic (no key: keep <=3)")
    ap.add_argument("--crawl-pages", type=int, default=120, help="max HTML pages per crawl seed")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--register", metavar="DIR",
                    help="hash + add hand-downloaded files under DIR (inside --out) to the manifest, then exit")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Hindi titles on Windows consoles

    if args.list:
        for name, (tier, fn) in JOBS.items():
            print(f"{name:<18} [{tier}]  {fn.__doc__.strip()}")
        return
    if args.register:
        ctx = Ctx(args)
        for f in sorted(Path(args.register).rglob("*")):
            if f.is_file() and not f.name.endswith(".part"):
                rel = f.resolve().relative_to(ctx.out.resolve()).as_posix()
                ctx.record("manual", rel, url="(manual download - fill in)", license="(see source portal)",
                           prd="", notes="registered via --register")
        ctx.pool.shutdown()
        finalize(ctx)
        return
    names = args.only.split(",") if args.only else [n for n, (t, _) in JOBS.items()
                                                    if t == "core" or args.tier == "full"]
    unknown = [n for n in names if n not in JOBS]
    if unknown:
        sys.exit(f"unknown job(s): {unknown}; see --list")

    ctx, t0 = Ctx(args), time.time()
    with cf.ThreadPoolExecutor(max_workers=len(names)) as jobs:
        futs = {jobs.submit(JOBS[n][1], ctx): n for n in names}
        for f in cf.as_completed(futs):
            try:
                f.result()
            except Exception as e:
                ctx.errors.append(f"{futs[f]}: {e}")
                ctx.log(futs[f], f"JOB FAILED: {e}")
    # downloads may enqueue while jobs finish; drain until stable
    while any(not f.done() for f in list(ctx.futures)):
        cf.wait(list(ctx.futures))
    ctx.pool.shutdown()
    finalize(ctx)
    print(f"== done in {(time.time() - t0) / 60:.1f} min")


if __name__ == "__main__":
    main()
