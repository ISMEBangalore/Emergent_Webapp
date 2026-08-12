import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket
from pydantic import BaseModel
from starlette.middleware.cors import CORSMiddleware

from report_engine import DEFAULT_SETTINGS, compute_report, aggregate_reports
from apps_parser import parse_application_files
from excel_export import build_workbook

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]
fs_bucket = AsyncIOMotorGridFSBucket(db)

app = FastAPI()
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("crm_report")

SAMPLE_LEADS = ROOT_DIR / "sample_data" / "sample_leads.xlsx"
SAMPLE_APP_COUNTS = {
    "B.Com": {"with_code": 3, "without_code": 5, "via_redirect": 4, "via_api": 4},
    "BBA": {"with_code": 10, "without_code": 25, "via_redirect": 11, "via_api": 24},
    "PGDM": {"with_code": 40, "without_code": 18, "via_redirect": 34, "via_api": 5},
}
SAMPLE_AMOUNT = {"B.Com": 387600, "BBA": 868800, "PGDM": 818900}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def get_settings() -> Dict[str, Any]:
    doc = await db.settings.find_one({"_id": "global"})
    if not doc:
        return dict(DEFAULT_SETTINGS)
    doc.pop("_id", None)
    return {**DEFAULT_SETTINGS, **doc}


def _kpis(result: Dict[str, Any]) -> Dict[str, Any]:
    programs = result["programs"]
    summ = {s["label"]: s for s in result["summary"] if "values" in s}
    total_leads = sum(result["matrix"][0]["values"].values()) if result["matrix"] else 0
    total_leads = summ.get("Total Leads", {}).get("total", 0)
    total_apps = summ.get("Total No. of Applications", {}).get("total", 0)
    amount = summ.get("Amount Spent", {}).get("total", 0)
    verified = summ.get("Verified Leads", {}).get("total", 0)
    return {
        "total_leads": total_leads,
        "total_applications": total_apps,
        "amount_spent": amount,
        "verified_leads": verified,
        "blended_cpa": round(amount / total_apps, 2) if total_apps else 0,
        "verified_pct": round(verified / total_leads * 100, 2) if total_leads else 0,
        "per_program": {p: result["matrix"] and summ.get("Total Leads", {}).get("values", {}).get(p, 0) for p in programs},
    }


async def _process(report_id: str, lead_bytes: bytes, app_files: List[bytes],
                   settings: Dict[str, Any], amount_spent: Dict[str, float],
                   additional_attributed: Dict[str, float],
                   preset_app_counts: Optional[Dict[str, Any]] = None,
                   date_range: Optional[Dict[str, str]] = None):
    try:
        if preset_app_counts is not None:
            app_counts = preset_app_counts
        else:
            app_counts = await asyncio.to_thread(parse_application_files, app_files, settings, date_range) if app_files else {}
        result = await asyncio.to_thread(
            compute_report, lead_bytes, settings, amount_spent, additional_attributed, app_counts, date_range
        )
        await db.reports.update_one(
            {"id": report_id},
            {"$set": {"status": "ready", "result": result, "application_counts": app_counts,
                      "kpis": _kpis(result), "date_range": date_range or {}, "updated_at": now_iso()}},
        )
    except Exception as e:  # noqa
        logger.exception("report processing failed")
        await db.reports.update_one(
            {"id": report_id},
            {"$set": {"status": "error", "error": str(e), "updated_at": now_iso()}},
        )


def _parse_json_form(raw: Optional[str]) -> Dict[str, Any]:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


@api_router.get("/")
async def root():
    return {"message": "CRM Weekly Report API"}


# ---------------- Settings ----------------
class SettingsIn(BaseModel):
    programs: Optional[List[str]] = None
    verified_logic: Optional[str] = None
    relevant_stages: Optional[List[str]] = None
    api_patterns: Optional[List[str]] = None
    redirect_patterns: Optional[List[str]] = None
    application_code_field: Optional[str] = None
    application_code_field_apps: Optional[str] = None
    exclude_test_leads: Optional[bool] = None
    test_keywords: Optional[List[str]] = None
    excluded_publishers: Optional[List[str]] = None
    included_publishers: Optional[List[str]] = None


@api_router.get("/settings")
async def read_settings():
    return await get_settings()


