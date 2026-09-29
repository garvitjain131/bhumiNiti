"""Parcel-level land records (SYNTHETIC demo data) served under role-based views with anonymisation."""
from __future__ import annotations

import io

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from ..core.db import duck
from ..core.security import audit, can_access, current_user, require
from ..services import anonymize as an

def records(df) -> list[dict]:
    """DataFrame -> JSON-safe records (NaN/NaT -> null)."""
    return df.astype(object).where(df.notna(), None).to_dict("records")


router = APIRouter(prefix="/api/v1/records", tags=["land records (synthetic) & anonymisation"])
DATASET = "land_records_synthetic"


def _load(village: str | None = None, limit: int | None = None, offset: int = 0):
    sql = "SELECT * FROM land_record WHERE (? IS NULL OR village = ?) ORDER BY record_id"
    params: list = [village, village]
    if limit:
        sql += " LIMIT ? OFFSET ?"
        params += [limit, offset]
    return duck().execute(sql, params).fetchdf()


@router.get("/policy")
def policy(user: dict = Depends(current_user)):
    """What each role can see, and the anonymisation rules applied to bulk exports."""
    return {"dataset": DATASET, "synthetic": True,
            "note": "Real parcel geometry (Dhamtari cadastral map); owners, IDs and phones are generated and fake.",
            "your_role": user["role"], "your_access": {
                "aggregate": user["role"] != "public",
                "masked_records": can_access(user, DATASET),
                "anonymised_bulk_export": can_access(user, DATASET),
                "identified_records": user["role"] == "admin"},
            "rules": an.POLICY}


@router.get("/aggregate")
def aggregate(by: str = Query("village", pattern="^(village|land_class|social_category|tehsil)$"),
              user: dict = Depends(require("researcher"))):
    """Village-level (or other) summaries; cells under 5 records are suppressed. Any signed-in user."""
    df = duck().execute("SELECT * FROM land_record").fetchdf()
    audit(user, "records_aggregate", DATASET, {"by": by})
    return {"small_cell_threshold": an.SMALL_CELL, "rows": an.aggregate(df, by)}


@router.get("/browse")
def browse(village: str | None = None, view: str = Query("masked", pattern="^(masked|identified)$"),
           limit: int = Query(50, le=500), offset: int = 0, user: dict = Depends(require("researcher"))):
    """Record-by-record view. masked: officials or approved researchers. identified: admins only (audited)."""
    if view == "identified" and user["role"] != "admin":
        raise HTTPException(403, "identified records are confidential (admin only)")
    if not can_access(user, DATASET):
        raise HTTPException(403, "restricted dataset: submit an access request first")
    df = _load(village, limit, offset)
    out = df if view == "identified" else an.mask(df)
    audit(user, f"records_browse_{view}", DATASET, {"village": village, "rows": len(out), "offset": offset})
    return {"view": view, "synthetic": True, "rows": records(out.drop(columns=["lon", "lat"]))}


@router.get("/export")
def export(village: str | None = None, user: dict = Depends(require("researcher"))):
    """Bulk CSV for research: identifiers removed, pseudonymised, k-anonymous (k=5). Report in response headers."""
    if not can_access(user, DATASET):
        raise HTTPException(403, "restricted dataset: submit an access request first")
    out, report = an.anonymise(_load(village))
    audit(user, "records_export_anonymised", DATASET, {"village": village, **report})
    buf = io.StringIO()
    out.to_csv(buf, index=False)
    headers = {"Content-Disposition": "attachment; filename=land_records_anonymised_SYNTHETIC.csv",
               "X-Anonymisation-Report": str(report).replace("\n", " ")}
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv", headers=headers)


@router.get("/export/report")
def export_report(village: str | None = None, user: dict = Depends(require("researcher"))):
    """Preview what the anonymised export would contain (no data rows)."""
    if not can_access(user, DATASET):
        raise HTTPException(403, "restricted dataset: submit an access request first")
    out, report = an.anonymise(_load(village))
    return {"report": report, "columns": list(out.columns), "sample": records(out.head(5))}
