"""
Dashboards (#16): research outputs, policy performance, land-use trends, climate resilience, land disputes,
project implementation outcomes, geospatial insights. Every KPI carries its definition, source and label.
"""
from __future__ import annotations

from fastapi import APIRouter

from ..core.db import one, q, rows

router = APIRouter(prefix="/api/v1/dashboards", tags=["dashboards"])


def kpi(name, value, unit, source, definition, label="OBSERVED", period=None):
    return {"name": name, "value": value, "unit": unit, "source": source, "definition": definition,
            "label": label, "period": period}


@router.get("/research")
def research_outputs():
    k = one("""SELECT count(*) AS items, count(*) FILTER (WHERE source = 'openalex') AS papers,
                      count(*) FILTER (WHERE type_group = 'Case study') AS case_studies,
                      count(*) FILTER (WHERE type_group IN ('Legal document', 'Guideline', 'Government document')) AS gov_docs,
                      (SELECT count(DISTINCT s) FROM (SELECT unnest(states) AS s FROM evidence_item WHERE land_score >= 4))
                          AS states_covered
               FROM evidence_item WHERE land_score >= 4""")
    contrib = q("SELECT status, count(*) AS n FROM contribution GROUP BY 1")
    return {
        "kpis": [kpi("Evidence items", k["items"], "items", "Repository", "Land-relevant items (relevance score >= 4)"),
                 kpi("Research papers", k["papers"], "papers", "OpenAlex", "Scholarly works on 30 land-governance topics"),
                 kpi("Case studies", k["case_studies"], "cases", "Land Conflict Watch", "Documented land conflicts"),
                 kpi("Government & legal documents", k["gov_docs"], "documents", "DoLR, DST, NRSC", "Acts, guidelines, reports"),
                 kpi("States with research", k["states_covered"], "states/UTs", "Repository", "Mentioned in at least one item")],
        "by_year": rows("""SELECT year, count(*) AS n FROM evidence_item WHERE land_score >= 4 AND source = 'openalex'
                           AND year BETWEEN 1990 AND year(current_date) GROUP BY 1 ORDER BY 1"""),
        "by_type": rows("SELECT type_group AS key, count(*) AS n FROM evidence_item WHERE land_score >= 4 GROUP BY 1 ORDER BY 2 DESC"),
        "by_state": rows("""SELECT s AS key, count(*) AS n FROM (SELECT unnest(states) AS s FROM evidence_item
                            WHERE land_score >= 4 AND source <> 'landconflictwatch') GROUP BY 1 ORDER BY 2 DESC"""),
        "contributions": contrib,
    }


@router.get("/policy-performance")
def policy_performance():
    t = one("""SELECT sum(land_parcels) AS parcels, sum(ulpin_assigned) AS ulpin, sum(ror_total) AS ror,
                      sum(ror_computerised) AS ror_c, sum(sro_total) AS sro, sum(sro_online) AS sro_on
               FROM dilrmp_state""")
    return {
        "kpis": [kpi("Records of Rights computerised", round(100 * t["ror_c"] / t["ror"], 2), "%", "DILRMP-MIS",
                     "Computerised RoR / total RoR"),
                 kpi("Parcels with ULPIN", round(100 * t["ulpin"] / t["parcels"], 2), "%", "DILRMP-MIS",
                     "Parcels assigned a Unique Land Parcel ID / total parcels"),
                 kpi("SROs registering online", round(100 * t["sro_on"] / t["sro"], 1), "%", "DILRMP-MIS",
                     "Sub-Registrar Offices using online registration")],
        "states": rows("""SELECT dilrmp_name AS state, ror_pct, maps_digitised_pct, georef_pct, ulpin_pct,
                                 round(100.0 * sro_online / nullif(sro_total, 0), 1) AS sro_online_pct
                          FROM dilrmp_state ORDER BY ulpin_pct DESC NULLS LAST"""),
        "insight": "Digitisation is near-universal, but ULPIN and geo-referencing vary from 0% to 100% by state: "
                   "the difference between 'digitised' and 'integrated'.",
    }


