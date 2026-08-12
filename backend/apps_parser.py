"""Parse per-program Application dumps into aggregate counts."""
from __future__ import annotations

import io
import re
from typing import Any, Dict, List

import pandas as pd

from report_engine import _find_col, program_series


PROG_CANDS = ["Programme", "Course", "Program"]
ORIGIN_CANDS = ["Lead Origin", "Lead Origin(Primary)", "Primary Traffic Channel", "Publisher Name", "Publisher"]
# Discount / coupon code columns (a non-empty value => "application with code")
CODE_CANDS = [
    "Discount Coupon", "Coupon Code", "Coupon", "Applied Coupon", "Coupon Applied",
    "Promo Code", "Promocode", "Promo Code Applied", "Discount Code", "Referral Code",
    "Referral Coupon", "Code", "Voucher Code", "Voucher", "Scholarship Code",
]
BLANK_TOKENS = {"", "NA", "N/A", "NAN", "NONE", "NULL", "0", "-", "NO", "NIL"}


def parse_application_files(files: List[bytes], settings: Dict[str, Any]) -> Dict[str, Dict[str, int]]:
    programs = settings.get("programs", ["B.Com", "BBA", "PGDM"])
    api_pat = [p.upper() for p in settings.get("api_patterns", ["API"])]
    redir_pat = [p.upper() for p in settings.get("redirect_patterns", ["REDIRECT", "PUSH", "WIDGET"])]
    code_field = settings.get("application_code_field_apps")

    counts = {p: {"with_code": 0, "without_code": 0, "via_redirect": 0, "via_api": 0} for p in programs}

    for content in files:
        try:
            df = pd.read_excel(io.BytesIO(content), engine="openpyxl")
        except Exception:
            continue
        if len(df) == 0:
            continue
        col_prog = _find_col(df, PROG_CANDS, prefer_data=True)
        col_origin = _find_col(df, ORIGIN_CANDS, prefer_data=True)
        cands = ([code_field] if code_field else []) + CODE_CANDS
        col_code = _find_col(df, cands, prefer_data=True)

        prog = program_series(df[col_prog], programs) if col_prog else pd.Series([None] * len(df), index=df.index)
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

        for p in programs:
            mask = (prog.values == p)
            counts[p]["with_code"] += int((mask & has_code.values).sum())
            counts[p]["without_code"] += int((mask & ~has_code.values).sum())
            counts[p]["via_redirect"] += int((mask & is_redir.values).sum())
            counts[p]["via_api"] += int((mask & is_api.values).sum())
    return counts
