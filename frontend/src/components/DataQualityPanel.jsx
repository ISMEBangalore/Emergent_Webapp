import { CheckCircle, XCircle, Warning } from "@phosphor-icons/react";
import { fmtInt, fmtPct1 } from "@/lib/format";

const COLUMN_LABELS = [
  { key: "program", label: "Program" },
  { key: "stage", label: "Lead Stage" },
  { key: "publisher", label: "Publisher" },
  { key: "email_verification", label: "Email Verification" },
  { key: "mobile_verification", label: "Mobile Verification" },
  { key: "lead_origin", label: "Lead Origin" },
  { key: "agent_code", label: "Agent Code" },
];

const ColumnChip = ({ label, found }) => (
  <span
    className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${
      found ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-red-50 text-red-700 border-red-200"
    }`}
    data-testid={`dq-col-${label.toLowerCase().replace(/\s+/g, "-")}`}
  >
    {found ? <CheckCircle size={13} weight="fill" /> : <XCircle size={13} weight="fill" />}
    {label}
  </span>
);

// Surfaces the backend's own data_quality/detected_columns numbers as a trust
// indicator - so a broken CRM export (missing column, mostly-unclassified
// programs, a date filter silently dropping most rows) is visible at a glance
// instead of only showing up as an unexplained dip in the numbers above it.
export const DataQualityPanel = ({ result }) => {
  const dq = result?.data_quality;
  const cols = result?.detected_columns;
  if (!dq || dq.weeks_aggregated === 0) {
    return (
      <div className="border border-dashed border-slate-300 rounded-md p-10 text-center text-slate-500"
           data-testid="dq-empty">
        No data quality information available for this range yet.
      </div>
    );
  }

  const rawRows = dq.raw_rows ?? dq.total_rows ?? 0;
  const afterTest = rawRows - (dq.test_leads_excluded || 0);
  const rowsBeforeDate = dq.rows_before_date_filter ?? afterTest;
  const analyzed = dq.total_rows ?? rowsBeforeDate;
  const unclassifiedPct = analyzed ? (dq.unclassified_program || 0) / analyzed * 100 : 0;
  const hasDateFilter = Boolean(dq.date_range?.start || dq.date_range?.end);

  return (
    <div data-testid="data-quality-panel" className="space-y-6">
      <div className="bg-white border border-slate-200 rounded-md p-5">
        <h3 className="font-display font-bold text-slate-900 mb-1">Columns detected in this file</h3>
        <p className="text-xs text-slate-500 mb-4">
          If a column shows red, that data point isn't being tracked at all for this upload — check the source
          file's headers.
        </p>
        <div className="flex flex-wrap gap-2">
          {COLUMN_LABELS.map((c) => (
            <ColumnChip key={c.key} label={c.label} found={Boolean(cols?.[c.key])} />
          ))}
          <ColumnChip label="State" found={Boolean(dq.state_column_present)} />
          <ColumnChip label="City" found={Boolean(dq.city_column_present)} />
        </div>
      </div>

      <div className="bg-white border border-slate-200 rounded-md p-5">
        <h3 className="font-display font-bold text-slate-900 mb-1">Row funnel</h3>
        <p className="text-xs text-slate-500 mb-4">How the raw file narrowed down to the rows this report is built from.</p>
        <div className="grid sm:grid-cols-4 gap-4">
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500 mb-1">Raw rows</p>
            <p className="font-display text-xl font-bold text-slate-900">{fmtInt(rawRows)}</p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500 mb-1">After test-lead exclusion</p>
            <p className="font-display text-xl font-bold text-slate-900">{fmtInt(afterTest)}</p>
            {dq.test_leads_excluded > 0 && (
              <p className="text-xs text-slate-500">{fmtInt(dq.test_leads_excluded)} excluded</p>
            )}
          </div>
          {hasDateFilter && (
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500 mb-1">After date filter</p>
              <p className="font-display text-xl font-bold text-slate-900">{fmtInt(analyzed)}</p>
              {dq.date_filtered_out > 0 && (
                <p className="text-xs text-slate-500">{fmtInt(dq.date_filtered_out)} outside range</p>
              )}
            </div>
          )}
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500 mb-1">Unclassified program</p>
            <p className={`font-display text-xl font-bold ${unclassifiedPct > 5 ? "text-amber-600" : "text-slate-900"}`}>
              {fmtPct1(unclassifiedPct)}
            </p>
            {unclassifiedPct > 5 && (
              <p className="text-xs text-amber-600 flex items-center gap-1 mt-0.5">
                <Warning size={12} weight="fill" /> Worth checking Settings → Programs
              </p>
            )}
          </div>
        </div>
      </div>

      {dq.data_date_min && dq.data_date_max && (
        <div className="bg-white border border-slate-200 rounded-md p-5">
          <h3 className="font-display font-bold text-slate-900 mb-1">Dates found in the file</h3>
          <p className="text-sm text-slate-700">
            {dq.data_date_min} to {dq.data_date_max}
            {hasDateFilter && (
              <span className="text-slate-500">
                {" "}(report filtered to {dq.date_range?.start || "the start"} – {dq.date_range?.end || "the end"})
              </span>
            )}
          </p>
        </div>
      )}
    </div>
  );
};
