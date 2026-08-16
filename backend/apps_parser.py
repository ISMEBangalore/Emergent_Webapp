"""Parse per-program Application dumps into aggregate counts."""
from __future__ import annotations

import io
import re
from typing import Any, Dict, List

import pandas as pd

from report_engine import _find_col, program_series, read_data_sheet


PROG_CANDS = ["Courses Preference", "Course Preference", "Course", "Programme", "Program"]
ORIGIN_CANDS = ["Lead Origin", "Lead Origin(Primary)", "Primary Traffic Channel", "Publisher Name", "Publisher"]
PUB_CANDS = ["Publisher", "Publisher Name"]
# Discount / coupon code columns (a non-empty value => "application with code")
CODE_CANDS = [
    "Discount Coupon", "Coupon Code", "Coupon", "Applied Coupon", "Coupon Applied",
    "Promo Code", "Promocode", "Promo Code Applied", "Discount Code", "Referral Code",
    "Referral Coupon", "Code", "Voucher Code", "Voucher", "Scholarship Code",
]
BLANK_TOKENS = {"", "NA", "N/A", "NAN", "NONE", "NULL", "0", "-", "NO", "NIL"}
PAY_STATUS_CANDS = ["Payment Status", "Payment Approval Status", "Payment Approved"]
PAY_DATE_CANDS = ["Payment Approved Date"]
APP_DATE_CANDS = [
    "Registration Date", "User Registration Date", "Created On", "Application Date",
    "Created Date", "Payment Date", "Date",
]

_EMPTY_COUNTS = {"with_code": 0, "without_code": 0, "via_redirect": 0, "via_api": 0}


def _blank_counts() -> Dict[str, int]:
    return dict(_EMPTY_COUNTS)


def parse_application_files(files: List[bytes], settings: Dict[str, Any],
                            date_range: Dict[str, Any] = None) -> Dict[str, Any]:
    """Returns {"by_program": {...}, "by_publisher": {...}, "by_program_publisher": {prog: {pub: {...}}}}."""
    programs = settings.get("programs", ["B.Com", "BBA", "PGDM"])
    program_aliases = settings.get("program_aliases") or {}
    api_pat = [p.upper() for p in settings.get("api_patterns", ["API"])]
    redir_pat = [p.upper() for p in settings.get("redirect_patterns", ["REDIRECT", "PUSH", "WIDGET"])]
    code_field = settings.get("application_code_field_apps")
    date_range = date_range or {}
    d_start = (str(date_range.get("start") or "")).strip() or None
    d_end = (str(date_range.get("end") or "")).strip() or None

    by_program = {p: _blank_counts() for p in programs}
    by_publisher: Dict[str, Dict[str, int]] = {}
    by_program_publisher: Dict[str, Dict[str, Dict[str, int]]] = {p: {} for p in programs}

    def _bump(target: Dict[str, int], mask) -> None:
        target["with_code"] += int((mask & has_code.values).sum())
        target["without_code"] += int((mask & ~has_code.values).sum())
        target["via_redirect"] += int((mask & is_redir.values).sum())
        target["via_api"] += int((mask & is_api.values).sum())

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
        # ---- Count only payment-approved applications ----
        if settings.get("applications_payment_approved_only", True):
            col_pay = _find_col(df, PAY_STATUS_CANDS, prefer_data=True)
            if col_pay is not None:
                paid = df[col_pay].astype("string").str.strip().str.upper().eq("PAYMENT APPROVED").fillna(False)
            else:
                col_paydate = _find_col(df, PAY_DATE_CANDS, prefer_data=True)
                if col_paydate is not None:
                    v = df[col_paydate].astype("string").str.strip().str.upper().fillna("")
                    paid = ~v.isin(BLANK_TOKENS)
                else:
                    paid = pd.Series(True, index=df.index)
            df = df[paid].reset_index(drop=True)
            if len(df) == 0:
                continue
        col_origin = _find_col(df, ORIGIN_CANDS, prefer_data=True)
        col_pub = _find_col(df, PUB_CANDS, prefer_data=True)
        cands = ([code_field] if code_field else []) + CODE_CANDS
        col_code = _find_col(df, cands, prefer_data=True)

        # Choose the course column that best matches the configured programs.
        prog = None
        best_matched = -1
        lut = {c.strip().lower(): c for c in df.columns}
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
        if col_code is not None:
            code_norm = df[col_code].astype("string").str.strip().str.upper().fillna("")
            has_code = ~code_norm.isin(BLANK_TOKENS)
        else:
            has_code = pd.Series([False] * len(df), index=df.index)

        if col_origin is not None:
            o = df[col_origin].astype("string").str.upper().fillna("")
            is_api = pd.Series(False, index=df.index)
            for p in api_pat:
                is_api = is_api | o.str.contains(re.escape(p))
            is_redir = pd.Series(False, index=df.index)
            for p in redir_pat:
                is_redir = is_redir | o.str.contains(re.escape(p))
            is_redir = is_redir & ~is_api
        else:
            is_api = pd.Series(False, index=df.index)
            is_redir = pd.Series(False, index=df.index)

        if col_pub is not None:
            pub_raw = df[col_pub].astype("string").str.strip()
            pub_raw = pub_raw.where(pub_raw.notna() & (pub_raw != ""), "Unknown")
        else:
            pub_raw = pd.Series(["Unknown"] * len(df), index=df.index, dtype="object")

        for p in programs:
            mask = (prog.values == p)
            _bump(by_program[p], mask)

        for pub_name in pub_raw.unique():
            mask = (pub_raw.values == pub_name)
            by_publisher.setdefault(pub_name, _blank_counts())
            _bump(by_publisher[pub_name], mask)
            for p in programs:
                pmask = mask & (prog.values == p)
                if pmask.any():
                    by_program_publisher[p].setdefault(pub_name, _blank_counts())
                    _bump(by_program_publisher[p][pub_name], pmask)

    return {
        "by_program": by_program,
        "by_publisher": by_publisher,
        "by_program_publisher": by_program_publisher,
    }
