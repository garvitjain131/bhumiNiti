"""Interactive GIS (#10): layers for land use, climate vulnerability, infrastructure, policy impact; cadastral overlay."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query

from ..core.db import feature_collection, one, rows
from ..core.security import can_access, current_user

router = APIRouter(prefix="/api/v1/geo", tags=["GIS"])

CADASTRAL = {"id": "dhamtari_cadastral", "name": "Cadastral parcels: Dhamtari district (Chhattisgarh)",
             "url": "/tiles/chhattisgarh/NCOG_CG_Dhamtari_Cadastrals.pmtiles", "layer": "NCOG_CG_Dhamtari_Cadastrals",
             "bounds": [81.409351, 20.492202, 81.758838, 20.856568], "minzoom": 11, "parcels": 159419,
             "source": "NCOG (BISAG-N) via open mirror", "district_name": "DHAMTARI"}


@router.get("/layers")
def layers():
    """Everything the map can show, grouped by the four themes of the brief."""
    metrics = rows("""SELECT m.*, count(d.district_lgd) AS districts FROM metric_meta m
                      LEFT JOIN district_metric d USING (metric) GROUP BY ALL ORDER BY theme, name""")
    indicators = rows("""SELECT m.indicator, m.name, m.unit, min(i.year) AS year_from, max(i.year) AS year_to,
                                count(DISTINCT i.district_lgd) AS districts
                         FROM indicator_meta m JOIN indicator i USING (indicator) GROUP BY ALL ORDER BY m.name""")
    return {
        "district_metrics": metrics,
        "time_series_indicators": indicators,
        "state_layers": [{"id": k, "name": n, "unit": "%"} for k, n in
                         [("ulpin_pct", "ULPIN assigned to land parcels"), ("georef_pct", "Parcels geo-referenced"),
                          ("maps_digitised_pct", "Cadastral maps digitised"), ("ror_pct", "Records of Rights computerised")]],
        "point_layers": [{"id": "conflicts", "name": "Land conflicts (Land Conflict Watch)", "theme": "Policy impact"},
                         {"id": "landslides", "name": "Landslides (GSI inventory)", "theme": "Climate"}],
        "cadastral": CADASTRAL,
    }


@router.get("/states")
def geo_states():
    """State polygons (Survey of India) with DILRMP progress and conflict counts attached."""
    return feature_collection("""
        SELECT ST_AsGeoJSON(s.geom_simple) AS gj, s.state_lgd, s.name,
               d.ulpin_pct, d.georef_pct, d.maps_digitised_pct, d.ror_pct,
               (SELECT count(*) FROM land_conflict c WHERE c.soi_state = s.name) AS conflicts
        FROM geo_state s LEFT JOIN dilrmp_state d ON d.soi_state_name = s.name""")


@router.get("/districts")
def geo_districts(metric: str | None = Query(None, description="a district metric id (see /geo/layers)"),
                  indicator: str | None = Query(None, description="or a time-series indicator id"),
                  year: int | None = Query(None, description="indicator year (default: latest)"),
                  state_lgd: int | None = None):
    """District polygons (Survey of India, simplified) with one value attached for colouring."""
    if metric:
        value_sql = "SELECT district_lgd, value, NULL::INTEGER AS year, label FROM district_metric WHERE metric = ?"
        params = [metric]
    else:
        ind = indicator or "pc11_pca_tot_p"
        value_sql = ("SELECT district_lgd, arg_max(value, year) AS value, max(year) AS year, any_value(label) AS label "
                     "FROM indicator WHERE indicator = ? AND (? IS NULL OR year = ?) GROUP BY 1")
        params = [ind, year, year]
    return feature_collection(f"""
        SELECT ST_AsGeoJSON(g.geom_simple) AS gj, g.district_lgd, g.state_lgd, g.name, g.state_name, g.is_disputed,
               round(g.area_km2) AS area_km2, v.value, v.year, v.label
        FROM geo_district g LEFT JOIN ({value_sql}) v USING (district_lgd)
        WHERE (? IS NULL OR g.state_lgd = ?)""", params + [state_lgd, state_lgd])


@router.get("/districts/{district_lgd}")
def district_profile(district_lgd: int):
    """District profile: all metrics, key time series, conflicts, and the most relevant evidence."""
    d = one("SELECT district_lgd, name, state_name, state_lgd, round(area_km2) AS area_km2, "
            "ST_AsGeoJSON(geom_simple) AS geometry FROM geo_district WHERE district_lgd = ?", [district_lgd])
    if not d:
        raise HTTPException(404, "district not found")
    d["geometry"] = json.loads(d["geometry"])
    d["metrics"] = rows("""SELECT m.metric, m.name, m.unit, m.theme, m.higher_is, m.method, d.value, d.label,
                                  round(100 * percent_rank() OVER (PARTITION BY m.metric ORDER BY d.value)) AS national_percentile
                           FROM district_metric d JOIN metric_meta m USING (metric)
                           QUALIFY d.district_lgd = ? ORDER BY m.theme, m.name""", [district_lgd])
    d["series"] = {}
    for key in ("dw_crops", "dw_built", "modis_cropland", "ghsl_built_km2", "viirs_ntl_mean", "chirps_rain_mm", "vcf_mean"):
        d["series"][key] = rows("SELECT year, value, label FROM indicator WHERE district_lgd = ? AND indicator = ? "
                                "ORDER BY year", [district_lgd, key])
    d["census"] = rows("""SELECT m.name, m.unit, i.value, i.year, i.label FROM indicator i JOIN indicator_meta m USING (indicator)
                          WHERE i.district_lgd = ? AND i.year = 2011 ORDER BY m.name""", [district_lgd])
    d["conflicts"] = rows("""SELECT url, title, year_started, people_affected, land_area_ha, sector, cause, ended
                             FROM land_conflict WHERE district_lgd = ? ORDER BY year_started DESC NULLS LAST""", [district_lgd])
    d["evidence"] = rows("""
        SELECT s.evidence_id, e.title, e.year, e.source, e.type_group, e.url
        FROM (SELECT evidence_id, fts_main_evidence_item.match_bm25(evidence_id, ?) AS score FROM evidence_item) s
        JOIN evidence_item e USING (evidence_id)
        WHERE s.score IS NOT NULL AND e.land_score >= 4 ORDER BY s.score DESC LIMIT 6""", [d["name"].title()])
    d["has_cadastral"] = d["name"] == CADASTRAL["district_name"]
    return d


@router.get("/points/conflicts")
def conflict_points(sector: str | None = None):
    """Conflicts aggregated at district centroids (exact sites are not published)."""
    return feature_collection("""
        SELECT ST_AsGeoJSON(ST_Centroid(g.geom_simple)) AS gj, g.district_lgd, g.name AS district, g.state_name,
               count(*) AS conflicts, sum(c.people_affected) AS people_affected, round(sum(c.land_area_ha)) AS land_area_ha,
               mode(c.sector) AS main_sector
        FROM land_conflict c JOIN geo_district g USING (district_lgd)
        WHERE (? IS NULL OR c.sector = ?) GROUP BY ALL""", [sector, sector])


@router.get("/points/landslides")
def landslide_points(state: str | None = None, limit: int = Query(40000, le=40000)):
    from ..core.config import DATA
    f = (DATA / "hazards/landslides/GSI_Landslide_Inventory.parquet").as_posix()
    return feature_collection(f"""
        SELECT ST_AsGeoJSON(geometry) AS gj, STATE AS state, DISTRICT AS district, TRIGGERING AS trigger,
               ACTIVITY AS activity FROM read_parquet('{f}')
        WHERE (? IS NULL OR lower(STATE) = lower(?)) LIMIT ?""", [state, state, limit])


@router.get("/query")
def spatial_query(rules: str = Query(..., examples=["built_growth_2000_2020:high,crops_change_2017_2025:low"],
                                     description="comma-separated metric:high|low"),
                  quantile: float = Query(0.25, gt=0, lt=0.5)):
    """Answer questions like 'where is built-up growth high and cropland shrinking?' with explicit thresholds."""
    parsed = []
    for part in rules.split(","):
        m, _, side = part.strip().partition(":")
        if side not in ("high", "low") or not one("SELECT 1 FROM metric_meta WHERE metric = ?", [m]):
            raise HTTPException(400, f"bad rule '{part}'; use metric:high or metric:low with a metric from /geo/layers")
        parsed.append((m, side))
    conds, params, thresholds = [], [], {}
    for m, side in parsed:
        t = one(f"SELECT quantile_cont(value, ?) AS t FROM district_metric WHERE metric = ?",
                [1 - quantile if side == "high" else quantile, m])["t"]
        thresholds[m] = {"side": side, "threshold": round(t, 3)}
        conds.append(f"max(value) FILTER (WHERE metric = ?) {'>=' if side == 'high' else '<='} ?")
        params += [m, t]
    res = rows(f"""SELECT g.district_lgd, g.name, g.state_name,
                          {', '.join(f"max(value) FILTER (WHERE metric = '{m}') AS {m}" for m, _ in parsed)}
                   FROM district_metric d JOIN geo_district g USING (district_lgd)
                   GROUP BY ALL HAVING {' AND '.join(conds)} ORDER BY g.state_name, g.name""", params)
    return {"rules": thresholds, "method": f"districts in the top/bottom {int(quantile * 100)}% for every rule",
            "count": len(res), "districts": res}


@router.get("/cadastral")
def cadastral_info():
    return CADASTRAL


@router.get("/cadastral/village-summary")
def cadastral_village(village: str, user: dict = Depends(current_user)):
    """Clicking a parcel: village-level summary of the (SYNTHETIC) land records, suppressed below 5 records.
    No owner details here; record-level views live under /records with role checks."""
    if user["role"] == "public":
        return {"village": village, "note": "sign in to see village-level land-record summaries"}
    r = one("""SELECT village, count(*) AS parcels, round(sum(area_ha), 1) AS area_ha,
                      round(avg((owner_gender = 'F')::INT), 3) AS female_owner_share,
                      round(avg((mortgage_bank IS NOT NULL)::INT), 3) AS mortgaged_share,
                      sum(mutation_pending::INT) AS mutation_pending, sum(dispute_pending::INT) AS dispute_pending,
                      round(median(circle_rate_lakh_per_ha), 1) AS median_circle_rate
               FROM land_record WHERE village = ? GROUP BY 1""", [village])
    if not r:
        raise HTTPException(404, "village not found")
    for k in ("mutation_pending", "dispute_pending"):
        if r[k] is not None and 0 < r[k] < 5:
            r[k] = None  # small-cell suppression
    r["synthetic"] = True
    r["record_level_access"] = can_access(user, "land_records_synthetic")
    return r
