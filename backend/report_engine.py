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
    "exclude_test_leads": True,
    "test_keywords": ["test"],
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
PUBLISHER_CANDIDATES = ["Publisher Name", "Publisher", "Publisher(Primary)"]


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
    raw_n = len(df)

    # ---- Exclude TEST leads (by name / remark / email / stage) ----
    test_excluded = 0
    if cfg.get("exclude_test_leads", True):
        kws = [str(k).lower().strip() for k in cfg.get("test_keywords", ["test"]) if str(k).strip()]
        is_test = pd.Series(False, index=df.index)
        name_col = _find_col(df, ["Registered Name", "Name", "First Name"])
        rem_col = _find_col(df, ["Lead Remark", "Remark", "Remarks"])
        email_col = _find_col(df, ["Email", "Email Id", "Email Address"])
        stage_col_tmp = _find_col(df, STAGE_CANDIDATES, prefer_data=True)
        for kw in kws:
            word_pat = r"\b" + re.escape(kw) + r"\b"
            if name_col:
                is_test |= df[name_col].astype("string").str.contains(word_pat, case=False, na=False, regex=True)
            if rem_col:
                is_test |= df[rem_col].astype("string").str.contains(word_pat, case=False, na=False, regex=True)
            if email_col:
                is_test |= df[email_col].astype("string").str.contains(kw, case=False, na=False, regex=False)
        if stage_col_tmp:
            is_test |= df[stage_col_tmp].astype("string").str.strip().str.upper().eq("TEST LEADS").fillna(False)
        test_excluded = int(is_test.sum())
        if test_excluded:
            df = df[~is_test].reset_index(drop=True)
    n = len(df)

    col_prog = _find_col(df, PROGRAM_CANDIDATES, prefer_data=True)
    col_stage = _find_col(df, STAGE_CANDIDATES, prefer_data=True)
    col_email = _find_col(df, EMAIL_VERIF_CANDIDATES)
    col_mobile = _find_col(df, MOBILE_VERIF_CANDIDATES)
    col_origin = _find_col(df, ORIGIN_CANDIDATES, prefer_data=True)
    col_widget = _find_col(df, WIDGET_CANDIDATES)
    col_payment = _find_col(df, PAYMENT_CANDIDATES)
    col_agent = _find_col(df, [cfg.get("application_code_field", "Agent Code")])
    col_pub = _find_col(df, PUBLISHER_CANDIDATES, prefer_data=True)

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
    setb(raw.isin(["NOT INTERESTED", "FORM STARTED - NOT INTERESTED"]), "COLD Unverified leads")
    setb(raw.isin(["JOINED IN OTHER COLLEGE", "JOINED IN ANOTHER COLLEGE"]), "JOINED IN ANOTHER COLLEGE")
    setb(raw == "UNANSWERED 3 TIMES", "UNANSWERED 3 TIMES")
    setb(raw.isin(["JUNK", "WRONG NUMBER", "TEST LEADS", "DONT PURGE"]), "JUNK")
    setb(raw.isin(["NOT ELIGIBLE", "ELIGIBLE FOR NEXT YEAR"]), "NOT ELIGIBLE")
    setb(raw == "NOT REACHABLE/SWITCH OFF", "NOT REACHABLE/SWITCH OFF")
    setb(raw.isin(["WARM", "HOT"]), "WARM")
    # unknown non-empty stages -> Untouched (already default); keep empty as Untouched too
    bucket.loc[empty] = "Untouched"

    if col_pub is not None:
        pub_raw = df[col_pub].astype("string").str.strip()
        pub_raw = pub_raw.where(pub_raw.notna() & (pub_raw != ""), "Unknown")
    else:
        pub_raw = pd.Series(["Unknown"] * n, index=df.index, dtype="object")

    work = pd.DataFrame({"prog": prog.values, "pub": pub_raw.values,
                         "bucket": bucket.values, "verified": verified.values})
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

    def agg(frame, colname, cats):
        def counts(mask=None):
            sub = frame if mask is None else frame[mask.values if hasattr(mask, "values") else mask]
            vc = sub[colname].value_counts()
            return {c: int(vc.get(c, 0)) for c in cats}
        ct = pd.crosstab(frame["bucket"], frame[colname])
        mc = {row: {c: int(ct.loc[row, c]) if (row in ct.index and c in ct.columns) else 0 for c in cats}
              for row in stage_rows}
        return (counts(), counts(frame["verified"]), counts(frame["is_redir"]),
                counts(frame["is_redir"] & frame["verified"]), counts(frame["is_api"]),
                counts(frame["is_api"] & frame["verified"]), counts(frame["relevant"]), mc)

    (total_leads, verified_leads, redirect_leads, redirect_verified,
     api_leads, api_verified, relevant_leads, matrix_counts) = agg(work, "prog", all_cols)

    # ---- Publisher breakdown (top publishers by volume, rest -> Other) ----
    pub_vc = work["pub"].value_counts()
    top_pubs = [str(x) for x in pub_vc.head(12).index.tolist()]
    work["pub"] = work["pub"].where(work["pub"].isin(top_pubs), "Other")
    pub_cats = top_pubs + (["Other"] if len(pub_vc) > len(top_pubs) else [])

    def make_publisher_result(frame):
        (t, ver, rd, rdv, ap, apv, rel, mc) = agg(frame, "pub", pub_cats)
        applied = mc.get("APPLIED", {})
        app_counts = {c: {"with_code": 0, "without_code": int(applied.get(c, 0)),
                          "via_redirect": 0, "via_api": 0} for c in pub_cats}
        return build_result(
            programs=pub_cats, stage_rows=stage_rows, matrix_counts=mc,
            total_leads=t, verified_leads=ver, redirect_leads=rd, redirect_verified=rdv,
            api_leads=ap, api_verified=apv, relevant_leads=rel,
            application_counts=app_counts, amount_spent={}, additional_attributed={},
            detected_columns={"publisher": col_pub},
            data_quality={"total_rows": len(frame), "publisher_column_present": bool(col_pub),
                          "publisher_count": int(len(pub_vc))},
        )

    publisher_result = make_publisher_result(work)
    # Per-program publisher breakdowns (same publisher columns for consistency)
    publisher_reports = {"All": publisher_result}
    for prog_name in programs:
        publisher_reports[prog_name] = make_publisher_result(work[work["prog"] == prog_name])

    result = build_result(
        programs=programs, stage_rows=stage_rows, matrix_counts=matrix_counts,
        total_leads=total_leads, verified_leads=verified_leads,
        redirect_leads=redirect_leads, redirect_verified=redirect_verified,
        api_leads=api_leads, api_verified=api_verified, relevant_leads=relevant_leads,
        application_counts=application_counts, amount_spent=amount_spent,
        additional_attributed=additional_attributed,
        detected_columns={
            "program": col_prog, "stage": col_stage,
            "email_verification": col_email, "mobile_verification": col_mobile,
            "lead_origin": col_origin, "agent_code": col_agent, "publisher": col_pub,
        },
        data_quality={
            "total_rows": n, "unclassified_program": unclassified,
            "program_column_present": bool(col_prog), "stage_column_present": bool(col_stage),
            "test_leads_excluded": test_excluded, "raw_rows": raw_n,
        },
    )
    result["publisher_report"] = publisher_result
    result["publisher_reports"] = publisher_reports

    # Program breakdown per publisher (columns = programs, one report per publisher)
    def make_program_result(frame):
        (t, ver, rd, rdv, ap, apv, rel, mc) = agg(frame, "prog", all_cols)
        applied = mc.get("APPLIED", {})
        app_counts = {p: {"with_code": 0, "without_code": int(applied.get(p, 0)),
                          "via_redirect": 0, "via_api": 0} for p in programs}
        return build_result(
            programs=programs, stage_rows=stage_rows, matrix_counts=mc,
            total_leads=t, verified_leads=ver, redirect_leads=rd, redirect_verified=rdv,
            api_leads=ap, api_verified=apv, relevant_leads=rel,
            application_counts=app_counts, amount_spent={}, additional_attributed={},
            detected_columns={"publisher": col_pub}, data_quality={"total_rows": len(frame)},
        )

    program_reports = {"All": {k: result[k] for k in
                        ("programs", "columns", "matrix", "summary", "detected_columns", "data_quality")}}
    for pub_name in pub_cats:
        program_reports[pub_name] = make_program_result(work[work["pub"] == pub_name])
    result["program_reports"] = program_reports
    return result


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


