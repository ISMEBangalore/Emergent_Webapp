"""
Weekly CRM report engine (vectorised).

Parses a CRM Lead dump (.xlsx) and optional Application dumps, and computes the
Program x Lead-Stage matrix plus derived metrics driven by configurable rules.
"""
from __future__ import annotations

import io
import re
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


DEFAULT_SETTINGS: Dict[str, Any] = {
    "programs": ["B.Com", "BBA", "PGDM"],
    "stage_rows": [
        "APPLIED",
        "COLD Unverified leads",
        "COLD Verified leads (includes NI)",
        "JOINED IN ANOTHER COLLEGE",
        "UNANSWERED 3 TIMES",
        "JUNK",
        "NOT ELIGIBLE",
        "NOT REACHABLE/SWITCH OFF",
        "Untouched",
        "WARM",
    ],
    "verified_logic": "any",           # any | all | mobile | email
    "relevant_stages": ["WARM", "HOT", "APPLIED", "INTERESTED IN PGDM R&L"],
    "api_patterns": ["API"],
    "redirect_patterns": ["REDIRECT", "PUSH", "WIDGET"],
    "application_code_field": "Agent Code",
}

PROGRAM_CANDIDATES = ["Course", "Programme", "Program", "Form Interested In"]
STAGE_CANDIDATES = ["Lead Stage", "First Lead Stage"]
EMAIL_VERIF_CANDIDATES = ["Email Verification Status"]
MOBILE_VERIF_CANDIDATES = ["Mobile Verification Status"]
ORIGIN_CANDIDATES = [
    "Lead Origin(Primary)", "Primary Traffic Channel", "Lead Origin",
    "Latest Traffic Channel", "Lead Type(Secondary)",
]
WIDGET_CANDIDATES = ["Widget Name"]
PAYMENT_CANDIDATES = ["Payment Approved"]


def _norm(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s)).strip().lower()


def _find_col(df: pd.DataFrame, candidates: List[str], prefer_data: bool = False) -> Optional[str]:
    lut = {_norm(c): c for c in df.columns}
    matches: List[str] = []
    for cand in candidates:
        key = _norm(cand)
        if key in lut and lut[key] not in matches:
            matches.append(lut[key])
    for cand in candidates:
        key = _norm(cand)
        for k, orig in lut.items():
            if key and key in k and orig not in matches:
                matches.append(orig)
    if not matches:
        return None
    if prefer_data:
        for m in matches:
            if df[m].notna().any():
                return m
    return matches[0]


def _prog_from_series(s: pd.Series) -> pd.Series:
    u = s.astype("string").str.upper().fillna("")
    out = pd.Series(np.where(u.str.contains("PGDM"), "PGDM",
             np.where(u.str.contains("BBA"), "BBA",
             np.where(u.str.contains("B.COM") | u.str.contains("BCOM") | u.str.contains("B COM") | u.str.contains("B. COM"), "B.Com",
             np.where(u.str.contains("BCA"), "BCA",
             np.where(u.str.strip().isin(["", "NAN", "NONE"]), None, "Other"))))), index=s.index)
    return out


