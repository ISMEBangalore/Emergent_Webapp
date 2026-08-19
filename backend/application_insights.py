"""Demographic/academic/funnel insights from Application dumps, scoped to the
payment-approved (application-fee-paid) applicant pool. Deliberately separate
from apps_parser.py / report_engine.py: this data isn't tied to a single
week's report — the admission fee (the real conversion event) is typically
paid weeks or months after the application fee, in a later report cycle
entirely, so it's aggregated across ALL stored reports on its own page
rather than folded into any one week's numbers."""
from __future__ import annotations

import re
from typing import Any, Dict, List

import pandas as pd

from report_engine import _find_col, program_series, read_data_sheet

PROG_CANDS = ["Courses Preference", "Course Preference", "Course", "Programme", "Program"]
PUB_CANDS = ["Publisher", "Publisher Name"]
PAY_STATUS_CANDS = ["Payment Status", "Payment Approval Status", "Payment Approved"]
APP_DATE_CANDS = [
    "Registration Date", "User Registration Date", "Created On", "Application Date",
    "Created Date", "Payment Date", "Date",
]
GENDER_CANDS = ["Gender"]
FATHER_OCC_CANDS = ["Fathers Occupation", "Father Occupation", "Father's Occupation"]
MOTHER_OCC_CANDS = ["Mothers Occupation", "Mother Occupation", "Mother's Occupation"]
CATEGORY_CANDS = ["Category"]
ADM_FEE_STATUS_CANDS = ["Admission Fee Status"]
PCT_12TH_CANDS = ["12th - Obtained Percentage/CGPA"]
BOARD_12TH_CANDS = ["12th - Board"]
HOSTEL_CANDS = ["Hostel Requirement"]
FINANCE_CANDS = ["Finance"]
SOURCE_INFO_CANDS = ["Source Of Information On ISME, Bangalore", "Source Of Information"]
CODE_CANDS = [
    "Discount Coupon", "Coupon Code", "Coupon", "Applied Coupon", "Coupon Applied",
    "Promo Code", "Promocode", "Discount Code", "Referral Code", "Referral Coupon", "Code",
]
# For the discount-coupon field specifically, "NO"/"0" mean "no code used" and
# count as blank. Do NOT reuse this for general categorical fields (Hostel
# Requirement, Finance, etc.) where "NO" is a legitimate answer, not junk.
CODE_BLANK_TOKENS = {"", "NA", "N/A", "NAN", "NONE", "NULL", "0", "-", "NO", "NIL"}
GENERIC_BLANK_TOKENS = {"", "NA", "N/A", "NAN", "NONE", "NULL", "-"}

TOP_N = 10


def _norm(series: pd.Series) -> pd.Series:
    """Uppercase/trim, and collapse the CRM's 'OTHER|<freeform text>' pattern
    down to a single OTHER bucket instead of a long tail of one-offs."""
    v = series.astype("string").str.strip().str.upper().fillna("")
    v = v.mask(v.isin(GENERIC_BLANK_TOKENS), "")
    v = v.where(~v.str.startswith("OTHER|", na=False), "OTHER")
    return v


def _counter(target: Dict[str, int], series: pd.Series) -> None:
    for name, n in series.value_counts().items():
        if name:
            target[name] = target.get(name, 0) + int(n)


def _blank_bucket() -> Dict[str, Any]:
    return {
        "applications": 0, "admission_paid": 0,
        "gender": {}, "father_occupation": {}, "mother_occupation": {}, "category": {},
        "board_12th": {}, "hostel": {}, "finance": {}, "self_reported_source": {},
        "tracked_publisher": {}, "discount_used": 0, "discount_total": 0,
        "pct_12th_sum": 0.0, "pct_12th_count": 0,
        # Publisher quality (approval RATE) needs the full applicant pool, not
        # just the payment-approved subset every other field here is scoped to.
        "publisher_totals": {}, "publisher_approved": {},
    }