def _aggregate(results, cols, stage_rows):
    """Sum aggregated counts across a list of result dicts for a fixed column set."""
    matrix_counts = {row: {c: 0 for c in cols} for row in stage_rows}
    verified_leads = {c: 0 for c in cols}
    redirect_leads = {c: 0 for c in cols}
    redirect_verified = {c: 0 for c in cols}
    api_leads = {c: 0 for c in cols}
    api_verified = {c: 0 for c in cols}
    relevant_leads = {c: 0 for c in cols}
    app_counts = {c: {"with_code": 0, "without_code": 0, "via_redirect": 0, "via_api": 0} for c in cols}
    amount_spent = {c: 0 for c in cols}
    additional_attributed = {c: 0 for c in cols}

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
    for res in results:
        if not res:
            continue
        for m in res.get("matrix", []):
            row = m["stage"]
            if row in matrix_counts:
                for c in cols:
                    matrix_counts[row][c] += m["values"].get(c, 0) or 0
        for s in res.get("summary", []):
            label = s.get("label")
            if label in label_map:
                for c in cols:
                    label_map[label][c] += s.get("values", {}).get(c, 0) or 0
            if label in app_map:
                key = app_map[label]
                for c in cols:
                    app_counts[c][key] += s.get("values", {}).get(c, 0) or 0

    total_leads = {c: sum(matrix_counts[row][c] for row in stage_rows) for c in cols}
    return build_result(
        programs=cols, stage_rows=stage_rows, matrix_counts=matrix_counts,
        total_leads=total_leads, verified_leads=verified_leads,
        redirect_leads=redirect_leads, redirect_verified=redirect_verified,
        api_leads=api_leads, api_verified=api_verified, relevant_leads=relevant_leads,
        application_counts=app_counts, amount_spent=amount_spent,
        additional_attributed=additional_attributed,
        detected_columns={}, data_quality={},
    )


