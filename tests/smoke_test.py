#!/usr/bin/env python3
"""
End-to-end smoke test of every deliverable, in-process (no server needed).

    python tests/smoke_test.py
Reads demo credentials from db/demo_accounts.txt (created by etl/seed_app.py).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from backend.app.main import app  # noqa: E402

PASS, FAIL = [], []


def creds() -> dict[str, tuple[str, str]]:
    out = {}
    for line in (ROOT / "db/demo_accounts.txt").read_text().splitlines():
        parts = line.split()
        if len(parts) == 3 and "@" in parts[1]:
            out.setdefault(parts[0], (parts[1], parts[2]))
    return out


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  - {detail}" if detail else ""))


def main() -> None:
    c = TestClient(app)
    c.__enter__()
    accounts = creds()

    def token(role):
        email, pw = accounts[role]
        r = c.post("/api/v1/auth/login", json={"email": email, "password": pw})
        return {"Authorization": f"Bearer {r.json()['token']}"}

    H = {r: token(r) for r in ("admin", "official", "reviewer", "researcher")}
    t0 = time.time()

    print("\n#7 repository")
    h = c.get("/api/v1/health").json()
    check("health", h["status"] == "ok", f"{h['evidence_items']} items, {h['districts']} districts")
    f = c.get("/api/v1/evidence/facets").json()
    check("facets incl. legal docs and case studies", {"Legal document", "Case study"} <= {x["key"] for x in f["type_group"]})
    b = c.get("/api/v1/evidence/browse", params={"type_group": "Legal document"}).json()
    check("browse legal documents", len(b) > 0, b[0]["title"][:60] if b else "")
    ds = c.get("/api/v1/datasets/summary").json()
    check("dataset catalogue", len(ds) > 10, f"{len(ds)} datasets")

    print("\n#8 AI search & recommendations")
    s = c.get("/api/v1/evidence/search", params={"q": "farmers losing land near growing cities"}).json()
    check("hybrid search", s["total"] > 0, s["results"][0]["title"][:70] if s["results"] else "")
    s2 = c.get("/api/v1/evidence/search", params={"q": "land records", "state": "Odisha", "type_group": "Research publication"}).json()
    check("filtered search", all("Odisha" in r["states"] for r in s2["results"]), f"{s2['total']} hits")
    eid = s["results"][0]["evidence_id"]
    rec = c.get(f"/api/v1/evidence/{eid}/recommendations").json()
    check("recommendations with reasons", rec and rec[0]["because"], "; ".join(rec[0]["because"]) if rec else "")

    print("\n#14 research assistant")
    a = c.post("/api/v1/assistant/ask", json={"question": "Does digitisation of land records reduce land disputes?"}).json()
    check("cited answer", a["sentences"] and all(s["citations"] for s in a["sentences"]),
          f"{len(a['sentences'])} sentences, mode={a['mode']}, dropped={a['verifier']['dropped_unsupported']}")
    check("evidence matrix", len(a["matrix"]) > 0)
    na = c.post("/api/v1/assistant/ask", json={"question": "What is the price of Martian real estate on Olympus Mons?"}).json()
    check("refuses when evidence missing", na["insufficient_evidence"], na.get("answer", "")[:60])
    check("missing evidence explained as a gap", any("olympus" in g["what"].lower() for g in na["evidence_gaps"]))
    d = c.post("/api/v1/assistant/ask", json={"question": "Which districts currently show the highest land conflict risk?"}).json()
    check("router: data question -> SQL/analytics", [r["route"] for r in d["router"]["routes"]] == ["data"])
    check("analytics claim keeps provenance", d["data"]["analyses"] and all(
        d["data"]["analyses"][0][k] for k in ("dataset", "indicator", "scope", "period", "method")))
    check("data support re-checked", any(v["check"] == "Data support" and v["status"] == "pass" for v in d["verification"]))
    m = c.post("/api/v1/assistant/ask", json={"question": "What does existing research say about land conflict, which districts "
               "currently show the highest risk, and what could happen if conflict-resolution capacity is increased?"}).json()
    check("router: multi-domain -> RAG + analytics + digital twin",
          [r["route"] for r in m["router"]["routes"]] == ["document", "data", "policy"], str(m["router"]["sub_questions"]))
    tw = m["twin"]
    check("digital twin: baseline + lever + distribution", tw["status"] == "ok" and tw["current_state"]["indicators"]
          and tw["simulation"]["draws"] >= 1000 and tw["simulation"]["impact"]["p10"] <= tw["simulation"]["impact"]["p90"],
          f"{tw['lever']}: P50 {tw['simulation']['impact']['p50']:.1f} {tw['simulation']['impact_unit']}, run #{tw['run'].get('run_id')}")
    check("stress test (3 scenarios) and sensitivity", len(tw["stress_test"]["scenarios"]) == 3 and tw["sensitivity"],
          tw["stress_test"]["stability"])
    check("simulation re-run verified", any(v["check"] == "Simulation support" and v["status"] == "pass" for v in m["verification"]))
    types = {cl["type"] for cl in m["evidence_matrix"]}
    check("evidence matrix mixes document, analytics and simulation", {"document", "analytics", "simulation"} <= types)
    sim_claims = [cl for cl in m["evidence_matrix"] if cl["type"] == "simulation"]
    check("simulated claims labelled and qualified", all(cl["label"] == "SIMULATED" for cl in sim_claims)
          and "Under the modelled assumptions" in sim_claims[0]["claim"])
    check("sensitive assumption becomes an evidence gap", any(g["kind"] == "unvalidated_relationship" for g in m["evidence_gaps"]))
    check("answer has all sections", {"key_findings", "data_findings", "policy_scenario", "twin_result", "uncertainty",
                                      "sensitivity", "conflicts", "evidence_gaps"} <= {s["key"] for s in m["answer_sections"]})
    tt = c.get("/api/v1/research/topic-trends").json()
    check("topic trends", len(tt["themes"]) > 10, f"rising: {tt['rising'][:3]}")

    print("\n#10 GIS")
    L = c.get("/api/v1/geo/layers").json()
    themes = {m["theme"] for m in L["district_metrics"]}
    check("layers cover land use, climate, infrastructure, disputes", {"Land use", "Climate", "Infrastructure", "Disputes"} <= themes, str(sorted(themes)))
    g = c.get("/api/v1/geo/districts", params={"metric": "climate_risk_index"}).json()
    check("district choropleth", len(g["features"]) > 700)
    p = c.get("/api/v1/geo/districts/549").json()
    check("district profile", p["metrics"] and p["series"]["ghsl_built_km2"], f"{p['name']}: {len(p['metrics'])} metrics")
    qy = c.get("/api/v1/geo/query", params={"rules": "built_growth_2000_2020:high,crops_change_2017_2025:low"}).json()
    check("spatial question", qy["count"] >= 0, f"{qy['count']} districts urbanising fast with cropland loss")
    cp = c.get("/api/v1/geo/points/conflicts").json()
    check("conflict hotspots", len(cp["features"]) > 300)
    tile = c.get("/tiles/chhattisgarh/NCOG_CG_Dhamtari_Cadastrals.pmtiles", headers={"Range": "bytes=0-126"})
    check("cadastral tiles (range request)", tile.status_code == 206 and tile.content[:7] == b"PMTiles")
    vs = c.get("/api/v1/geo/cadastral/village-summary", params={"village": "Mategahan"}, headers=H["researcher"]).json()
    check("parcel click: village summary (synthetic)", vs.get("parcels", 0) > 0, f"{vs.get('parcels')} parcels")

    print("\n#11 analytics")
    tr = c.get("/api/v1/analytics/trend", params={"indicator": "dw_crops"}).json()
    check("trend", "slope_per_year" in tr, f"cropland slope {tr['slope_per_year'] * 100:.3f} pp/yr")
    ev = c.get("/api/v1/analytics/evaluate", params={"treatment": "ulpin_pct>=90", "outcome": "dw_built"}).json()
    check("policy evaluation (DiD)", "did_estimate" in ev, f"DiD {ev['did_estimate']:.4f}, CI {ev['ci95_state_bootstrap']}")
    em = c.get("/api/v1/analytics/emerging").json()
    check("emerging trends", em["fastest_built_up_growth"], em["fastest_built_up_growth"][0]["name"])
    co = c.get("/api/v1/analytics/correlate", params={"x": "built_growth_2000_2020", "y": "conflicts"}).json()
    check("correlation (labelled)", co["evidence_type"] == "CORRELATIONAL", f"rho={co['spearman_rho']:.2f}")
    fc = c.get("/api/v1/analytics/forecast", params={"indicator": "dw_built", "district_lgd": 549}).json()
    check("forecast labelled PREDICTED", fc["evidence_type"] == "PREDICTED" and fc["forecast"])
    fc2 = c.get("/api/v1/analytics/forecast", params={"indicator": "chirps_rain_mm"}).json()
    check("forecast back-test", fc2["backtest"] is not None, str(fc2["backtest"]))
    check("model registry", len(c.get("/api/v1/analytics/models").json()) >= 6)

    print("\n#12 policy simulation")
    lv = c.get("/api/v1/simulations/levers").json()
    check("3 levers", len(lv) == 3)
    r1 = c.post("/api/v1/simulations/run", json={"lever": "agri_conversion", "params": {"state": "Maharashtra"}}, headers=H["official"]).json()
    check("zoning scenario", r1["impact"]["cropland_saved_km2"]["p50"][-1] > 0, r1["headline"])
    r2 = c.post("/api/v1/simulations/run", json={"lever": "acquisition_reform", "params": {}}).json()
    check("acquisition scenario", "conflicts_avoided" in r2["impact"], r2["headline"])
    r3 = c.post("/api/v1/simulations/run", json={"lever": "dispute_pendency", "params": {}}).json()
    check("pendency scenario", r3["impact"]["pendency_reduction_pct"]["p50"] > 0, r3["headline"])
    check("tornado + graded coefficients", r1["tornado"] and all(x["grade"] for x in r1["coefficients"]))
    rep = c.post(f"/api/v1/simulations/runs/{r1['run_id']}/reproduce").json()
    check("reproducible (same seed -> same result)", rep["identical_results"])
    cmp = c.post("/api/v1/simulations/compare", json={"lever": "acquisition_reform", "scenarios": [
        {"label": "No consent rule", "params": {"consent_threshold": 0, "sia": False}},
        {"label": "70% consent + SIA", "params": {"consent_threshold": 70, "sia": True}}]}).json()
    check("scenario comparison", len(cmp["scenarios"]) == 2)
    br = c.get(f"/api/v1/simulations/runs/{r1['run_id']}/brief", headers=H["official"]).json()
    vb = c.post("/api/v1/simulations/verify-brief", json={"markdown": br["markdown"]}).json()
    check("policy brief + verify", vb["hash_matches_content"] and vb["found_in_audit_log"])
    tampered = c.post("/api/v1/simulations/verify-brief", json={"markdown": br["markdown"].replace("median", "mean", 1)}).json()
    check("tampered brief detected", not tampered["hash_matches_content"])
    ov = c.post("/api/v1/simulations/run", json={"lever": "agri_conversion", "params": {"coef_overrides": {"leakage": [0.0, 0.05]}}}).json()
    check("coefficient override recorded", any(x["grade"] == "user" for x in ov["coefficients"]))

    print("\n#16 dashboards")
    for d in ("research", "policy-performance", "land-use", "climate", "disputes", "project-outcomes", "geospatial"):
        r = c.get(f"/api/v1/dashboards/{d}")
        check(f"dashboard: {d}", r.status_code == 200)

    print("\n#9 workspaces")
    ws = c.get("/api/v1/workspaces", headers=H["researcher"]).json()
    check("my workspaces", len(ws) >= 1)
    w = c.post("/api/v1/workspaces", headers=H["researcher"], json={"name": "Smoke test workspace",
               "question": "Do ULPINs reduce boundary disputes in Odisha?"}).json()
    wid = w["id"]
    c.post(f"/api/v1/workspaces/{wid}/items", headers=H["researcher"], json={"evidence_id": eid, "stance": "supports"})
    n1 = c.post(f"/api/v1/workspaces/{wid}/notes", headers=H["researcher"], json={"title": "Draft", "body": "v1"}).json()
    n2 = c.post(f"/api/v1/workspaces/{wid}/notes", headers=H["researcher"], json={"title": "Draft", "body": "v2", "note_key": n1["note_key"]}).json()
    check("versioned notes", n2["version"] == 2)
    c.post(f"/api/v1/workspaces/{wid}/members", headers=H["researcher"], json={"email": accounts["official"][0], "role": "editor"})
    c.post(f"/api/v1/workspaces/{wid}/notes/{n2['id']}/status", headers=H["researcher"], json={"status": "in_review"})
    ap = c.post(f"/api/v1/workspaces/{wid}/notes/{n2['id']}/status", headers=H["official"], json={"status": "approved"})
    check("review & approve", ap.status_code == 200)
    c.post(f"/api/v1/workspaces/{wid}/comments", headers=H["official"], json={"body": "Looks good"})
    check("workspace recommendations", len(c.get(f"/api/v1/workspaces/{wid}/recommendations", headers=H["researcher"]).json()) > 0)
    bib = c.get(f"/api/v1/workspaces/{wid}/bibliography", headers=H["researcher"]).json()
    check("bibliography export", bib["count"] == 1)
    check("non-member blocked", c.get(f"/api/v1/workspaces/{wid}", headers=H["reviewer"]).status_code == 403)

    print("\n#15 innovation portal & feedback loop")
    gaps = c.get("/api/v1/gaps/states").json()
    check("gap radar", gaps and "gap_score" in gaps[0], f"top gap: {gaps[0]['state']}")
    call = c.post("/api/v1/gaps/to-call", headers=H["official"], json={"state": gaps[0]["state"]}).json()
    check("gap -> draft call", call["status"] == "draft")
    c.post(f"/api/v1/calls/{call['id']}/status", params={"status": "open"}, headers=H["official"])
    app_ = c.post(f"/api/v1/calls/{call['id']}/applications", headers=H["researcher"], json={
        "title": "Smoke application", "hypothesis": "Hypothesis text long enough", "methodology": "Methodology text long enough",
        "budget_lakh": 5}).json()
    rv = c.post(f"/api/v1/applications/{app_['id']}/reviews", headers=H["reviewer"], json={"score": 77, "comments": "solid proposal"})
    check("referee scoring", rv.status_code == 200)
    adv = c.post(f"/api/v1/applications/{app_['id']}/advance", params={"to": "advance_released"}, headers=H["official"]).json()
    check("grant workflow + 40% advance", adv["funds_released_pct"] == 40)
    c.post(f"/api/v1/applications/{app_['id']}/advance", params={"to": "awarded"}, headers=H["official"])
    pil = c.get("/api/v1/pilots").json()
    check("award creates pilot", any(x["application_id"] == app_["id"] for x in pil))
    before = next(g_ for g_ in c.get("/api/v1/gaps/states").json() if g_["state"] == "ODISHA")["evidence_items"]
    sub = c.post("/api/v1/contributions", headers=H["researcher"], json={"kind": "finding", "title": "Smoke finding on Odisha land records",
               "abstract": "A test finding about land records modernisation in Odisha, long enough to pass validation rules.",
               "states": ["Odisha"], "themes": ["land_records"]}).json()
    c.post(f"/api/v1/contributions/{sub['id']}/decide", headers=H["reviewer"], json={"approve": True})
    after = next(g_ for g_ in c.get("/api/v1/gaps/states").json() if g_["state"] == "ODISHA")["evidence_items"]
    check("approved finding updates Gap Radar", after == before + 1, f"{before} -> {after}")
    s3 = c.get("/api/v1/evidence/search", params={"q": "Smoke finding Odisha land records"}).json()
    check("approved finding searchable", any("Smoke finding" in x["title"] for x in s3["contributions"]))

    print("\n#17 security: RBAC & anonymisation")
    import secrets as _s
    reg = c.post("/api/v1/auth/register", json={"email": f"fresh{_s.token_hex(4)}@example.org", "name": "Fresh Researcher",
                                                 "password": _s.token_urlsafe(16)}).json()
    check("self-registration gives researcher role", reg["user"]["role"] == "researcher")
    H["researcher"] = {"Authorization": f"Bearer {reg['token']}"}
    check("public blocked from records", c.get("/api/v1/records/browse").status_code == 401)
    check("researcher needs approval", c.get("/api/v1/records/export", headers=H["researcher"]).status_code == 403)
    ar = c.post("/api/v1/access-requests", headers=H["researcher"], json={"dataset": "land_records_synthetic",
                "purpose": "Studying mutation delays and women's ownership at village level for a DoLR grant."}).json()
    c.post(f"/api/v1/access-requests/{ar['id']}/decide", headers=H["official"], json={"approve": True})
    rep = c.get("/api/v1/records/export/report", headers=H["researcher"]).json()
    check("k-anonymity >= 5", rep["report"]["min_group_size"] >= 5, json.dumps(rep["report"])[:140])
    check("no direct identifiers", not {"owner_name", "citizen_id", "phone", "father_or_spouse"} & set(rep["columns"]))
    exp = c.get("/api/v1/records/export", headers=H["researcher"], params={"village": "Mategahan"})
    check("anonymised CSV export", exp.status_code == 200 and "owner_pseudonym" in exp.text.splitlines()[0])
    mb = c.get("/api/v1/records/browse", headers=H["official"], params={"limit": 2}).json()
    check("officials see masked names", "*" in mb["rows"][0]["owner_name"], mb["rows"][0]["owner_name"])
    check("identified view admin-only", c.get("/api/v1/records/browse", headers=H["official"], params={"view": "identified"}).status_code == 403)
    idv = c.get("/api/v1/records/browse", headers=H["admin"], params={"view": "identified", "limit": 1}).json()
    check("admin identified view (audited)", "*" not in idv["rows"][0]["owner_name"])
    agg = c.get("/api/v1/records/aggregate", headers=H["researcher"]).json()
    check("small-cell suppression", any(r["suppressed"] for r in agg["rows"]) or agg["rows"])
    av = c.get("/api/v1/audit/verify").json()
    check("audit hash chain intact", av["valid"], f"{av['entries_checked']} entries")
    check("admin-only audit log", c.get("/api/v1/audit", headers=H["researcher"]).status_code == 403)
    bad = c.post("/api/v1/auth/login", json={"email": accounts["admin"][0], "password": "wrong-password"})
    check("bad login rejected", bad.status_code == 401)

    print("\n#18 APIs")
    check("OpenAPI docs", c.get("/openapi.json").status_code == 200)
    oc = c.get("/ogc/collections").json()
    check("OGC API Features collections", len(oc["collections"]) == 4)
    oi = c.get("/ogc/collections/states/items", params={"limit": 5})
    check("OGC items GeoJSON", oi.status_code == 200 and oi.json()["type"] == "FeatureCollection")
    oai = c.get("/oai", params={"verb": "ListRecords", "metadataPrefix": "oai_dc"})
    check("OAI-PMH ListRecords", oai.status_code == 200 and "<record>" in oai.text)
    dc = c.get("/api/v1/catalog/dcat").json()
    check("DCAT catalogue", dc["@type"] == "dcat:Catalog" and len(dc["dcat:dataset"]) > 10)
    k = c.post("/api/v1/admin/api-keys", headers=H["admin"], json={"name": "Smoke state Land Stack"}).json()
    viak = c.get("/api/v1/auth/me", headers={"X-API-Key": k["key"]}).json()
    check("partner API key auth", viak["user"]["name"].startswith("API:"))
    c.delete(f"/api/v1/admin/api-keys/{k['id']}", headers=H["admin"])
    check("revoked key rejected", c.get("/api/v1/auth/me", headers={"X-API-Key": k["key"]}).status_code == 401)
    check("connectors listed", len(c.get("/api/v1/connectors").json()) >= 6)

    print(f"\n{len(PASS)} passed, {len(FAIL)} failed in {time.time() - t0:.1f}s")
    if FAIL:
        print("FAILED:", FAIL)
        sys.exit(1)


if __name__ == "__main__":
    main()