def parse_insights(files: List[bytes], settings: Dict[str, Any],
                   date_range: Dict[str, Any] = None) -> Dict[str, Any]:
    """Returns {program_or_'All': bucket} — see _blank_bucket() for the shape.
    Every dimension is scoped to Payment-Approved (application-fee-paid) rows."""
    programs = settings.get("programs", ["B.Com", "BBA", "PGDM"])
    program_aliases = settings.get("program_aliases") or {}
    date_range = date_range or {}
    d_start = (str(date_range.get("start") or "")).strip() or None
    d_end = (str(date_range.get("end") or "")).strip() or None

    buckets: Dict[str, Dict[str, Any]] = {"All": _blank_bucket()}
    for p in programs:
        buckets[p] = _blank_bucket()

    for content in files:
        try:
            df = read_data_sheet(content)
        except Exception:
            continue
        if len(df) == 0:
            continue

        if d_start or d_end:
            col_date = _find_col(df, APP_DATE_CANDS, prefer_data=True)
            if col_date is not None:
                parsed = pd.to_datetime(df[col_date], errors="coerce", dayfirst=True)
                keep = pd.Series(True, index=df.index)
                if d_start:
                    keep &= parsed >= pd.Timestamp(d_start)
                if d_end:
                    keep &= parsed < (pd.Timestamp(d_end) + pd.Timedelta(days=1))
                df = df[keep.fillna(False)].reset_index(drop=True)
                if len(df) == 0:
                    continue

        col_pay = _find_col(df, PAY_STATUS_CANDS, prefer_data=True)
        if col_pay is None:
            continue  # can't tell what's actually converted; skip the file
        paid = df[col_pay].astype("string").str.strip().str.upper().eq("PAYMENT APPROVED").fillna(False)

        # Program classification on the FULL pool (before the payment-approved
        # filter below) so publisher approval RATE can be broken out per program,
        # not just overall.
        lut = {c.strip().lower(): c for c in df.columns}
        prog_all = None
        best_matched = -1
        for cand in PROG_CANDS:
            col = lut.get(cand.strip().lower())
            if col is None or not df[col].notna().any():
                continue
            ps = program_series(df[col], programs, program_aliases)
            matched = int(ps.notna().sum())
            if matched > best_matched:
                best_matched, prog_all = matched, ps
        if prog_all is None:
            prog_all = pd.Series([None] * len(df), index=df.index)

        col_pub_all = _find_col(df, PUB_CANDS, prefer_data=True)
        if col_pub_all is not None:
            pub_all = _norm(df[col_pub_all])
            _counter(buckets["All"]["publisher_totals"], pub_all)
            _counter(buckets["All"]["publisher_approved"], pub_all[paid])
            for p in programs:
                pmask = prog_all.values == p
                _counter(buckets[p]["publisher_totals"], pub_all[pmask])
                _counter(buckets[p]["publisher_approved"], pub_all[pmask & paid.values])

        prog = prog_all[paid].reset_index(drop=True)
        df = df[paid].reset_index(drop=True)
        if len(df) == 0:
            continue

        col_adm = _find_col(df, ADM_FEE_STATUS_CANDS, prefer_data=True)
        admitted = (df[col_adm].astype("string").str.strip().str.upper().eq("PAID").fillna(False)
                   if col_adm is not None else pd.Series(False, index=df.index))

        col_gender = _find_col(df, GENDER_CANDS, prefer_data=True)
        gender = _norm(df[col_gender]) if col_gender is not None else pd.Series([""] * len(df), index=df.index)
        col_fo = _find_col(df, FATHER_OCC_CANDS, prefer_data=True)
        father_occ = _norm(df[col_fo]) if col_fo is not None else pd.Series([""] * len(df), index=df.index)
        col_mo = _find_col(df, MOTHER_OCC_CANDS, prefer_data=True)
        mother_occ = _norm(df[col_mo]) if col_mo is not None else pd.Series([""] * len(df), index=df.index)
        col_cat = _find_col(df, CATEGORY_CANDS, prefer_data=True)
        category = _norm(df[col_cat]) if col_cat is not None else pd.Series([""] * len(df), index=df.index)
        col_board = _find_col(df, BOARD_12TH_CANDS, prefer_data=True)
        board = _norm(df[col_board]) if col_board is not None else pd.Series([""] * len(df), index=df.index)
        col_hostel = _find_col(df, HOSTEL_CANDS, prefer_data=True)
        hostel = _norm(df[col_hostel]) if col_hostel is not None else pd.Series([""] * len(df), index=df.index)
        col_fin = _find_col(df, FINANCE_CANDS, prefer_data=True)
        finance = _norm(df[col_fin]) if col_fin is not None else pd.Series([""] * len(df), index=df.index)
        col_src = _find_col(df, SOURCE_INFO_CANDS, prefer_data=True)
        source = _norm(df[col_src]) if col_src is not None else pd.Series([""] * len(df), index=df.index)
        col_pub = _find_col(df, PUB_CANDS, prefer_data=True)
        publisher = _norm(df[col_pub]) if col_pub is not None else pd.Series([""] * len(df), index=df.index)
        col_code = _find_col(df, CODE_CANDS, prefer_data=True)
        has_code = (~df[col_code].astype("string").str.strip().str.upper().fillna("").isin(CODE_BLANK_TOKENS)
                   if col_code is not None else pd.Series(False, index=df.index))
        col_pct = _find_col(df, PCT_12TH_CANDS, prefer_data=True)
        pct_12th = pd.to_numeric(df[col_pct], errors="coerce") if col_pct is not None else pd.Series([None] * len(df))
        # A handful of CRM entries put the percentile/other junk in this field —
        # values outside a plausible 12th-standard percentage range are dropped.
        pct_12th = pct_12th.where((pct_12th >= 20) & (pct_12th <= 100))

        def _bump(bucket: Dict[str, Any], mask: pd.Series) -> None:
            bucket["applications"] += int(mask.sum())
            bucket["admission_paid"] += int((mask & admitted).sum())
            _counter(bucket["gender"], gender[mask])
            _counter(bucket["father_occupation"], father_occ[mask])
            _counter(bucket["mother_occupation"], mother_occ[mask])
            _counter(bucket["category"], category[mask])
            _counter(bucket["board_12th"], board[mask])
            _counter(bucket["hostel"], hostel[mask])
            _counter(bucket["finance"], finance[mask])
            _counter(bucket["self_reported_source"], source[mask])
            _counter(bucket["tracked_publisher"], publisher[mask])
            bucket["discount_used"] += int((mask & has_code).sum())
            bucket["discount_total"] += int(mask.sum())
            valid_pct = pct_12th[mask].dropna()
            bucket["pct_12th_sum"] += float(valid_pct.sum())
            bucket["pct_12th_count"] += int(len(valid_pct))

        all_mask = pd.Series(True, index=df.index)
        _bump(buckets["All"], all_mask)
        for p in programs:
            _bump(buckets[p], prog.values == p)

    return buckets