def aggregate_reports(reports, settings):
    """Sum aggregated counts across multiple stored reports (program + publisher)."""
    cfg = {**DEFAULT_SETTINGS, **(settings or {})}
    programs = cfg["programs"]
    stage_rows = cfg["stage_rows"]

    prog_results = [r.get("result") for r in reports if r.get("result")]
    weeks = len(prog_results)
    result = _aggregate(prog_results, programs, stage_rows)
    result["data_quality"] = {"weeks_aggregated": weeks}

    # Publisher cumulative (overall + per program): union publisher columns, top 12 by leads.
    def pub_cumulative(getter):
        pub_results = [getter(r["result"]) for r in reports
                       if r.get("result") and getter(r["result"])]
        if not pub_results:
            return None
        totals = {}
        for pr in pub_results:
            for m in pr.get("matrix", []):
                for c, v in m["values"].items():
                    totals[c] = totals.get(c, 0) + (v or 0)
        pub_cols = [c for c, _ in sorted(totals.items(), key=lambda x: -x[1]) if c != "Other"][:12]
        if "Other" in totals:
            pub_cols.append("Other")
        cum = _aggregate(pub_results, pub_cols, stage_rows)
        cum["data_quality"] = {"weeks_aggregated": weeks}
        return cum

    overall = pub_cumulative(lambda res: res.get("publisher_report"))
    if overall:
        result["publisher_report"] = overall
        pub_reports = {"All": overall}
        for prog_name in programs:
            pr = pub_cumulative(lambda res, p=prog_name: (res.get("publisher_reports") or {}).get(p))
            if pr:
                pub_reports[prog_name] = pr
        result["publisher_reports"] = pub_reports

    # Program-per-publisher cumulative
    pub_keys = set()
    for r in reports:
        pr = (r.get("result") or {}).get("program_reports") or {}
        pub_keys.update(k for k in pr.keys() if k != "All")
    prog_reports = {"All": {k: result[k] for k in
                    ("programs", "columns", "matrix", "summary") if k in result}}
    for pub_name in pub_keys:
        subs = [r["result"]["program_reports"][pub_name] for r in reports
                if r.get("result") and (r["result"].get("program_reports") or {}).get(pub_name)]
        if subs:
            pr = _aggregate(subs, programs, stage_rows)
            pr["data_quality"] = {"weeks_aggregated": weeks}
            prog_reports[pub_name] = pr
    if len(prog_reports) > 1:
        result["program_reports"] = prog_reports
    return result