def compute_report(
    lead_bytes: bytes,
    settings: Dict[str, Any],
    amount_spent: Optional[Dict[str, float]] = None,
    additional_attributed: Optional[Dict[str, float]] = None,
    application_counts: Optional[Dict[str, Dict[str, int]]] = None,
) -> Dict[str, Any]:
    cfg = {**DEFAULT_SETTINGS, **(settings or {})}
    programs: List[str] = cfg["programs"]
    stage_rows: List[str] = cfg["stage_rows"]
    amount_spent = amount_spent or {}
    additional_attributed = additional_attributed or {}
    application_counts = application_counts or {}

    df = pd.read_excel(io.BytesIO(lead_bytes), engine="openpyxl")
    n = len(df)

    col_prog = _find_col(df, PROGRAM_CANDIDATES, prefer_data=True)
    col_stage = _find_col(df, STAGE_CANDIDATES, prefer_data=True)
    col_email = _find_col(df, EMAIL_VERIF_CANDIDATES)
    col_mobile = _find_col(df, MOBILE_VERIF_CANDIDATES)
    col_origin = _find_col(df, ORIGIN_CANDIDATES, prefer_data=True)
    col_widget = _find_col(df, WIDGET_CANDIDATES)
    col_payment = _find_col(df, PAYMENT_CANDIDATES)
    col_agent = _find_col(df, [cfg.get("application_code_field", "Agent Code")])

    all_cols = list(programs) + ["Other"]

    # ---- Program (vectorised) ----
    if col_prog is not None:
        prog = _prog_from_series(df[col_prog])
    else:
        prog = pd.Series([None] * n, index=df.index, dtype="object")
    # Fallback via widget / payment where program still unknown
    need = prog.isna()
    if need.any() and (col_widget or col_payment):
        wp = pd.Series([""] * n, index=df.index, dtype="object")
        if col_widget:
            wp = wp.str.cat(df[col_widget].astype("string").fillna("").str.upper(), sep=" ")
        if col_payment:
            wp = wp.str.cat(df[col_payment].astype("string").fillna("").str.upper(), sep=" ")
        fb = pd.Series(np.where(wp.str.contains("PGDM", regex=False) | wp.str.contains("WIDGET(PG)", regex=False) | wp.str.contains("PG-EX", regex=False), "PGDM",
                        np.where(wp.str.contains("UG", regex=False), "UG", None)), index=df.index)
        prog = prog.where(~need, fb)
    unclassified = int(prog.isna().sum())
    prog = prog.where(prog.isin(all_cols), "Other")

    # ---- Verified (vectorised) ----
    e = (df[col_email].astype("string").str.upper() == "VERIFIED") if col_email else pd.Series(False, index=df.index)
    m = (df[col_mobile].astype("string").str.upper() == "VERIFIED") if col_mobile else pd.Series(False, index=df.index)
    e = e.fillna(False); m = m.fillna(False)
    logic = cfg.get("verified_logic", "any")
    verified = {"email": e, "mobile": m, "all": e & m}.get(logic, e | m)

    # ---- Stage bucket (vectorised) ----
    if col_stage is not None:
        raw = df[col_stage].astype("string").str.strip().str.upper()
    else:
        raw = pd.Series([pd.NA] * n, index=df.index, dtype="string")
    empty = raw.isna() | (raw == "")
    bucket = pd.Series("Untouched", index=df.index, dtype="object")
    def setb(mask, label):
        bucket.loc[mask & (bucket == "Untouched")] = label
    setb(raw == "APPLIED", "APPLIED")
    setb((raw == "COLD") & verified, "COLD Verified leads (includes NI)")
    setb((raw == "COLD") & ~verified, "COLD Unverified leads")
    setb(raw.isin(["NOT INTERESTED", "FORM STARTED - NOT INTERESTED"]), "COLD Verified leads (includes NI)")
    setb(raw.isin(["JOINED IN OTHER COLLEGE", "JOINED IN ANOTHER COLLEGE"]), "JOINED IN ANOTHER COLLEGE")
    setb(raw == "UNANSWERED 3 TIMES", "UNANSWERED 3 TIMES")
    setb(raw.isin(["JUNK", "WRONG NUMBER", "TEST LEADS", "DONT PURGE"]), "JUNK")
    setb(raw == "NOT ELIGIBLE", "NOT ELIGIBLE")
    setb(raw == "NOT REACHABLE/SWITCH OFF", "NOT REACHABLE/SWITCH OFF")
    setb(raw.isin(["WARM", "HOT"]), "WARM")
    # unknown non-empty stages -> Untouched (already default); keep empty as Untouched too
    bucket.loc[empty] = "Untouched"

    work = pd.DataFrame({"prog": prog.values, "bucket": bucket.values, "verified": verified.values})
    relevant_set = {s.upper() for s in cfg["relevant_stages"]}
    work["relevant"] = raw.isin(relevant_set).values

    # ---- Channel kind (vectorised) ----
    if col_origin is not None:
        o = df[col_origin].astype("string").str.upper().fillna("")
        is_api = pd.Series(False, index=df.index)
        for p in cfg.get("api_patterns", []):
            is_api = is_api | o.str.contains(re.escape(p.upper()))
        is_redir = pd.Series(False, index=df.index)
        for p in cfg.get("redirect_patterns", []):
            is_redir = is_redir | o.str.contains(re.escape(p.upper()))
        is_redir = is_redir & ~is_api
    else:
        is_api = pd.Series(False, index=df.index)
        is_redir = pd.Series(False, index=df.index)
    work["is_api"] = is_api.values
    work["is_redir"] = is_redir.values

    def by_prog(mask_series=None) -> Dict[str, int]:
        sub = work if mask_series is None else work[mask_series.values if hasattr(mask_series, "values") else mask_series]
        vc = sub["prog"].value_counts()
        return {p: int(vc.get(p, 0)) for p in all_cols}

    total_leads = by_prog()
    verified_leads = by_prog(work["verified"])
    redirect_leads = by_prog(work["is_redir"])
    redirect_verified = by_prog(work["is_redir"] & work["verified"])
    api_leads = by_prog(work["is_api"])
    api_verified = by_prog(work["is_api"] & work["verified"])
    relevant_leads = by_prog(work["relevant"])

    # matrix counts: crosstab prog x bucket
    ct = pd.crosstab(work["bucket"], work["prog"])
    matrix_counts = {row: {p: int(ct.loc[row, p]) if (row in ct.index and p in ct.columns) else 0 for p in all_cols}
                     for row in stage_rows}

    return build_result(
        programs=programs, stage_rows=stage_rows, matrix_counts=matrix_counts,
        total_leads=total_leads, verified_leads=verified_leads,
        redirect_leads=redirect_leads, redirect_verified=redirect_verified,
        api_leads=api_leads, api_verified=api_verified, relevant_leads=relevant_leads,
        application_counts=application_counts, amount_spent=amount_spent,
        additional_attributed=additional_attributed,
        detected_columns={
            "program": col_prog, "stage": col_stage,
            "email_verification": col_email, "mobile_verification": col_mobile,
            "lead_origin": col_origin, "agent_code": col_agent,
        },
        data_quality={
            "total_rows": n, "unclassified_program": unclassified,
            "program_column_present": bool(col_prog), "stage_column_present": bool(col_stage),
        },
    )


