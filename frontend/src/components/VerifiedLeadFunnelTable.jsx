import { useState, useMemo } from "react";
import { CaretUp, CaretDown, CaretUpDown } from "@phosphor-icons/react";
import { fmtInt, fmtPct1 } from "@/lib/format";
import { gradeColor, rangeOf, textOn } from "@/lib/geoColors";

// A season with no end date picks up the single latest report system-wide as its
// snapshot — correct for an ongoing season, but silently wrong for a closed one
// (it'll show whatever the newest report anywhere is, not that season's own data).
// Surfacing the saved range everywhere a season is shown makes that mistake visible.
export function seasonRangeLabel(season) {
  if (!season) return "";
  return `${season.start || "no start"} → ${season.end || "no end"}`;
}

export const Chips = ({ options, value, onChange, testidPrefix }) => (
  <div className="flex flex-wrap items-center gap-2" data-testid={`${testidPrefix}-filter`}>
    <span className="text-xs uppercase tracking-wide text-slate-500 mr-1">Program:</span>
    {options.map((opt) => (
      <button
        key={opt}
        data-testid={`${testidPrefix}-${opt}`}
        onClick={() => onChange(opt)}
        className={`px-3 py-1 rounded-full text-sm border transition-colors ${
          value === opt
            ? "bg-[#002FA7] text-white border-[#002FA7]"
            : "border-slate-200 text-slate-600 hover:border-[#002FA7] hover:text-[#002FA7]"
        }`}
      >
        {opt}
      </button>
    ))}
  </div>
);

const cell = "border border-slate-200 px-3 py-1.5 text-sm whitespace-nowrap";

// Matches the backend's rounding (round(num/den*100, 2)) so client-computed totals
// and the "All programs" merge display at the same precision as server-computed rows.
const pct = (num, den) => (den ? Math.round((num / den) * 10000) / 100 : null);

export function withPct(row) {
  return {
    ...row,
    verification_pct: pct(row.verified_leads, row.total_leads),
    application_pct: pct(row.application, row.total_leads),
    admission_pct: pct(row.admission_fee_paid, row.application),
    joined_pct: pct(row.joined, row.admission_fee_paid),
  };
}

export function mergeAllPrograms(funnel, programs) {
  const map = {};
  for (const p of programs) {
    for (const row of funnel?.[p] || []) {
      const cur = map[row.publisher] || {
        publisher: row.publisher, total_leads: 0, verified_leads: 0,
        application: 0, admission_fee_paid: 0, joined: 0,
      };
      cur.total_leads += row.total_leads;
      cur.verified_leads += row.verified_leads;
      cur.application += row.application;
      cur.admission_fee_paid += row.admission_fee_paid;
      cur.joined += row.joined;
      map[row.publisher] = cur;
    }
  }
  return Object.values(map).map(withPct);
}

const GradeCell = ({ pctVal, min, max, bold }) => {
  const fill = gradeColor(pctVal, min, max);
  return (
    <td
      className={`${cell} text-right ${bold ? "font-bold" : ""}`}
      style={fill ? { backgroundColor: fill, color: textOn(fill) } : undefined}
    >
      {fmtPct1(pctVal)}
    </td>
  );
};

// One row of truth for every column: key into a data row, header label/color,
// and whether it's a percentage (graded + rendered via GradeCell) or a plain count.
const COLUMNS = [
  { key: "publisher", label: "Source (Publisher)", headerClass: "bg-[#9DC3E6] text-left" },
  { key: "total_leads", label: "Total Leads", headerClass: "bg-[#C6EFCE] text-right" },
  { key: "verified_leads", label: "Verified Leads", headerClass: "bg-[#C6EFCE] text-right" },
  { key: "verification_pct", label: "Verification %", headerClass: "bg-slate-100 text-right", pct: true },
  { key: "application", label: "Application", headerClass: "bg-[#C6EFCE] text-right" },
  { key: "application_pct", label: "Application %", headerClass: "bg-slate-100 text-right", pct: true },
  { key: "admission_fee_paid", label: "Admission Fee Paid", headerClass: "bg-[#C6EFCE] text-right" },
  { key: "admission_pct", label: "Admissions %", headerClass: "bg-slate-100 text-right", pct: true },
  { key: "joined", label: "Joined", headerClass: "bg-[#FFE699] text-right", emphasis: true },
  { key: "joined_pct", label: "Joined %", headerClass: "bg-slate-100 text-right", pct: true },
];
const PCT_KEYS = COLUMNS.filter((c) => c.pct).map((c) => c.key);