def _top_n(d: Dict[str, int], n: int = TOP_N) -> List[Dict[str, Any]]:
    return [{"name": k, "count": v} for k, v in sorted(d.items(), key=lambda x: -x[1])[:n]]


def _publisher_quality(totals: Dict[str, int], approved: Dict[str, int], n: int = TOP_N) -> List[Dict[str, Any]]:
    rows = []
    for name, total in totals.items():
        app = approved.get(name, 0)
        rows.append({
            "name": name, "total": total, "approved": app,
            "approval_pct": round(app / total * 100, 2) if total else None,
        })
    return sorted(rows, key=lambda r: -r["total"])[:n]


def summarize_bucket(b: Dict[str, Any]) -> Dict[str, Any]:
    """Turn one raw accumulator bucket into the JSON shape the frontend renders."""
    apps = b["applications"]
    admitted = b["admission_paid"]
    return {
        "applications": apps,
        "admission_paid": admitted,
        "admission_conversion_pct": round(admitted / apps * 100, 2) if apps else None,
        "gender": _top_n(b["gender"]),
        "father_occupation": _top_n(b["father_occupation"]),
        "mother_occupation": _top_n(b["mother_occupation"]),
        "category": _top_n(b["category"]),
        "board_12th": _top_n(b["board_12th"]),
        "hostel": _top_n(b["hostel"]),
        "finance": _top_n(b["finance"]),
        "self_reported_source": _top_n(b["self_reported_source"]),
        "tracked_publisher": _top_n(b["tracked_publisher"]),
        "publisher_quality": _publisher_quality(b.get("publisher_totals", {}), b.get("publisher_approved", {})),
        "discount_used": b["discount_used"],
        "discount_total": b["discount_total"],
        "discount_usage_pct": round(b["discount_used"] / b["discount_total"] * 100, 2) if b["discount_total"] else None,
        "pct_12th_avg": round(b["pct_12th_sum"] / b["pct_12th_count"], 2) if b["pct_12th_count"] else None,
        "pct_12th_sample_size": b["pct_12th_count"],
    }