@router.get("/land-use")
def land_use(state: str | None = None):
    def nat(ind):
        return rows("""SELECT i.year, round(100 * sum(i.value * g.area_km2) / sum(g.area_km2), 2) AS pct
                       FROM indicator i JOIN geo_district g USING (district_lgd)
                       WHERE indicator = ? AND (? IS NULL OR g.state_name = upper(?)) GROUP BY 1 ORDER BY 1""",
                    [ind, state, state])
    built = rows("""SELECT i.year, round(sum(i.value)) AS km2, any_value(i.label) AS label FROM indicator i
                    JOIN geo_district g USING (district_lgd) WHERE indicator = 'ghsl_built_km2'
                    AND (? IS NULL OR g.state_name = upper(?)) GROUP BY 1 ORDER BY 1""", [state, state])
    return {"area": state or "India",
            "cropland_share_modis": nat("modis_cropland"), "forest_share_modis": nat("modis_forest"),
            "cropland_share_dw": nat("dw_crops"), "built_share_dw": nat("dw_built"), "trees_share_dw": nat("dw_trees"),
            "built_up_km2_ghsl": built,
            "top_cropland_loss": rows("""SELECT g.name, g.state_name, round(value, 1) AS pp FROM district_metric
                JOIN geo_district g USING (district_lgd) WHERE metric = 'crops_change_2017_2025'
                AND (? IS NULL OR g.state_name = upper(?)) ORDER BY value LIMIT 10""", [state, state]),
            "labels": {"satellite": "ESTIMATED", "ghsl_2025_2030": "PREDICTED"},
            "sources": "Dynamic World (2017-2025), MODIS MCD12Q1 (2001-2023), GHSL built-up (1975-2030)"}


@router.get("/climate")
def climate(state: str | None = None):
    rain = rows("""SELECT i.year, round(sum(i.value * g.area_km2) / sum(g.area_km2)) AS mm FROM indicator i
                   JOIN geo_district g USING (district_lgd) WHERE indicator = 'chirps_rain_mm'
                   AND (? IS NULL OR g.state_name = upper(?)) GROUP BY 1 ORDER BY 1""", [state, state])
    risk = rows("""SELECT g.name, g.state_name, g.district_lgd, value AS index FROM district_metric
                   JOIN geo_district g USING (district_lgd) WHERE metric = 'climate_risk_index'
                   AND (? IS NULL OR g.state_name = upper(?)) ORDER BY value DESC LIMIT 15""", [state, state])
    tree = rows("""SELECT i.year, round(avg(i.value), 2) AS pct FROM indicator i JOIN geo_district g USING (district_lgd)
                   WHERE indicator = 'vcf_mean' AND (? IS NULL OR g.state_name = upper(?)) GROUP BY 1 ORDER BY 1""", [state, state])
    atlas = rows("SELECT evidence_id, title FROM evidence_item WHERE source = 'wasteland_atlas' ORDER BY title")
    return {"area": state or "India", "rainfall_mm": rain, "tree_cover_pct": tree, "highest_risk_districts": risk,
            "exposure": rows("""SELECT m.name, count(*) AS districts_exposed, round(sum(d.value)) AS total
                                FROM district_metric d JOIN metric_meta m USING (metric)
                                WHERE metric IN ('landslides', 'earthquakes_m4') GROUP BY 1"""),
            "wastelands_atlas": atlas,
            "method": "Climate-risk index = mean percentile of rainfall variability, flood exposure, landslides, low "
                      "tree cover (screening index, ESTIMATED)."}


@router.get("/disputes")
def disputes():
    t = one("""SELECT count(*) AS n, sum(people_affected) AS people, sum(land_area_ha) AS ha,
                      count(*) FILTER (WHERE NOT ended) AS ongoing, sum(investment_crore) AS inv FROM land_conflict""")
    return {
        "kpis": [kpi("Documented land conflicts", t["n"], "conflicts", "Land Conflict Watch", "Cases documented by LCW"),
                 kpi("People affected", t["people"], "persons", "Land Conflict Watch", "As reported per case"),
                 kpi("Land affected", round(t["ha"] or 0), "ha", "Land Conflict Watch", "As reported per case"),
                 kpi("Ongoing", t["ongoing"], "conflicts", "Land Conflict Watch", "Conflict not reported as ended"),
                 kpi("Investment involved", round(t["inv"] or 0), "Rs crore", "Land Conflict Watch", "Where reported")],
        "by_sector": rows("""SELECT sector AS key, count(*) AS n, sum(people_affected) AS people FROM land_conflict
                             WHERE sector <> '' GROUP BY 1 ORDER BY 2 DESC"""),
        "by_state": rows("""SELECT soi_state AS key, count(*) AS n, sum(people_affected) AS people FROM land_conflict
                            WHERE soi_state IS NOT NULL GROUP BY 1 ORDER BY 2 DESC"""),
        "by_start_year": rows("""SELECT year_started::INTEGER AS year, count(*) AS n FROM land_conflict
                                 WHERE year_started BETWEEN 1990 AND year(current_date) GROUP BY 1 ORDER BY 1"""),
        "by_cause": rows("""SELECT cause AS key, count(*) AS n FROM land_conflict WHERE cause <> '' GROUP BY 1
                            ORDER BY 2 DESC LIMIT 12"""),
        "by_land_type": rows("""SELECT lt AS key, count(*) AS n FROM (SELECT unnest(string_split(land_type, '; ')) AS lt
                                FROM land_conflict WHERE land_type <> '') GROUP BY 1 ORDER BY 2 DESC LIMIT 8"""),
        "note": "Documented cases only; court disputes (revenue and civil) need RCCMS / eCourts data.",
    }


