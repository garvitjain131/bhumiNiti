"""
Integration APIs (#18): OGC API - Features (GIS systems such as QGIS, Bhuvan-style portals), OAI-PMH
(research databases and institutional repositories harvest our metadata), DCAT catalogue (data.gov.in-style
dataset registries), and connector stubs documenting how Land Stack / DILRMP-MIS / data.gov.in plug in.
"""
from __future__ import annotations

import datetime as dt
import json
from xml.sax.saxutils import escape

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, Response

from ..core.db import feature_collection, rows

router = APIRouter(tags=["integration APIs (OGC, OAI-PMH, DCAT)"])

COLLECTIONS = {
    "districts": ("District boundaries (Survey of India) with LGD codes",
                  "SELECT ST_AsGeoJSON(geom_simple) AS gj, district_lgd, name, state_name, round(area_km2) AS area_km2 "
                  "FROM geo_district WHERE NOT is_disputed"),
    "states": ("State boundaries with DILRMP progress",
               "SELECT ST_AsGeoJSON(s.geom_simple) AS gj, s.state_lgd, s.name, d.ulpin_pct, d.georef_pct "
               "FROM geo_state s LEFT JOIN dilrmp_state d ON d.soi_state_name = s.name"),
    "land-conflicts": ("Land conflicts aggregated at district centroids (Land Conflict Watch)",
                       "SELECT ST_AsGeoJSON(ST_Centroid(g.geom_simple)) AS gj, g.district_lgd, g.name AS district, "
                       "count(*) AS conflicts, sum(c.people_affected) AS people_affected FROM land_conflict c "
                       "JOIN geo_district g USING (district_lgd) GROUP BY ALL"),
    "district-metrics": ("District metrics (land use change, climate exposure, conflicts) in wide format",
                         "SELECT ST_AsGeoJSON(g.geom_simple) AS gj, g.district_lgd, g.name, g.state_name, "
                         "map_from_entries(list(struct_pack(k := metric, v := value))) AS metrics FROM district_metric d "
                         "JOIN geo_district g USING (district_lgd) GROUP BY ALL"),
}


def _base(req: Request) -> str:
    return str(req.base_url).rstrip("/")


@router.get("/ogc")
def ogc_landing(request: Request):
    b = _base(request)
    return {"title": "LPIP OGC API - Features", "links": [
        {"href": f"{b}/ogc/conformance", "rel": "conformance"}, {"href": f"{b}/ogc/collections", "rel": "data"},
        {"href": f"{b}/openapi.json", "rel": "service-desc", "type": "application/vnd.oai.openapi+json;version=3.0"}]}


@router.get("/ogc/conformance")
def ogc_conformance():
    return {"conformsTo": ["http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/core",
                           "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/geojson"]}


@router.get("/ogc/collections")
def ogc_collections(request: Request):
    b = _base(request)
    return {"collections": [{"id": k, "title": v[0], "extent": {"spatial": {"bbox": [[68, 6, 98, 38]]}},
                             "links": [{"href": f"{b}/ogc/collections/{k}/items", "rel": "items",
                                        "type": "application/geo+json"}]} for k, v in COLLECTIONS.items()]}


@router.get("/ogc/collections/{cid}/items")
def ogc_items(cid: str, limit: int = Query(1000, le=5000), offset: int = 0, bbox: str | None = None):
    if cid not in COLLECTIONS:
        raise HTTPException(404, "collection not found")
    sql = COLLECTIONS[cid][1]
    fc = feature_collection(f"SELECT * FROM ({sql}) LIMIT {int(limit)} OFFSET {int(offset)}")
    if bbox:
        x0, y0, x1, y1 = (float(v) for v in bbox.split(","))

        def inside(f):
            g = f["geometry"]
            if not g:
                return False
            flat = json.dumps(g["coordinates"])
            nums = [float(n) for n in flat.replace("[", " ").replace("]", " ").replace(",", " ").split()]
            xs, ys = nums[0::2], nums[1::2]
            return not (max(xs) < x0 or min(xs) > x1 or max(ys) < y0 or min(ys) > y1)
        fc["features"] = [f for f in fc["features"] if inside(f)]
    for f in fc["features"]:
        for k, v in list(f["properties"].items()):
            if isinstance(v, dict):
                f["properties"][k] = {str(a): b for a, b in v.items()}
    fc["numberReturned"] = len(fc["features"])
    return JSONResponse(jsonable_encoder(fc), media_type="application/geo+json")


