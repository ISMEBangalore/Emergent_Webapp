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

## Comprehensive (complete-data) model — 2026-06
- User uploads ONE cumulative CRM file that grows each week (includes prior + new leads).
- Report is computed over the COMPLETE uploaded file by default (no weekly summing → no double counting).
- Optional lead date-range slicing supported via `date_range` (lead col: "User Registration Date";
  app col: "Registration Date"), applied only when start/end supplied; empty = complete data.
- Source files persisted in GridFS; `POST /api/reports/{id}/regenerate` re-slices without re-upload.
- Fixed: broken `report_engine.py` (duplicate block + undefined date vars) that crashed the backend.

## Real-file fixes — 2026-06 (10Aug2026 dump)
- ROOT CAUSE of wrong totals: the Lead workbook has TWO sheets — Sheet2 (pivot summary, 7 rows)
  first and Sheet1 (raw data, 156,944 rows) second. `pd.read_excel` defaulted to the first sheet.
  Added `read_data_sheet()` which picks the LARGEST sheet (raw data) in both lead + app parsing.
- App program attribution: app parser now picks the course column that best matches configured
  programs (tries "Courses Preference","Course Preference","Course","Programme","Program"), so
  UG apps (Programme="BACHELOR DEGREE PROGRAMME") map correctly to B.Com/BBA instead of 0.
- Verified totals on real file: B.Com 21,940 · BBA 31,573 · PGDM 63,448 (of 156,758 leads after
  186 test leads excluded). Date coverage 2025-10-05 → 2026-08-10 via "User Registration Date".
- NOTE: BCA (29k), MCA, PhD, "COURSE NOT AVAILABLE" leads fall into "Other" (not shown) because
  only B.Com/BBA/PGDM are configured programs. Add them in Settings if the user wants them shown.

## Selectable programs + regenerate — 2026-06
- ALL courses detected in the uploaded file are now selectable in Settings (chips). `/available`
  returns courses/publishers from the LATEST uploaded report (not stale aggregate), so the user
  sees their real raw course names (B.COM WITH ACCA, BCA, MCA, "PGDM (MKT/FIN/HR/BA/IA)", etc.).
- `program_series` matching: exact (alnum) match first; substring fallback ONLY for programs with
  no exact match (canonical short names like B.Com/PGDM). Selecting full raw course names is exact
  and never double-counts. Verified with unit test on real course list.
- `POST /reports/{id}/regenerate` now uses the LATEST global settings (selected programs/publishers/
  rules) + optional date range, re-running on the GridFS-stored file. Persists new settings+range.
- ReportView: added date-coverage line + From/To + "Apply & Regenerate" panel (only when a source
  file is stored). Verified: full 1,740 → Oct–Dec slice 360; coverage shown 2024-10-20→2026-08-09.

## Saved Views + large-upload verified — 2026-06
- Saved Views: `GET/POST/DELETE /api/views` store {name, programs, start, end}. On ReportView users
  can Save current view (programs + date range) and one-click Apply (updates settings.programs +
  regenerates on the stored file). Verified create/list/apply/delete.
- LARGE UPLOAD VERIFIED: real 98MB (102,668,308 bytes) lead file uploaded through the app gateway
  → HTTP 200 in 4.3s (no ingress size limit hit). Full compute of 156,944 rows finished in ~40s.
  NOTE: saving backend code during processing hot-reloads uvicorn and kills the in-flight background
  task (report stuck "processing") — recover via regenerate (file is safely in GridFS).
- Real-file totals confirmed: B.Com 21,940 · BBA 31,573 · PGDM 63,448 (116,961 total); apps
  665/1,073/1,695; 26 publishers + 21 courses detected; coverage 2025-10-05 → 2026-08-10.

## Backlog / Next
- P1: Per-program application file → program auto-detect from filename.
- P1: shadcn calendar date picker on Generate page (currently native date input).
- P2: Configurable stage→bucket mapping UI; support arbitrary program names in normalization.
- P2: Global error/retry states on all data loads.