@router.get("/project-outcomes")
def project_outcomes():
    proj = one("""SELECT count(*) FILTER (WHERE project_status LIKE '%stalled%') AS stalled,
                         count(*) FILTER (WHERE project_status LIKE '%Delayed; Yes%' OR project_status LIKE '%delayed%') AS delayed,
                         count(*) FILTER (WHERE investment_crore IS NOT NULL) AS with_inv,
                         sum(investment_crore) FILTER (WHERE project_status LIKE '%stalled%') AS stalled_inv
                  FROM land_conflict""")
    pilots = q("""SELECT p.id, p.title, p.state, p.status, count(o.id) AS outcomes FROM pilot p
                  LEFT JOIN outcome o ON o.pilot_id = p.id GROUP BY p.id ORDER BY p.id DESC""")
    outcomes = q("""SELECT o.*, p.title AS pilot FROM outcome o JOIN pilot p ON p.id = o.pilot_id ORDER BY o.id DESC LIMIT 20""")
    return {
        "kpis": [kpi("Projects stalled by land conflict", proj["stalled"], "projects", "Land Conflict Watch",
                     "Conflicts where the project was reported stalled"),
                 kpi("Investment in stalled projects", round(proj["stalled_inv"] or 0), "Rs crore", "Land Conflict Watch",
                     "Where investment was reported"),
                 kpi("Platform pilots", len(pilots), "pilots", "Innovation Portal", "Pilots registered on the platform")],
        "dilrmp_progress": rows("""SELECT dilrmp_name AS state, maps_digitised_pct, georef_pct, ulpin_pct FROM dilrmp_state
                                   ORDER BY ulpin_pct NULLS FIRST LIMIT 12"""),
        "pilots": pilots, "pilot_outcomes": outcomes,
    }


@router.get("/geospatial")
def geospatial():
    return {
        "hotspots_conflict": rows("""SELECT g.name, g.state_name, g.district_lgd, value AS conflicts FROM district_metric
                                     JOIN geo_district g USING (district_lgd) WHERE metric = 'conflicts' ORDER BY value DESC LIMIT 10"""),
        "urbanising_fast": rows("""SELECT g.name, g.state_name, g.district_lgd, round(value) AS pct FROM district_metric
                                   JOIN geo_district g USING (district_lgd) WHERE metric = 'built_growth_2000_2020'
                                   ORDER BY value DESC LIMIT 10"""),
        "pressure_overlap": rows("""
            SELECT g.name, g.state_name, g.district_lgd,
                   round(max(value) FILTER (WHERE metric = 'built_growth_2000_2020')) AS built_growth_pct,
                   round(max(value) FILTER (WHERE metric = 'crops_change_2017_2025'), 1) AS cropland_change_pp,
                   max(value) FILTER (WHERE metric = 'conflicts') AS conflicts
            FROM district_metric JOIN geo_district g USING (district_lgd) GROUP BY ALL
            HAVING built_growth_pct > 100 AND cropland_change_pp < -2 ORDER BY conflicts DESC NULLS LAST LIMIT 15"""),
        "method": "Pressure overlap = built-up grew >100% (2000-2020) AND cropland share fell >2 points (2017-2025).",
    }


@router.get("/overview")
def overview():
    """Home-page summary across all seven dashboards."""
    return {"research": research_outputs()["kpis"][:3], "policy": policy_performance()["kpis"],
            "disputes": disputes()["kpis"][:3],
            "land_use_latest": land_use()["cropland_share_dw"][-1:],
            "geospatial": geospatial()["pressure_overlap"][:5]}
