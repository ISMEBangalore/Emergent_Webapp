"""Verified-Lead -> Application -> Admission -> Joined funnel, broken down by
publisher and program.

Two data sources feed this, on purpose kept separate:
  - Total Leads / Verified Leads come straight from each report's already-
    computed result.publisher_reports[program] (built by report_engine.py at
    upload time) — no need to reparse raw files.
  - Application / Admission Fee Paid / Joined come from a compact per-
    applicant index (see extract_applicant_records) stored in its own Mongo
    collection, keyed by Application No, so a later "final students who
    reported" upload can be matched against it by Application No or Name —
    the CRM's own Enrolment Status field isn't kept up to date, so it can't
    be trusted for "Joined"."""
from __future__ import annotations

import io
from typing import Any, Dict, List, Optional

import pandas as pd

from report_engine import _find_col, program_series, read_data_sheet

PROG_CANDS = ["Courses Preference", "Course Preference", "Course", "Programme", "Program"]
PUB_CANDS = ["Publisher", "Publisher Name"]
PAY_STATUS_CANDS = ["Payment Status", "Payment Approval Status", "Payment Approved"]
ADM_FEE_STATUS_CANDS = ["Admission Fee Status"]
APP_NO_CANDS = ["Application No", "Application Number", "Application No."]
NAME_CANDS = ["Registered Name", "Applicant Name", "Full Name", "Student Name", "Name"]
APP_DATE_CANDS = [
    "Registration Date", "User Registration Date", "Created On", "Application Date",
    "Created Date", "Payment Date", "Date",
]


def _norm(series: pd.Series) -> pd.Series:
    return series.astype("string").str.strip().str.upper().fillna("")


def _norm_name(series: pd.Series) -> pd.Series:
    # Collapse repeated internal whitespace so "JOHN  DOE" and "JOHN DOE" match.
    return _norm(series).str.replace(r"\s+", " ", regex=True)