# --------------------------------------------------------------------------- OAI-PMH (Dublin Core)

@router.get("/oai")
def oai(verb: str, metadataPrefix: str = "oai_dc", identifier: str | None = None,
        resumptionToken: str | None = None, set: str | None = None):
    """OAI-PMH 2.0 subset: Identify, ListMetadataFormats, ListSets, ListRecords, GetRecord (oai_dc)."""
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    head = (f'<?xml version="1.0" encoding="UTF-8"?><OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/">'
            f"<responseDate>{now}</responseDate><request verb=\"{escape(verb)}\">/oai</request>")

    def rec(r):
        dc = "".join(f"<dc:{t}>{escape(str(v))}</dc:{t}>" for t, v in
                     [("title", r["title"]), ("date", r["year"]), ("type", r["type_group"]),
                      ("publisher", r["source_org"]), ("identifier", r["doi"] or r["url"]),
                      ("description", (r["abstract"] or "")[:1000])] if v)
        dc += "".join(f"<dc:creator>{escape(a)}</dc:creator>" for a in (r["authors"] or [])[:10])
        dc += "".join(f"<dc:coverage>{escape(s)}</dc:coverage>" for s in (r["states"] or []))
        return (f"<record><header><identifier>oai:lpip:{escape(r['evidence_id'])}</identifier><datestamp>"
                f"{r['year'] or 1900}-01-01</datestamp><setSpec>{escape(r['type_group'])}</setSpec></header><metadata>"
                f'<oai_dc:dc xmlns:oai_dc="http://www.openarchives.org/OAI/2.0/oai_dc/" '
                f'xmlns:dc="http://purl.org/dc/elements/1.1/">{dc}</oai_dc:dc></metadata></record>')

    if verb == "Identify":
        body = ("<Identify><repositoryName>Land Policy Intelligence Platform</repositoryName><baseURL>/oai</baseURL>"
                "<protocolVersion>2.0</protocolVersion><earliestDatestamp>1900-01-01</earliestDatestamp>"
                "<deletedRecord>no</deletedRecord><granularity>YYYY-MM-DD</granularity></Identify>")
    elif verb == "ListMetadataFormats":
        body = ("<ListMetadataFormats><metadataFormat><metadataPrefix>oai_dc</metadataPrefix>"
                "<schema>http://www.openarchives.org/OAI/2.0/oai_dc.xsd</schema>"
                "<metadataNamespace>http://www.openarchives.org/OAI/2.0/oai_dc/</metadataNamespace></metadataFormat></ListMetadataFormats>")
    elif verb == "ListSets":
        body = "<ListSets>" + "".join(f"<set><setSpec>{escape(r['k'])}</setSpec><setName>{escape(r['k'])}</setName></set>"
                                      for r in rows("SELECT DISTINCT type_group AS k FROM evidence_item")) + "</ListSets>"
    elif verb in ("ListRecords", "GetRecord"):
        if metadataPrefix != "oai_dc":
            body = '<error code="cannotDisseminateFormat">only oai_dc</error>'
        elif verb == "GetRecord":
            r = rows("SELECT * FROM evidence_item WHERE evidence_id = ?", [(identifier or "").replace("oai:lpip:", "")])
            body = f"<GetRecord>{rec(r[0])}</GetRecord>" if r else '<error code="idDoesNotExist"/>'
        else:
            off = int(resumptionToken or 0)
            rs = rows("SELECT * FROM evidence_item WHERE land_score >= 4 AND (? IS NULL OR type_group = ?) "
                      "ORDER BY evidence_id LIMIT 100 OFFSET ?", [set, set, off])
            tok = f"<resumptionToken>{off + 100}</resumptionToken>" if len(rs) == 100 else "<resumptionToken/>"
            body = "<ListRecords>" + "".join(rec(r) for r in rs) + tok + "</ListRecords>"
    else:
        body = '<error code="badVerb">unsupported verb</error>'
    return Response(head + body + "</OAI-PMH>", media_type="text/xml")


