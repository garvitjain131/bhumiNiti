"""
Land Policy Intelligence Platform - API.

    uvicorn backend.app.main:app --port 8000        (from the project root)
    docs: http://localhost:8000/docs
"""
from __future__ import annotations

from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .core.config import CORS_ORIGINS, DATA, RATE_LIMIT_PER_MIN
from .core.db import init_app_db, one, rows
from .core.security import rate_limited
from .routers import (analytics, auth, dashboards, evidence, geo, innovation, interop, records, simulate,
                      workspaces)
from .services import search

app = FastAPI(
    title="Land Policy Intelligence Platform API", version="1.0.0",
    description="National platform for land-governance research and policy innovation (SIH26019): repository, "
                "AI search, GIS, analytics, policy simulation, workspaces, innovation portal, secure access, open APIs.")
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"], expose_headers=["X-Anonymisation-Report"])


@app.middleware("http")
async def limits(request: Request, call_next):
    if request.url.path.startswith(("/api", "/ogc", "/oai")) and rate_limited(request, RATE_LIMIT_PER_MIN):
        return JSONResponse({"detail": "rate limit exceeded; slow down or use an API key"}, status_code=429)
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return resp


@app.on_event("startup")
def startup():
    init_app_db()


for r in (auth, evidence, geo, analytics, dashboards, simulate, workspaces, innovation, records, interop):
    app.include_router(r.router)

# map tiles (PMTiles need HTTP range requests; StaticFiles supports them)
if (DATA / "cadastral").exists():
    app.mount("/tiles", StaticFiles(directory=DATA / "cadastral"), name="tiles")


@app.get("/api/v1/health", tags=["system"])
def health():
    return {"status": "ok",
            "districts": one("SELECT count(*) AS n FROM geo_district WHERE NOT is_disputed")["n"],
            "indicator_observations": one("SELECT count(*) AS n FROM indicator")["n"],
            "evidence_items": one("SELECT count(*) AS n FROM evidence_item")["n"],
            "land_conflicts": one("SELECT count(*) AS n FROM land_conflict")["n"],
            "datasets_catalogued": one("SELECT count(*) AS n FROM catalog")["n"],
            "semantic_search": search.semantic_available()}


@app.get("/api/v1/disputes", tags=["dashboards"])
def disputes(state: str | None = Query(None, description="SOI state name, e.g. 'ODISHA'"),
             district_lgd: int | None = None, sector: str | None = None,
             limit: int = Query(50, le=500), offset: int = 0):
    """Documented land conflicts (Land Conflict Watch), newest first."""
    return rows("""
        SELECT url, title, soi_state AS state, district, district_lgd, year_started, people_affected,
               households_affected, land_area_ha, investment_crore, sector, cause, land_type, legal_status, ended,
               substr(summary, 1, 400) AS summary
        FROM land_conflict
        WHERE (? IS NULL OR soi_state = upper(?)) AND (? IS NULL OR district_lgd = ?) AND (? IS NULL OR sector = ?)
        ORDER BY year_started DESC NULLS LAST LIMIT ? OFFSET ?""",
                [state, state, district_lgd, district_lgd, sector, sector, limit, offset])