def merge_buckets(buckets: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Sum raw accumulator buckets (as returned by parse_insights) across reports."""
    out = _blank_bucket()
    for b in buckets:
        out["applications"] += b.get("applications", 0)
        out["admission_paid"] += b.get("admission_paid", 0)
        out["discount_used"] += b.get("discount_used", 0)
        out["discount_total"] += b.get("discount_total", 0)
        out["pct_12th_sum"] += b.get("pct_12th_sum", 0.0)
        out["pct_12th_count"] += b.get("pct_12th_count", 0)
        for key in ("gender", "father_occupation", "mother_occupation", "category",
                    "board_12th", "hostel", "finance", "self_reported_source", "tracked_publisher",
                    "publisher_totals", "publisher_approved"):
            for name, n in (b.get(key) or {}).items():
                out[key][name] = out[key].get(name, 0) + n
    return out


CRITICAL_MIN_APPLICATIONS = 50
CRITICAL_MIN_PUBLISHER_APPS = 30


def evaluate_alerts(all_bucket: Dict[str, Any], program_buckets: Dict[str, Dict[str, Any]]) -> List[Dict[str, str]]:
    """Server-side threshold checks -> in-app alert banners. Kept deliberately
    small and specific rather than flagging everything, so it stays useful."""
    alerts: List[Dict[str, str]] = []
    summary = summarize_bucket(all_bucket)

    if summary["applications"] >= CRITICAL_MIN_APPLICATIONS and summary["admission_conversion_pct"] is not None:
        if summary["admission_conversion_pct"] < 20:
            alerts.append({
                "severity": "critical",
                "title": "Low admission-fee conversion",
                "message": (
                    f"Only {summary['admission_conversion_pct']}% of {summary['applications']} "
                    "payment-approved applications have gone on to pay the admission fee. "
                    "Most \"applications\" are stalling before actual admission."
                ),
            })

    for row in summary["publisher_quality"]:
        if row["total"] >= CRITICAL_MIN_PUBLISHER_APPS and row["approval_pct"] is not None and row["approval_pct"] < 25:
            alerts.append({
                "severity": "warning",
                "title": f"{row['name']}: poor application quality",
                "message": (
                    f"Only {row['approval_pct']}% of {row['total']} applications from "
                    f"{row['name']} were payment-approved — well below other channels. "
                    "Worth reviewing spend here."
                ),
            })

    for prog, bucket in program_buckets.items():
        s = summarize_bucket(bucket)
        if s["applications"] >= CRITICAL_MIN_APPLICATIONS and s["admission_conversion_pct"] is not None:
            if s["admission_conversion_pct"] < 15:
                alerts.append({
                    "severity": "critical",
                    "title": f"{prog}: very low admission conversion",
                    "message": (
                        f"{prog} is converting only {s['admission_conversion_pct']}% of "
                        f"{s['applications']} payment-approved applications to paid admission."
                    ),
                })

    return alerts
