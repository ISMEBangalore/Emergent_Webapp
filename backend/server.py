import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")  # must run before importing auth (reads env vars at import time)

from fastapi import APIRouter, Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket
from pydantic import BaseModel
from starlette.middleware.cors import CORSMiddleware

from auth import TokenData, bootstrap_admin, create_access_token, get_current_user, verify_password
from report_engine import DEFAULT_SETTINGS, compute_report, aggregate_reports
from apps_parser import parse_application_files
from application_insights import evaluate_alerts, merge_buckets, parse_insights, summarize_bucket
from verified_lead_analysis import build_funnel, extract_applicant_records, match_joined_students
from excel_export import build_workbook

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]
fs_bucket = AsyncIOMotorGridFSBucket(db)

app = FastAPI()
auth_router = APIRouter(prefix="/api/auth")
api_router = APIRouter(prefix="/api", dependencies=[Depends(get_current_user)])

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


async def _match_and_flag_joined(joined_bytes: bytes, rec_query: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Matches an uploaded 'final students who reported' file against every
    applicant_records row in scope (not just one report's) and flags the
    matches joined=True. Raises ValueError on a file it can't parse."""
    records = await db.applicant_records.find(rec_query or {}, {"app_no": 1}).to_list(50000)
    result = await asyncio.to_thread(match_joined_students, joined_bytes, records)
    matched_ids = result.pop("matched_ids", [])
    if matched_ids:
        await db.applicant_records.update_many({"_id": {"$in": matched_ids}}, {"$set": {"joined": True}})
    return result


async def _process(report_id: str, lead_bytes: bytes, app_files: List[bytes],
                   settings: Dict[str, Any], amount_spent: Dict[str, float],
                   additional_attributed: Dict[str, float],
                   preset_app_counts: Optional[Dict[str, Any]] = None,
                   date_range: Optional[Dict[str, str]] = None,
                   week_date: Optional[str] = None,
                   joined_bytes: Optional[bytes] = None):
    try:
        if preset_app_counts is not None:
            app_counts = preset_app_counts
            insight_buckets = None
            applicant_records = None
        else:
            app_counts = await asyncio.to_thread(parse_application_files, app_files, settings, date_range) if app_files else {}
            insight_buckets = await asyncio.to_thread(parse_insights, app_files, settings, date_range) if app_files else None
            applicant_records = await asyncio.to_thread(extract_applicant_records, app_files, settings, date_range) if app_files else None
        result = await asyncio.to_thread(
            compute_report, lead_bytes, settings, amount_spent, additional_attributed, app_counts, date_range
        )
        update = {"status": "ready", "result": result, "application_counts": app_counts.get("by_program", app_counts),
                 "kpis": _kpis(result), "date_range": date_range or {}, "updated_at": now_iso()}
        if insight_buckets is not None:
            update["insight_buckets"] = insight_buckets
        await db.reports.update_one({"id": report_id}, {"$set": update})
        # applicant_records lives in its own collection (not the report doc) so the Joined-
        # students upload can update individual records by _id without rewriting the report.
        await db.applicant_records.delete_many({"report_id": report_id})
        if applicant_records:
            await db.applicant_records.insert_many([
                {**r, "report_id": report_id, "week_date": week_date} for r in applicant_records
            ])
        if joined_bytes:
            # Matched against every applicant_records row seen so far, not just this
            # report's — a student can join weeks after the report that logged their
            # application. A bad joined-file shouldn't fail the report itself.
            try:
                await _match_and_flag_joined(joined_bytes)
            except Exception:
                logger.exception("joined-students matching failed for report %s", report_id)
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


@app.get("/api/health")
async def health():
    return {"status": "ok"}


class LoginIn(BaseModel):
    username: str
    password: str


@auth_router.post("/login")
async def login(payload: LoginIn):
    user = await db.users.find_one({"username": payload.username})
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(401, "Invalid username or password")
    token = create_access_token(user["username"])
    return {"access_token": token, "token_type": "bearer", "username": user["username"]}


@auth_router.get("/me")
async def me(current: TokenData = Depends(get_current_user)):
    return {"username": current.username}


@api_router.get("/")
async def root():
    return {"message": "CRM Weekly Report API"}


# ---------------- Settings ----------------
class SettingsIn(BaseModel):
    programs: Optional[List[str]] = None
    program_aliases: Optional[Dict[str, List[str]]] = None
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
    applications_payment_approved_only: Optional[bool] = None


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
    joined_file: Optional[UploadFile] = File(None),
):
    settings = await get_settings()
    lead_bytes = await lead_file.read()
    app_bytes = [await f.read() for f in (application_files or [])]
    joined_bytes = await joined_file.read() if joined_file is not None else None

    report_id = str(uuid.uuid4())
    date_range = {"start": lead_start_date or None, "end": lead_end_date or None}
    doc = {
        "id": report_id,
        "week_label": week_label,
        "week_date": week_date,
        "status": "processing",
        "source": "upload",
        "lead_filename": lead_file.filename,
        "application_filenames": [f.filename for f in (application_files or [])],
        "amount_spent": _parse_json_form(amount_spent),
        "additional_attributed": _parse_json_form(additional_attributed),
        "date_range": date_range,
        "settings": settings,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db.reports.insert_one(doc)
    # Crunching starts immediately on the bytes already in memory — it doesn't need the
    # GridFS copy. That copy only exists for the later "regenerate by date" feature, so
    # it's written in the background instead of making the user wait ~100MB of Atlas
    # writes before the report even starts processing.
    asyncio.create_task(_process(report_id, lead_bytes, app_bytes, settings,
                                 doc["amount_spent"], doc["additional_attributed"],
                                 date_range=date_range, week_date=week_date, joined_bytes=joined_bytes))
    asyncio.create_task(_store_source_files(report_id, lead_bytes, app_bytes))
    return {"id": report_id, "status": "processing"}


class RegenerateIn(BaseModel):
    start: Optional[str] = None
    end: Optional[str] = None


async def _read_gridfs(file_id: str) -> bytes:
    from bson import ObjectId
    stream = await fs_bucket.open_download_stream(ObjectId(file_id))
    return await stream.read()


async def _delete_gridfs_files(file_ids: List[str]) -> None:
    from bson import ObjectId
    for fid in file_ids:
        try:
            await fs_bucket.delete(ObjectId(fid))
        except Exception:
            pass


async def _store_source_files(report_id: str, lead_bytes: bytes, app_bytes: List[bytes]) -> None:
    """Backs up the raw uploaded files to GridFS for later /regenerate use.
    Runs independently of report processing — crunching never waits on this."""
    try:
        lead_fid = await fs_bucket.upload_from_stream(f"{report_id}_lead.xlsx", lead_bytes)
        app_fids = []
        for i, ab in enumerate(app_bytes):
            app_fids.append(await fs_bucket.upload_from_stream(f"{report_id}_app{i}.xlsx", ab))
        await db.reports.update_one(
            {"id": report_id},
            {"$set": {"lead_file_id": str(lead_fid), "app_file_ids": [str(x) for x in app_fids]}},
        )
        await _purge_old_source_files(report_id)
    except Exception:
        logger.exception("failed to store source files for report %s", report_id)


async def _purge_old_source_files(keep_report_id: str) -> None:
    """The free Atlas tier caps out at 512MB and a single lead+application
    upload can be ~100MB, so only the newest report's raw source files are
    kept in GridFS. Older reports keep their computed results but lose the
    ability to be re-sliced by date via /regenerate."""
    cursor = db.reports.find(
        {"id": {"$ne": keep_report_id}, "lead_file_id": {"$exists": True}},
        {"id": 1, "lead_file_id": 1, "app_file_ids": 1},
    )
    async for old in cursor:
        file_ids = [old["lead_file_id"]] + old.get("app_file_ids", [])
        await _delete_gridfs_files(file_ids)
        await db.reports.update_one(
            {"id": old["id"]},
            {"$unset": {"lead_file_id": "", "app_file_ids": ""}},
        )


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
                                 date_range=date_range, week_date=doc.get("week_date")))
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
                                 SAMPLE_AMOUNT, {},
                                 preset_app_counts={"by_program": SAMPLE_APP_COUNTS, "by_publisher": {},
                                                    "by_program_publisher": {}}))
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
async def export_cumulative(start: Optional[str] = None, end: Optional[str] = None, top_publishers: int = 0):
    doc = await _build_cumulative(start, end)
    data = await asyncio.to_thread(build_workbook, doc, top_publishers)
    return StreamingResponse(
        iter([data]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="report_range.xlsx"'},
    )


async def _build_insights(start: Optional[str] = None, end: Optional[str] = None) -> Dict[str, Any]:
    """Aggregates application_insights buckets across all stored reports whose
    week falls in range. Deliberately independent of any single week's report —
    the admission fee (the real conversion event this tracks) is often paid
    weeks after the application fee, in a different report cycle entirely."""
    start = _validate_date(start, "start")
    end = _validate_date(end, "end")
    if start and end and start > end:
        raise HTTPException(400, "start date must be on or before end date.")
    settings = await get_settings()
    programs = settings.get("programs", ["B.Com", "BBA", "PGDM"])
    reports = await db.reports.find(
        {"status": "ready", "insight_buckets": {"$exists": True}},
        {"_id": 0, "insight_buckets": 1, "week_date": 1},
    ).to_list(2000)

    def in_range(r):
        wd = r.get("week_date") or ""
        if start and wd < start:
            return False
        if end and wd > end:
            return False
        return True

    reports = [r for r in reports if in_range(r)]
    all_bucket = merge_buckets([r["insight_buckets"]["All"] for r in reports if r.get("insight_buckets", {}).get("All")])
    program_buckets = {
        p: merge_buckets([r["insight_buckets"][p] for r in reports if r.get("insight_buckets", {}).get(p)])
        for p in programs
    }
    summary = {"All": summarize_bucket(all_bucket)}
    for p in programs:
        summary[p] = summarize_bucket(program_buckets[p])
    return {
        "programs": programs,
        "summary": summary,
        "alerts": evaluate_alerts(all_bucket, program_buckets),
        "reports_included": len(reports),
        "date_range": {"start": start, "end": end},
    }


@api_router.get("/insights")
async def get_insights(start: Optional[str] = None, end: Optional[str] = None):
    return await _build_insights(start, end)


def _build_ai_prompt(data: Dict[str, Any]) -> str:
    s = data["summary"]["All"]
    lines = [
        "You are advising an admissions/marketing team at ISME Bangalore (a business school "
        "running PGDM and undergraduate programs). Below is aggregate, anonymized data — no "
        "individual student names or PII — computed from their payment-approved applications.",
        "",
        f"Payment-approved applications: {s['applications']}",
        f"Went on to pay the admission fee: {s['admission_paid']} ({s['admission_conversion_pct']}%)",
        f"12th-standard score average: {s['pct_12th_avg']} (n={s['pct_12th_sample_size']})",
        f"Discount coupon usage: {s['discount_usage_pct']}% of applications",
        "",
        "Publisher/channel quality (applications submitted -> payment-approved rate):",
    ]
    for row in s["publisher_quality"]:
        lines.append(f"  - {row['name']}: {row['total']} submitted, {row['approval_pct']}% approved")
    lines.append("")
    lines.append("Self-reported \"how did you hear about us\" (may differ from tracked channel above):")
    for row in s["self_reported_source"][:8]:
        lines.append(f"  - {row['name']}: {row['count']}")
    lines.append("")
    for label, key in [("Gender", "gender"), ("Father's occupation", "father_occupation"),
                       ("Mother's occupation", "mother_occupation"), ("Category", "category"),
                       ("Hostel requirement", "hostel"), ("Finance mode", "finance")]:
        lines.append(f"{label}: " + ", ".join(f"{r['name']}={r['count']}" for r in s[key][:6]))
    lines.append("")
    if data["alerts"]:
        lines.append("System-flagged critical items:")
        for a in data["alerts"]:
            lines.append(f"  - [{a['severity']}] {a['title']}: {a['message']}")
    lines.append("")
    lines.append(
        "Give concrete, specific recommendations under three sections: Marketing, Branding, and "
        "Sales/Counseling. Each should reference the actual numbers above, not generic advice. "
        "Keep it under 350 words total. End with a one-line \"Most urgent\" callout if one item "
        "clearly matters more than the rest. Reply in PLAIN TEXT only — no markdown, no # headers, "
        "no ** bold markers, no bullet characters. Use a section name on its own line followed by "
        "a colon, then plain sentences or hyphen-led lines underneath."
    )
    return "\n".join(lines)


@api_router.post("/insights/ai")
async def ai_insights(start: Optional[str] = None, end: Optional[str] = None):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(503, "AI Insight isn't configured yet — ANTHROPIC_API_KEY is missing.")
    data = await _build_insights(start, end)
    if not data["summary"]["All"]["applications"]:
        raise HTTPException(400, "No payment-approved applications in this range to analyze.")
    import anthropic
    prompt = _build_ai_prompt(data)
    ai_client = anthropic.Anthropic(api_key=api_key)
    try:
        msg = await asyncio.to_thread(
            ai_client.messages.create,
            model="claude-sonnet-5",
            max_tokens=1200,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        raise HTTPException(502, f"AI Insight request failed: {e}")
    text = "".join(getattr(b, "text", "") for b in msg.content)
    return {"insight": text}


@api_router.get("/reports/{report_id}")
async def get_report(report_id: str):
    doc = await db.reports.find_one({"id": report_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Report not found")
    return doc


@api_router.delete("/reports/{report_id}")
async def delete_report(report_id: str):
    doc = await db.reports.find_one({"id": report_id}, {"lead_file_id": 1, "app_file_ids": 1})
    if not doc:
        raise HTTPException(404, "Report not found")
    await db.reports.delete_one({"id": report_id})
    file_ids = ([doc["lead_file_id"]] if doc.get("lead_file_id") else []) + doc.get("app_file_ids", [])
    if file_ids:
        await _delete_gridfs_files(file_ids)
    await db.applicant_records.delete_many({"report_id": report_id})
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
async def export_report(report_id: str, top_publishers: int = 0):
    doc = await db.reports.find_one({"id": report_id}, {"_id": 0})
    if not doc or doc.get("status") != "ready":
        raise HTTPException(404, "Report not ready")
    data = await asyncio.to_thread(build_workbook, doc, top_publishers)
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


# ---------------- Saved Views (programs + date range) ----------------
class ViewIn(BaseModel):
    name: str
    programs: List[str] = []
    start: Optional[str] = None
    end: Optional[str] = None


@api_router.get("/views")
async def list_views():
    return await db.views.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)


@api_router.post("/views")
async def create_view(payload: ViewIn):
    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(400, "View name is required.")
    doc = {
        "id": str(uuid.uuid4()), "name": name, "programs": payload.programs or [],
        "start": _validate_date(payload.start, "start"), "end": _validate_date(payload.end, "end"),
        "created_at": now_iso(),
    }
    await db.views.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api_router.delete("/views/{view_id}")
async def delete_view(view_id: str):
    res = await db.views.delete_one({"id": view_id})
    if res.deleted_count == 0:
        raise HTTPException(404, "View not found")
    return {"deleted": True}


# ---------------- Verified Lead Analysis ----------------
async def _build_verified_lead_analysis(start: Optional[str] = None, end: Optional[str] = None) -> Dict[str, Any]:
    """Publisher x program funnel: Total Leads / Verified Leads (from each report's
    already-computed publisher_reports) summed against Application / Admission Fee
    Paid / Joined (from the applicant_records collection) for reports whose week
    falls in range. Always recomputed live from current data — never a frozen
    snapshot — so a saved season stays accurate as more weeks are uploaded into it."""
    start = _validate_date(start, "start")
    end = _validate_date(end, "end")
    if start and end and start > end:
        raise HTTPException(400, "start date must be on or before end date.")
    settings = await get_settings()
    programs = settings.get("programs", ["B.Com", "BBA", "PGDM"])

    reports = await db.reports.find(
        {"status": "ready", "result.publisher_reports": {"$exists": True}},
        {"_id": 0, "result.publisher_reports": 1, "week_date": 1},
    ).to_list(2000)

    def in_range(wd):
        wd = wd or ""
        if start and wd < start:
            return False
        if end and wd > end:
            return False
        return True

    reports = [r for r in reports if in_range(r.get("week_date"))]

    rec_query: Dict[str, Any] = {}
    wd_q: Dict[str, Any] = {}
    if start:
        wd_q["$gte"] = start
    if end:
        wd_q["$lte"] = end
    if wd_q:
        rec_query["week_date"] = wd_q
    records = await db.applicant_records.find(rec_query, {"_id": 0}).to_list(50000)

    funnel = await asyncio.to_thread(build_funnel, reports, records, programs)
    return {
        "programs": programs,
        "funnel": funnel,
        "reports_included": len(reports),
        "applications_included": len(records),
        "date_range": {"start": start, "end": end},
    }


@api_router.get("/verified-lead-analysis")
async def verified_lead_analysis(start: Optional[str] = None, end: Optional[str] = None):
    return await _build_verified_lead_analysis(start, end)


@api_router.post("/verified-lead-analysis/joined-upload")
async def upload_joined_students(
    file: UploadFile = File(...),
    start: Optional[str] = Form(None),
    end: Optional[str] = Form(None),
):
    """Marks applicant_records as joined by matching an uploaded 'final students
    who reported' file against Application No. The CRM's own Enrolment Status
    field isn't kept up to date, so it can't be trusted for this — this upload
    is the only source of truth for who actually joined."""
    start = _validate_date(start, "start")
    end = _validate_date(end, "end")
    upload_bytes = await file.read()

    rec_query: Dict[str, Any] = {}
    wd_q: Dict[str, Any] = {}
    if start:
        wd_q["$gte"] = start
    if end:
        wd_q["$lte"] = end
    if wd_q:
        rec_query["week_date"] = wd_q

    try:
        return await _match_and_flag_joined(upload_bytes, rec_query)
    except ValueError as e:
        raise HTTPException(400, str(e))


# ---------------- Seasons (named, live-recomputing Verified Lead Analysis ranges) ----------------
class SeasonIn(BaseModel):
    label: str
    start: Optional[str] = None
    end: Optional[str] = None


@api_router.get("/seasons")
async def list_seasons():
    return await db.seasons.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)


@api_router.post("/seasons")
async def create_season(payload: SeasonIn):
    label = (payload.label or "").strip()
    if not label:
        raise HTTPException(400, "Season label is required.")
    doc = {
        "id": str(uuid.uuid4()), "label": label,
        "start": _validate_date(payload.start, "start"), "end": _validate_date(payload.end, "end"),
        "created_at": now_iso(),
    }
    await db.seasons.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api_router.delete("/seasons/{season_id}")
async def delete_season(season_id: str):
    res = await db.seasons.delete_one({"id": season_id})
    if res.deleted_count == 0:
        raise HTTPException(404, "Season not found")
    return {"deleted": True}


@api_router.get("/seasons/{season_id}/verified-lead-analysis")
async def season_verified_lead_analysis(season_id: str):
    season = await db.seasons.find_one({"id": season_id}, {"_id": 0})
    if not season:
        raise HTTPException(404, "Season not found")
    data = await _build_verified_lead_analysis(season.get("start"), season.get("end"))
    data["season"] = season
    return data


app.include_router(auth_router)
app.include_router(api_router)

_cors_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]
if not _cors_origins:
    logger.warning("CORS_ORIGINS is not set — defaulting to http://localhost:3000 only.")
    _cors_origins = ["http://localhost:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_credentials=False,  # auth is via Bearer token, not cookies — no credentials needed
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],  # so the frontend can read the export filename
)


@app.on_event("startup")
async def bootstrap_on_startup():
    await bootstrap_admin(db)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