def build_result(programs, stage_rows, matrix_counts, total_leads, verified_leads,
                 redirect_leads, redirect_verified, api_leads, api_verified, relevant_leads,
                 application_counts, amount_spent, additional_attributed,
                 detected_columns, data_quality):
    """Build the report result dict from pre-aggregated count dictionaries."""
    def totrow(d):
        return sum(d.get(p, 0) for p in programs)

    apps_with = {p: int(application_counts.get(p, {}).get("with_code", 0)) for p in programs}
    apps_without = {p: int(application_counts.get(p, {}).get("without_code", 0)) for p in programs}
    apps_redirect = {p: int(application_counts.get(p, {}).get("via_redirect", 0)) for p in programs}
    apps_api = {p: int(application_counts.get(p, {}).get("via_api", 0)) for p in programs}
    total_apps = {p: apps_with[p] + apps_without[p] for p in programs}

    def pct(num, den):
        return round(num / den * 100, 2) if den else None

    grand_total = totrow(total_leads)
    result: Dict[str, Any] = {
        "programs": programs,
        "columns": programs + ["Total"],
        "detected_columns": detected_columns,
        "data_quality": data_quality,
        "matrix": [],
        "summary": [],
    }

    for row in stage_rows:
        entry = {"stage": row, "values": {}, "pct": {}, "total": totrow(matrix_counts[row])}
        for p in programs:
            entry["values"][p] = matrix_counts[row][p]
            entry["pct"][p] = pct(matrix_counts[row][p], total_leads[p])
        entry["total_pct"] = pct(entry["total"], grand_total)
        result["matrix"].append(entry)

    def srow(label, values, pcts=None, fmt="int", kind="metric"):
        e = {"label": label, "fmt": fmt, "kind": kind, "values": {}, "pct": {}}
        tot = 0
        for p in programs:
            v = values.get(p, 0)
            e["values"][p] = v
            tot += v or 0
            if pcts is not None:
                e["pct"][p] = pcts.get(p)
        e["total"] = round(tot, 2)
        if pcts is not None:
            e["total_pct"] = pcts.get("Total")
        return e

    S = result["summary"]
    S.append(srow("Total Leads", total_leads, {**{p: 100.0 for p in programs}, "Total": 100.0}, kind="header"))
    S.append(srow("Verified Leads", verified_leads))
    S.append(srow("Verified leads (%) of Total Leads", verified_leads,
                  {**{p: pct(verified_leads[p], total_leads[p]) for p in programs}, "Total": pct(totrow(verified_leads), grand_total)}, fmt="pct_only"))
    S.append(srow("Total Redirect Leads", redirect_leads))
    S.append(srow("Total Verified redirect leads", redirect_verified))
    S.append(srow("Verified % of Redirect Leads", redirect_verified,
                  {**{p: pct(redirect_verified[p], redirect_leads[p]) for p in programs}, "Total": pct(totrow(redirect_verified), totrow(redirect_leads))}, fmt="pct_only"))
    S.append(srow("Total API Leads", api_leads))
    S.append(srow("Total Verified API leads", api_verified))
    S.append(srow("Verified % of API Leads", api_verified,
                  {**{p: pct(api_verified[p], api_leads[p]) for p in programs}, "Total": pct(totrow(api_verified), totrow(api_leads))}, fmt="pct_only"))
    S.append(srow("No. of Applications with codes", apps_with))
    S.append(srow("No. of Applications without codes", apps_without))
    S.append({"label": "Lead Analysis", "kind": "section"})
    S.append(srow("Relevant Leads", relevant_leads))
    S.append(srow("% Relevant Leads", relevant_leads,
                  {**{p: pct(relevant_leads[p], total_leads[p]) for p in programs}, "Total": pct(totrow(relevant_leads), grand_total)}, fmt="pct_only"))
    S.append(srow("Total No. of Applications", total_apps))
    S.append(srow("% of Applications", total_apps,
                  {**{p: pct(total_apps[p], total_leads[p]) for p in programs}, "Total": pct(sum(total_apps.values()), grand_total)}, fmt="pct_only"))
    S.append(srow("No of applications through redirect leads", apps_redirect))
    S.append(srow("% of application based on redirect leads", apps_redirect,
                  {**{p: pct(apps_redirect[p], total_apps[p]) for p in programs}, "Total": pct(sum(apps_redirect.values()), sum(total_apps.values()))}, fmt="pct_only"))
    S.append(srow("No of applications through API leads", apps_api))
    S.append(srow("% of application based on API leads", apps_api,
                  {**{p: pct(apps_api[p], total_apps[p]) for p in programs}, "Total": pct(sum(apps_api.values()), sum(total_apps.values()))}, fmt="pct_only"))

    spent = {p: float(amount_spent.get(p, 0) or 0) for p in programs}
    add_attr = {p: float(additional_attributed.get(p, 0) or 0) for p in programs}
    S.append(srow("Amount Spent", spent, fmt="money"))
    cost_per_app = {p: round(spent[p] / total_apps[p], 2) if total_apps[p] else 0 for p in programs}
    S.append(srow("Cost/Application", cost_per_app, fmt="money"))
    S.append(srow("Additional Attributed Applications", add_attr, fmt="int"))
    mod_cost = {p: round(spent[p] / (total_apps[p] + add_attr[p]), 2) if (total_apps[p] + add_attr[p]) else 0 for p in programs}
    S.append(srow("Modified CPA after attribution", mod_cost, fmt="money"))

    return result



