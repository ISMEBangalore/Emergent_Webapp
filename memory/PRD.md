# LeadPulse — Weekly CRM Report Dashboard

## Original Problem
A college/business school downloads two Excel files from their CRM (merrito.com) every Monday:
a Lead Dump (all programs) and Application dumps (one per program). They want a web app that
auto-generates a weekly report (Program × Lead-Stage matrix + derived metrics) instead of doing it manually.

## User Choices
1. BOTH interactive dashboard AND one-click Excel export matching their sample.
2. Real weekly files have `Course` + `Lead Stage` populated (full-schema parser).
3. User types Amount Spent per program each week → app computes Cost/Application & CPA.
4. Programs shown: B.Com, BBA, PGDM (each with % of total leads) + Total column.
5. Save each week's report for week-over-week comparison.

## Architecture
- **Backend** FastAPI + MongoDB (motor). Excel parsing via pandas/openpyxl.
  - `report_engine.py`: vectorised compute_report() — fuzzy column detection (data-preferring
    fallback: e.g. falls back to `First Lead Stage` if `Lead Stage` empty), program & stage
    normalisation, verified/redirect/API/relevant logic. Configurable via settings.
  - `apps_parser.py`: aggregates per-program application counts (with/without code, redirect/API).
  - `excel_export.py`: styled .xlsx matching the reference report colours.
  - `server.py`: async upload processing (background task + status polling), settings, trends,
    amounts PATCH (recompute CPA), export.
- **Frontend** React + Tailwind + shadcn. Manrope/IBM Plex Sans, brand #002FA7 (Swiss high-contrast).
  Pages: Dashboard, Generate Report, Report View, History, Settings. Recharts for charts.

## Implemented (2026-06)
- Weekly upload (lead file + optional per-program application files) with async processing + polling.
- Program × Lead-Stage matrix + full summary metrics (verified, redirect/API, relevant, applications, CPA).
- Editable Amount Spent / Additional Attributed → live CPA recalculation.
- Sample-data generator + one-click sample report (matches reference numbers).
- Styled Excel export. Report history + week-over-week trend charts. Configurable rules (Settings).
- Data-quality banner when Course column is unpopulated. Responsive layout (mobile drawer).

## Assumptions / Business Rules (configurable in Settings)
- Verified = mobile OR email verified (default).
- Stage grouping: COLD split into Verified(incl NOT INTERESTED)/Unverified; WARM incl HOT; JUNK incl WRONG NUMBER; unknown/blank → Untouched.
- Redirect vs API detected from Lead Origin text patterns.
- Application "with code" = Discount Coupon present (apps) / Agent Code (leads).

## Backlog / Next
- P1: Per-program application file → program auto-detect from filename.
- P1: shadcn calendar date picker on Generate page (currently native date input).
- P2: Configurable stage→bucket mapping UI; support arbitrary program names in normalization.
- P2: Global error/retry states on all data loads.