def extract_applicant_records(files: List[bytes], settings: Dict[str, Any],
                              date_range: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    """One record per payment-approved application: the compact index that
    the funnel table and the later Joined-students matcher both read from."""
    programs = settings.get("programs", ["B.Com", "BBA", "PGDM"])
    program_aliases = settings.get("program_aliases") or {}
    date_range = date_range or {}
    d_start = (str(date_range.get("start") or "")).strip() or None
    d_end = (str(date_range.get("end") or "")).strip() or None

    records: List[Dict[str, Any]] = []

    for content in files:
        try:
            df = read_data_sheet(content)
        except Exception:
            continue
        if len(df) == 0:
            continue

        # Captured regardless of whether a date filter is active: this is each row's
        # real application date, used later to scope the Verified Lead Analysis funnel
        # by date even though the Applications file itself is a cumulative season-to-
        # date export re-uploaded every week (so a report's own week_date reflects
        # "last seen," not "when this application actually happened").
        col_date = _find_col(df, APP_DATE_CANDS, prefer_data=True)
        app_date = (pd.to_datetime(df[col_date], errors="coerce", dayfirst=True)
                   if col_date is not None else pd.Series([pd.NaT] * len(df), index=df.index))

        if (d_start or d_end) and col_date is not None:
            keep = pd.Series(True, index=df.index)
            if d_start:
                keep &= app_date >= pd.Timestamp(d_start)
            if d_end:
                keep &= app_date < (pd.Timestamp(d_end) + pd.Timedelta(days=1))
            keep = keep.fillna(False)
            df = df[keep].reset_index(drop=True)
            app_date = app_date[keep].reset_index(drop=True)
            if len(df) == 0:
                continue

        col_pay = _find_col(df, PAY_STATUS_CANDS, prefer_data=True)
        if col_pay is None:
            continue
        paid = df[col_pay].astype("string").str.strip().str.upper().eq("PAYMENT APPROVED").fillna(False)
        df = df[paid].reset_index(drop=True)
        if len(df) == 0:
            continue

        col_appno = _find_col(df, APP_NO_CANDS, prefer_data=True)
        col_name = _find_col(df, NAME_CANDS, prefer_data=True)
        if col_appno is None and col_name is None:
            continue  # nothing to match a Joined-students list against

        lut = {c.strip().lower(): c for c in df.columns}
        prog = None
        best_matched = -1
        for cand in PROG_CANDS:
            col = lut.get(cand.strip().lower())
            if col is None or not df[col].notna().any():
                continue
            ps = program_series(df[col], programs, program_aliases)
            matched = int(ps.notna().sum())
            if matched > best_matched:
                best_matched, prog = matched, ps
        if prog is None:
            prog = pd.Series([None] * len(df), index=df.index)

        col_pub = _find_col(df, PUB_CANDS, prefer_data=True)
        publisher = _norm(df[col_pub]) if col_pub is not None else pd.Series(["UNKNOWN"] * len(df), index=df.index)
        publisher = publisher.where(publisher != "", "UNKNOWN")

        col_adm = _find_col(df, ADM_FEE_STATUS_CANDS, prefer_data=True)
        admitted = (df[col_adm].astype("string").str.strip().str.upper().eq("PAID").fillna(False)
                   if col_adm is not None else pd.Series(False, index=df.index))

        app_no = _norm(df[col_appno]) if col_appno is not None else pd.Series([""] * len(df), index=df.index)
        name = _norm_name(df[col_name]) if col_name is not None else pd.Series([""] * len(df), index=df.index)

        for i in range(len(df)):
            p = prog.values[i]
            if p is None:
                continue
            ts = app_date.iloc[i]
            records.append({
                "app_no": app_no.iloc[i], "name": name.iloc[i],
                "publisher": publisher.iloc[i], "program": p,
                "admission_paid": bool(admitted.iloc[i]), "joined": False,
                "app_date": ts.strftime("%Y-%m-%d") if pd.notna(ts) else None,
            })

    return records


def _blank_row() -> Dict[str, Any]:
    return {"total_leads": 0, "verified_leads": 0, "application": 0, "admission_fee_paid": 0, "joined": 0}


def build_funnel(reports: List[Dict[str, Any]], applicant_records: List[Dict[str, Any]],
                 programs: List[str]) -> Dict[str, List[Dict[str, Any]]]:
    """reports: list of stored report docs (need .result.publisher_reports).
    applicant_records: rows from the applicant_records collection for the same range.
    Returns {program: [ {publisher, total_leads, verified_leads, application,
                         admission_fee_paid, joined}, ... ]}"""
    out: Dict[str, Dict[str, Dict[str, Any]]] = {p: {} for p in programs}

    for r in reports:
        pub_reports = ((r.get("result") or {}).get("publisher_reports") or {})
        for p in programs:
            pr = pub_reports.get(p)
            if not pr:
                continue
            summary = {s.get("label"): s for s in pr.get("summary", [])}
            total_row = summary.get("Total Leads", {}).get("values", {})
            verified_row = summary.get("Verified Leads", {}).get("values", {})
            for pub_name in pr.get("programs", []):  # publisher_reports uses "programs" as publisher columns
                row = out[p].setdefault(pub_name, _blank_row())
                row["total_leads"] += int(total_row.get(pub_name, 0) or 0)
                row["verified_leads"] += int(verified_row.get(pub_name, 0) or 0)

    for rec in applicant_records:
        p, pub = rec.get("program"), rec.get("publisher") or "UNKNOWN"
        if p not in out:
            continue
        row = out[p].setdefault(pub, _blank_row())
        row["application"] += 1
        if rec.get("admission_paid"):
            row["admission_fee_paid"] += 1
        if rec.get("joined"):
            row["joined"] += 1

    result: Dict[str, List[Dict[str, Any]]] = {}
    for p in programs:
        rows = [{"publisher": pub, **vals} for pub, vals in out[p].items()]
        rows.sort(key=lambda r: -r["application"])
        result[p] = rows
    return result


def _read_all_data_sheets(content: bytes) -> pd.DataFrame:
    """Joined-students exports sometimes split by program across separate sheets
    (e.g. 'BBA Joined' / 'B.Com Joined' in one workbook) instead of one flat
    list — concatenate every sheet that has an Application No or Name column,
    rather than picking just the largest one like read_data_sheet does."""
    frames = []
    xls = pd.ExcelFile(io.BytesIO(content), engine="calamine")
    for name in xls.sheet_names:
        sheet = xls.parse(name)
        if len(sheet) == 0:
            continue
        if _find_col(sheet, APP_NO_CANDS, prefer_data=True) is None and \
           _find_col(sheet, NAME_CANDS, prefer_data=True) is None:
            continue
        frames.append(sheet)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True, sort=False)


def match_joined_students(upload_bytes: bytes, records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Parses a 'final students who reported' file and marks matching
    applicant_records as joined, by Application No only. Name matching was
    tried as a fallback and dropped: a common first name (e.g. two different
    "ADITYA"s in different programs) can cross-match the wrong student, and
    Application No is reliably present and unique in this CRM's exports."""
    df = _read_all_data_sheets(upload_bytes)
    if len(df) == 0:
        raise ValueError("Couldn't find any usable rows in this file.")
    col_appno = _find_col(df, APP_NO_CANDS, prefer_data=True)
    if col_appno is None:
        raise ValueError("Couldn't find an Application No column in this file.")

    appnos = _norm(df[col_appno])
    by_appno = {r["app_no"]: r for r in records if r.get("app_no")}

    matched_ids: List[Any] = []
    matched_id_set = set()
    unmatched_by_appno = 0
    for app_no in appnos:
        r = by_appno.get(app_no) if app_no else None
        if r is None:
            unmatched_by_appno += 1
            continue
        if r["_id"] not in matched_id_set:
            matched_ids.append(r["_id"])
            matched_id_set.add(r["_id"])

    return {
        "matched_ids": matched_ids,
        "matched_count": len(matched_ids),
        "total_upload_rows": len(df),
        "unmatched_by_appno_count": unmatched_by_appno,
    }