# --------------------------------------------------------------------------- DCAT catalogue

@router.get("/api/v1/catalog/dcat")
def dcat(request: Request):
    """Dataset catalogue as DCAT (JSON-LD): the format data.gov.in-style registries and EU/US portals exchange."""
    b = _base(request)
    ds = rows("""SELECT job, count(*) AS files, round(sum(MB), 1) AS mb, any_value(license) AS license,
                        any_value(prd_modules) AS used_for, max(retrieved_at) AS modified, any_value(url) AS sample_url
                 FROM catalog GROUP BY 1 ORDER BY 1""")
    return JSONResponse(jsonable_encoder({
        "@context": {"dcat": "http://www.w3.org/ns/dcat#", "dct": "http://purl.org/dc/terms/"},
        "@type": "dcat:Catalog", "dct:title": "Land Policy Intelligence Platform - dataset catalogue",
        "dcat:dataset": [{"@type": "dcat:Dataset", "@id": f"{b}/api/v1/datasets?job={d['job']}", "dct:identifier": d["job"],
                          "dct:title": d["job"].replace("_", " "), "dct:description": d["used_for"],
                          "dct:license": d["license"], "dct:modified": d["modified"], "dct:spatial": "India",
                          "dcat:distribution": [{"@type": "dcat:Distribution", "dcat:accessURL": d["sample_url"],
                                                 "dcat:byteSize": int((d["mb"] or 0) * 1e6)}]} for d in ds]}),
        media_type="application/ld+json")


@router.get("/api/v1/connectors")
def connectors():
    """How external systems plug in. 'live' connectors run today; 'stub' ones define the contract."""
    return [
        {"id": "dilrmp-mis", "system": "DILRMP-MIS (DoLR)", "status": "live", "direction": "pull",
         "data": "state physical progress (RoR, maps, ULPIN, SRO)", "how": "pipelines/fetch.py job dilrmp_progress"},
        {"id": "data-gov-in", "system": "Open Government Data (data.gov.in)", "status": "ready (needs API key)",
         "direction": "pull", "data": "any resource ID", "how": "DATAGOV_API_KEY + pipelines/datagov_resources.txt"},
        {"id": "land-stack", "system": "State Land Stacks / Bhu-Aadhaar (ULPIN)", "status": "stub", "direction": "pull",
         "data": "district-aggregated parcel statistics (never personal data)",
         "contract": {"endpoint": "GET {state_land_stack}/aggregates?lgd_district={code}",
                      "fields": ["parcels", "ulpin_assigned", "mutations_pending", "disputes_pending"],
                      "auth": "mutual TLS + API key", "privacy": "aggregates only; small cells suppressed at source"}},
        {"id": "rccms", "system": "Revenue Court Case Management System", "status": "stub", "direction": "pull",
         "data": "filings and disposals per court per month", "use": "calibrates the pendency simulator"},
        {"id": "bhuvan", "system": "Bhuvan (NRSC) WMS", "status": "display", "direction": "pull",
         "data": "land use / land cover layers shown directly in the map client"},
        {"id": "earth-engine", "system": "Google Earth Engine", "status": "live", "direction": "pull",
         "data": "district x year satellite indicators", "how": "pipelines/gee_district_indicators.py"},
        {"id": "oai-pmh", "system": "Research repositories (Shodhganga, institutional DSpace)", "status": "live",
         "direction": "push (harvestable)", "how": "/oai?verb=ListRecords&metadataPrefix=oai_dc"},
        {"id": "ogc", "system": "GIS systems (QGIS, ArcGIS, state GIS portals)", "status": "live",
         "direction": "push (queryable)", "how": "/ogc/collections"},
    ]