def _sum_row(target, values):
    for p, v in (values or {}).items():
        target[p] = target.get(p, 0) + (v or 0)


def aggregate_reports(reports, settings):
    """Sum aggregated counts across multiple stored report results into one result."""
    cfg = {**DEFAULT_SETTINGS, **(settings or {})}
    programs = cfg["programs"]
    stage_rows = cfg["stage_rows"]

    matrix_counts = {row: {p: 0 for p in programs} for row in stage_rows}
    total_leads = {p: 0 for p in programs}
    verified_leads = {p: 0 for p in programs}
    redirect_leads = {p: 0 for p in programs}
    redirect_verified = {p: 0 for p in programs}
    api_leads = {p: 0 for p in programs}
    api_verified = {p: 0 for p in programs}
    relevant_leads = {p: 0 for p in programs}
    app_counts = {p: {"with_code": 0, "without_code": 0, "via_redirect": 0, "via_api": 0} for p in programs}
    amount_spent = {p: 0 for p in programs}
    additional_attributed = {p: 0 for p in programs}

    label_map = {
        "Verified Leads": verified_leads,
        "Total Redirect Leads": redirect_leads,
        "Total Verified redirect leads": redirect_verified,
        "Total API Leads": api_leads,
        "Total Verified API leads": api_verified,
        "Relevant Leads": relevant_leads,
        "Amount Spent": amount_spent,
        "Additional Attributed Applications": additional_attributed,
    }
    app_map = {
        "No. of Applications with codes": "with_code",
        "No. of Applications without codes": "without_code",
        "No of applications through redirect leads": "via_redirect",
        "No of applications through API leads": "via_api",
    }

    weeks = 0
    for rep in reports:
        res = rep.get("result")
        if not res:
            continue
        weeks += 1
        for m in res.get("matrix", []):
            row = m["stage"]
            if row in matrix_counts:
                for p in programs:
                    matrix_counts[row][p] += m["values"].get(p, 0) or 0
        for s in res.get("summary", []):
            label = s.get("label")
            if label in label_map:
                _sum_row(label_map[label], s.get("values"))
            if label in app_map:
                key = app_map[label]
                for p in programs:
                    app_counts[p][key] += s.get("values", {}).get(p, 0) or 0
        # total leads per program = sum of matrix values (recomputed at the end)

    for p in programs:
        total_leads[p] = sum(matrix_counts[row][p] for row in stage_rows)

    result = build_result(
        programs=programs, stage_rows=stage_rows, matrix_counts=matrix_counts,
        total_leads=total_leads, verified_leads=verified_leads,
        redirect_leads=redirect_leads, redirect_verified=redirect_verified,
        api_leads=api_leads, api_verified=api_verified, relevant_leads=relevant_leads,
        application_counts=app_counts, amount_spent=amount_spent,
        additional_attributed=additional_attributed,
        detected_columns={}, data_quality={"weeks_aggregated": weeks},
    )
    return result