@api_router.put("/settings")
async def update_settings(payload: SettingsIn):
    update = {k: v for k, v in payload.model_dump().items() if v is not None}
    await db.settings.update_one({"_id": "global"}, {"$set": update}, upsert=True)
    return await get_settings()


@api_router.get("/available")
async def available_dimensions():
    """Courses and Publishers detected in the latest uploaded report (falls back to
    any latest ready report). Reflects the file the user is actually working with."""
    proj = {"_id": 0, "result.data_quality.available_courses": 1,
            "result.data_quality.available_publishers": 1}
    doc = await db.reports.find_one({"status": "ready", "source": "upload"}, proj,
                                    sort=[("created_at", -1)])
    if not doc:
        doc = await db.reports.find_one({"status": "ready"}, proj, sort=[("created_at", -1)])
    dq = ((doc or {}).get("result") or {}).get("data_quality") or {}
    return {
        "courses": dq.get("available_courses", []) or [],
        "publishers": dq.get("available_publishers", []) or [],
    }


# ---------------- Reports ----------------
@api_router.post("/reports")
async def create_report(
    week_label: str = Form(...),
    week_date: str = Form(...),
    amount_spent: str = Form("{}"),
    additional_attributed: str = Form("{}"),
    lead_start_date: str = Form(""),
    lead_end_date: str = Form(""),
    lead_file: UploadFile = File(...),
    application_files: List[UploadFile] = File(default=[]),
):
    settings = await get_settings()
    lead_bytes = await lead_file.read()
    app_bytes = [await f.read() for f in (application_files or [])]

    report_id = str(uuid.uuid4())
    # Persist raw files in GridFS so the report can be re-sliced by date later.
    lead_fid = await fs_bucket.upload_from_stream(f"{report_id}_lead.xlsx", lead_bytes)
    app_fids = []
    for i, ab in enumerate(app_bytes):
        app_fids.append(await fs_bucket.upload_from_stream(f"{report_id}_app{i}.xlsx", ab))
    date_range = {"start": lead_start_date or None, "end": lead_end_date or None}
    doc = {
        "id": report_id,
        "week_label": week_label,
        "week_date": week_date,
        "status": "processing",
        "source": "upload",
        "lead_filename": lead_file.filename,
        "application_filenames": [f.filename for f in (application_files or [])],
        "lead_file_id": str(lead_fid),
        "app_file_ids": [str(x) for x in app_fids],
        "amount_spent": _parse_json_form(amount_spent),
        "additional_attributed": _parse_json_form(additional_attributed),
        "date_range": date_range,
        "settings": settings,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db.reports.insert_one(doc)
    asyncio.create_task(_process(report_id, lead_bytes, app_bytes, settings,
                                 doc["amount_spent"], doc["additional_attributed"],
                                 date_range=date_range))
    return {"id": report_id, "status": "processing"}


class RegenerateIn(BaseModel):
    start: Optional[str] = None
    end: Optional[str] = None


async def _read_gridfs(file_id: str) -> bytes:
    from bson import ObjectId
    stream = await fs_bucket.open_download_stream(ObjectId(file_id))
    return await stream.read()


@api_router.post("/reports/{report_id}/regenerate")
async def regenerate_report(report_id: str, payload: RegenerateIn):
    doc = await db.reports.find_one({"id": report_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Report not found")
    if not doc.get("lead_file_id"):
        raise HTTPException(400, "This report has no stored source file (e.g. sample). Re-upload to slice by date.")
    settings = await get_settings()
    lead_bytes = await _read_gridfs(doc["lead_file_id"])
    app_bytes = [await _read_gridfs(fid) for fid in doc.get("app_file_ids", [])]
    date_range = {"start": payload.start or None, "end": payload.end or None}
    await db.reports.update_one({"id": report_id},
                                {"$set": {"status": "processing", "settings": settings,
                                          "date_range": date_range, "updated_at": now_iso()}})
    asyncio.create_task(_process(report_id, lead_bytes, app_bytes, settings,
                                 doc.get("amount_spent", {}), doc.get("additional_attributed", {}),
                                 date_range=date_range))
    return {"id": report_id, "status": "processing"}


@api_router.post("/reports/sample")
async def create_sample_report():
    settings = await get_settings()
    lead_bytes = SAMPLE_LEADS.read_bytes()
    report_id = str(uuid.uuid4())
    label = f"Sample Week — {datetime.now(timezone.utc).strftime('%d %b %Y')}"
    doc = {
        "id": report_id, "week_label": label,
        "week_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "status": "processing", "source": "sample",
        "lead_filename": "sample_leads.xlsx", "application_filenames": [],
        "amount_spent": SAMPLE_AMOUNT, "additional_attributed": {},
        "settings": settings, "created_at": now_iso(), "updated_at": now_iso(),
    }
    await db.reports.insert_one(doc)
    asyncio.create_task(_process(report_id, lead_bytes, [], settings,
                                 SAMPLE_AMOUNT, {}, preset_app_counts=SAMPLE_APP_COUNTS))
    return {"id": report_id, "status": "processing"}


@api_router.get("/reports")
async def list_reports():
    cursor = db.reports.find(
        {}, {"_id": 0, "result": 0, "settings": 0}
    ).sort("created_at", -1)
    return await cursor.to_list(500)


def _validate_date(value: Optional[str], field: str) -> Optional[str]:
    if value is None or value == "":
        return None
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(400, f"Invalid {field} date '{value}'. Use YYYY-MM-DD.")
    return value


async def _build_cumulative(start: Optional[str] = None, end: Optional[str] = None):
    start = _validate_date(start, "start")
    end = _validate_date(end, "end")
    if start and end and start > end:
        raise HTTPException(400, "start date must be on or before end date.")
    settings = await get_settings()
    reports = await db.reports.find({"status": "ready"}, {"_id": 0}).to_list(2000)

    def in_range(r):
        wd = r.get("week_date") or ""
        if start and wd < start:
            return False
        if end and wd > end:
            return False
        return True

    reports = [r for r in reports if in_range(r)]
    result = await asyncio.to_thread(aggregate_reports, reports, settings)
    weeks = result.get("data_quality", {}).get("weeks_aggregated", 0)
    if start or end:
        rng = f"{start or 'start'} to {end or 'today'}"
        label = f"Custom Report — {rng} ({weeks} week{'s' if weeks != 1 else ''})"
    else:
        label = f"Report Till Date ({weeks} week{'s' if weeks != 1 else ''})"
    doc = {
        "id": "cumulative",
        "week_label": label,
        "week_date": now_iso()[:10],
        "status": "ready",
        "source": "cumulative",
        "lead_filename": f"{weeks} reports aggregated",
        "range": {"start": start, "end": end},
        "result": result,
        "kpis": _kpis(result),
    }
    return doc


@api_router.get("/reports/cumulative")
async def cumulative_report(start: Optional[str] = None, end: Optional[str] = None):
    return await _build_cumulative(start, end)


@api_router.get("/reports/cumulative/export")
async def export_cumulative(start: Optional[str] = None, end: Optional[str] = None):
    doc = await _build_cumulative(start, end)
    data = await asyncio.to_thread(build_workbook, doc)
    return StreamingResponse(
        iter([data]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="report_range.xlsx"'},
    )


@api_router.get("/reports/{report_id}")
async def get_report(report_id: str):
    doc = await db.reports.find_one({"id": report_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Report not found")
    return doc


@api_router.delete("/reports/{report_id}")
async def delete_report(report_id: str):
    res = await db.reports.delete_one({"id": report_id})
    if res.deleted_count == 0:
        raise HTTPException(404, "Report not found")
    return {"deleted": True}


class AmountUpdate(BaseModel):
    amount_spent: Dict[str, float] = {}
    additional_attributed: Dict[str, float] = {}


@api_router.patch("/reports/{report_id}/amounts")
async def update_amounts(report_id: str, payload: AmountUpdate):
    doc = await db.reports.find_one({"id": report_id}, {"_id": 0})
    if not doc or doc.get("status") != "ready":
        raise HTTPException(404, "Report not ready")
    result = doc["result"]
    settings = doc.get("settings", DEFAULT_SETTINGS)
    programs = result["programs"]
    # recompute only the money rows from existing counts
    summ = {s["label"]: s for s in result["summary"]}
    total_apps = {p: summ["Total No. of Applications"]["values"][p] for p in programs}
    spent = {p: float(payload.amount_spent.get(p, 0) or 0) for p in programs}
    add_attr = {p: float(payload.additional_attributed.get(p, 0) or 0) for p in programs}
    summ["Amount Spent"]["values"] = spent
    summ["Amount Spent"]["total"] = round(sum(spent.values()), 2)
    summ["Cost/Application"]["values"] = {p: round(spent[p] / total_apps[p], 2) if total_apps[p] else 0 for p in programs}
    summ["Cost/Application"]["total"] = round(sum(spent.values()) / sum(total_apps.values()), 2) if sum(total_apps.values()) else 0
    summ["Additional Attributed Applications"]["values"] = add_attr
    summ["Additional Attributed Applications"]["total"] = round(sum(add_attr.values()), 2)
    summ["Modified CPA after attribution"]["values"] = {
        p: round(spent[p] / (total_apps[p] + add_attr[p]), 2) if (total_apps[p] + add_attr[p]) else 0 for p in programs}
    denom = sum(total_apps.values()) + sum(add_attr.values())
    summ["Modified CPA after attribution"]["total"] = round(sum(spent.values()) / denom, 2) if denom else 0
    await db.reports.update_one(
        {"id": report_id},
        {"$set": {"result": result, "amount_spent": spent, "additional_attributed": add_attr,
                  "kpis": _kpis(result), "updated_at": now_iso()}},
    )
    return await db.reports.find_one({"id": report_id}, {"_id": 0})


class PublisherAmountUpdate(BaseModel):
    amount_spent: Dict[str, float] = {}
    cpa: Dict[str, float] = {}


@api_router.patch("/reports/{report_id}/publisher-amounts")
async def update_publisher_amounts(report_id: str, payload: PublisherAmountUpdate):
    doc = await db.reports.find_one({"id": report_id}, {"_id": 0})
    if not doc or doc.get("status") != "ready":
        raise HTTPException(404, "Report not ready")
    result = doc["result"]
    pr = result.get("publisher_report")
    if not pr:
        raise HTTPException(400, "No publisher report available")
    cols = pr["programs"]
    summ = {s["label"]: s for s in pr["summary"]}
    total_apps = {c: summ["Total No. of Applications"]["values"].get(c, 0) for c in cols}
    spent = {}
    for c in cols:
        amt = float(payload.amount_spent.get(c, 0) or 0)
        cpa = float(payload.cpa.get(c, 0) or 0)
        spent[c] = amt if amt > 0 else round(cpa * total_apps[c], 2)
    summ["Amount Spent"]["values"] = spent
    summ["Amount Spent"]["total"] = round(sum(spent.values()), 2)
    cost = {c: round(spent[c] / total_apps[c], 2) if total_apps[c] else 0 for c in cols}
    summ["Cost/Application"]["values"] = cost
    summ["Cost/Application"]["total"] = round(sum(spent.values()) / sum(total_apps.values()), 2) if sum(total_apps.values()) else 0
    summ["Modified CPA after attribution"]["values"] = cost
    summ["Modified CPA after attribution"]["total"] = summ["Cost/Application"]["total"]
    result["publisher_report"] = pr
    if isinstance(result.get("publisher_reports"), dict):
        result["publisher_reports"]["All"] = pr
    await db.reports.update_one(
        {"id": report_id},
        {"$set": {"result": result, "publisher_amount_spent": payload.amount_spent,
                  "publisher_cpa": payload.cpa, "updated_at": now_iso()}},
    )
    return await db.reports.find_one({"id": report_id}, {"_id": 0})


@api_router.get("/reports/{report_id}/export")
async def export_report(report_id: str):
    doc = await db.reports.find_one({"id": report_id}, {"_id": 0})
    if not doc or doc.get("status") != "ready":
        raise HTTPException(404, "Report not ready")
    data = await asyncio.to_thread(build_workbook, doc)
    raw = (doc.get("week_label") or "report").replace(" ", "_")[:40]
    fname = "".join(ch for ch in raw if ord(ch) < 128) or "report"
    fname += ".xlsx"
    return StreamingResponse(
        iter([data]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@api_router.get("/trends")
async def trends():
    cursor = db.reports.find({"status": "ready"}, {"_id": 0, "id": 1, "week_label": 1,
                             "week_date": 1, "kpis": 1, "created_at": 1}).sort("week_date", 1)
    return await cursor.to_list(500)


app.include_router(api_router)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