// Nulls (no leads/applications to compute a ratio from) always sort last, in
// either direction, rather than being confused with a genuine 0.
function sortRows(rows, key, dir) {
  const sign = dir === "asc" ? 1 : -1;
  return [...rows].sort((a, b) => {
    if (key === "publisher") {
      const cmp = String(a.publisher).localeCompare(String(b.publisher));
      return sign * cmp;
    }
    const av = a[key], bv = b[key];
    if (av == null && bv == null) return 0;
    if (av == null) return 1;
    if (bv == null) return -1;
    return sign * (av - bv);
  });
}

const SortIndicator = ({ active, dir }) => {
  if (!active) return <CaretUpDown size={12} weight="bold" className="text-slate-400" />;
  return dir === "asc"
    ? <CaretUp size={12} weight="bold" className="text-[#002FA7]" />
    : <CaretDown size={12} weight="bold" className="text-[#002FA7]" />;
};

function totals(rows) {
  const t = rows.reduce((t, r) => ({
    total_leads: t.total_leads + r.total_leads,
    verified_leads: t.verified_leads + r.verified_leads,
    application: t.application + r.application,
    admission_fee_paid: t.admission_fee_paid + r.admission_fee_paid,
    joined: t.joined + r.joined,
  }), { total_leads: 0, verified_leads: 0, application: 0, admission_fee_paid: 0, joined: 0 });
  return withPct(t);
}

export const FunnelTable = ({ rows, testid }) => {
  const [sortKey, setSortKey] = useState("verification_pct");
  const [sortDir, setSortDir] = useState("desc");
  const toggleSort = (key) => {
    if (key === sortKey) { setSortDir((d) => (d === "desc" ? "asc" : "desc")); return; }
    setSortKey(key);
    setSortDir("desc");
  };
  const sorted = useMemo(() => sortRows(rows, sortKey, sortDir), [rows, sortKey, sortDir]);
  const t = totals(rows);
  // Per-column range, from the individual publisher rows only (not the Total row) —
  // so "green" always means "the best publisher actually on screen right now".
  const ranges = useMemo(() => {
    const r = {};
    for (const k of PCT_KEYS) r[k] = rangeOf(sorted.map((row) => row[k]));
    return r;
  }, [sorted]);
  return (
    <div className="overflow-x-auto thin-scroll">
      <table className="border-collapse min-w-full" data-testid={testid}>
        <thead>
          <tr>
            {COLUMNS.map((c) => (
              <th
                key={c.key}
                data-testid={`${testid}-sort-${c.key}`}
                onClick={() => toggleSort(c.key)}
                className={`${cell} ${c.headerClass} font-bold cursor-pointer select-none hover:brightness-95`}
              >
                <span className={`inline-flex items-center gap-1 ${c.headerClass.includes("text-left") ? "" : "justify-end w-full"}`}>
                  {c.label}
                  <SortIndicator active={sortKey === c.key} dir={sortDir} />
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.length === 0 ? (
            <tr><td className={`${cell} text-slate-400 text-center`} colSpan={COLUMNS.length}>No data in this range.</td></tr>
          ) : sorted.map((r) => (
            <tr key={r.publisher} className="hover:bg-slate-50">
              {COLUMNS.map((c) => (
                c.pct ? (
                  <GradeCell key={c.key} pctVal={r[c.key]} min={ranges[c.key].min} max={ranges[c.key].max} />
                ) : c.key === "publisher" ? (
                  <td key={c.key} className={`${cell} font-medium text-slate-800`}>{r.publisher}</td>
                ) : (
                  <td key={c.key} className={`${cell} text-right ${c.emphasis ? "font-semibold text-emerald-700" : ""}`}>
                    {fmtInt(r[c.key])}
                  </td>
                )
              ))}
            </tr>
          ))}
        </tbody>
        {sorted.length > 0 && (
          <tfoot>
            <tr className="bg-slate-50 font-bold">
              {COLUMNS.map((c) => (
                c.pct ? (
                  <GradeCell key={c.key} pctVal={t[c.key]} min={ranges[c.key].min} max={ranges[c.key].max} bold />
                ) : c.key === "publisher" ? (
                  <td key={c.key} className={cell}>Total</td>
                ) : (
                  <td key={c.key} className={`${cell} text-right ${c.emphasis ? "text-emerald-700" : ""}`}>
                    {fmtInt(t[c.key])}
                  </td>
                )
              ))}
            </tr>
          </tfoot>
        )}
      </table>
    </div>
  );
};
