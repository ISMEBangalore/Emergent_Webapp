import { useEffect, useState, useCallback, useRef, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import {
  ArrowLeft, CalendarBlank, ChartLineUp, CloudArrowUp, FloppyDisk, Trash, ArrowsLeftRight,
  CaretUp, CaretDown, CaretUpDown, Warning,
} from "@phosphor-icons/react";
import { fmtInt, fmtPct1 } from "@/lib/format";
import { rampColor } from "@/lib/geoColors";

const isoDaysAgo = (days) => {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
};
const yearStart = () => `${new Date().getFullYear()}-01-01`;
const today = () => new Date().toISOString().slice(0, 10);

// A season with no end date picks up the single latest report system-wide as its
// snapshot — correct for an ongoing season, but silently wrong for a closed one
// (it'll show whatever the newest report anywhere is, not that season's own data).
// Surfacing the saved range everywhere a season is shown makes that mistake visible.
function seasonRangeLabel(season) {
  if (!season) return "";
  return `${season.start || "no start"} → ${season.end || "no end"}`;
}

const Preset = ({ label, onClick, testid }) => (
  <button data-testid={testid} onClick={onClick}
          className="px-3 py-1.5 rounded-full border border-slate-200 text-sm text-slate-600 hover:border-[#002FA7] hover:text-[#002FA7] transition-colors">
    {label}
  </button>
);

const Chips = ({ options, value, onChange, testidPrefix }) => (
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

function withPct(row) {
  return {
    ...row,
    verification_pct: pct(row.verified_leads, row.total_leads),
    application_pct: pct(row.application, row.total_leads),
    admission_pct: pct(row.admission_fee_paid, row.application),
    joined_pct: pct(row.joined, row.admission_fee_paid),
  };
}

function mergeAllPrograms(funnel, programs) {
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

// Green -> amber -> red grading scale for the four conversion-rate columns, high
// to low (higher conversion always reads as "better"). Validated colorblind-safe
// via the dataviz skill's palette checker. The amber midpoint sits at 30% (not
// 50%) so the 30-100% band — where most real conversion rates here fall — reads
// as a gradual green-to-amber fade, while 0-30% is a narrower, faster red ramp
// that separates poor performers more sharply.
const GRADE_RAMP = ["#DC2626", "#F59E0B", "#10B981"];
const GRADE_STOPS = [0, 0.3, 1];
function gradeColor(pctVal) {
  if (pctVal === null || pctVal === undefined) return null;
  return rampColor(GRADE_RAMP, Math.max(0, Math.min(100, pctVal)) / 100, GRADE_STOPS);
}

function relLuminance(hex) {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  const lin = (c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}
function contrastRatio(hexA, hexB) {
  const [l1, l2] = [relLuminance(hexA), relLuminance(hexB)].sort((a, b) => b - a);
  return (l1 + 0.05) / (l2 + 0.05);
}
// Picks whichever of white/dark ink has higher contrast against a given fill,
// so text stays legible across the whole light-to-dark ramp.
function textOn(bgHex) {
  const white = "#ffffff", dark = "#0f172a";
  return contrastRatio(bgHex, white) >= contrastRatio(bgHex, dark) ? white : dark;
}

const GradeCell = ({ pctVal, bold }) => {
  const fill = gradeColor(pctVal);
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

const FunnelTable = ({ rows, testid }) => {
  const [sortKey, setSortKey] = useState("verification_pct");
  const [sortDir, setSortDir] = useState("desc");
  const toggleSort = (key) => {
    if (key === sortKey) { setSortDir((d) => (d === "desc" ? "asc" : "desc")); return; }
    setSortKey(key);
    setSortDir("desc");
  };
  const sorted = useMemo(() => sortRows(rows, sortKey, sortDir), [rows, sortKey, sortDir]);
  const t = totals(rows);
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
                  <GradeCell key={c.key} pctVal={r[c.key]} />
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
                  <GradeCell key={c.key} pctVal={t[c.key]} bold />
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

export default function VerifiedLeadAnalysis() {
  const nav = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [prog, setProg] = useState("All");

  const [seasons, setSeasons] = useState([]);
  const [activeSeasonId, setActiveSeasonId] = useState("live");
  const [saveOpen, setSaveOpen] = useState(false);
  const [seasonLabel, setSeasonLabel] = useState("");
  const [saving, setSaving] = useState(false);

  const [uploading, setUploading] = useState(false);
  const fileRef = useRef(null);

  const [compareA, setCompareA] = useState("");
  const [compareB, setCompareB] = useState("");
  const [compareProg, setCompareProg] = useState("All");
  const [compareDataA, setCompareDataA] = useState(null);
  const [compareDataB, setCompareDataB] = useState(null);
  const [compareLoading, setCompareLoading] = useState(false);

  const loadSeasons = useCallback(async () => {
    try {
      const s = await api.listSeasons();
      setSeasons(s || []);
    } catch {
      // seasons are a convenience layer — a failed fetch shouldn't block the live funnel
    }
  }, []);

  const loadLive = useCallback(async (s, e) => {
    setLoading(true);
    try {
      const params = {};
      if (s) params.start = s;
      if (e) params.end = e;
      const d = await api.getVerifiedLeadAnalysis(params);
      setData(d);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not load Verified Lead Analysis.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadLive("", ""); loadSeasons(); }, [loadLive, loadSeasons]);

  const selectSeason = async (value) => {
    setActiveSeasonId(value);
    if (value === "live") {
      loadLive(start, end);
      return;
    }
    setLoading(true);
    try {
      const d = await api.getSeasonAnalysis(value);
      setData(d);
      setStart(d.season?.start || "");
      setEnd(d.season?.end || "");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not load that season.");
    } finally {
      setLoading(false);
    }
  };

  const apply = () => { setActiveSeasonId("live"); loadLive(start, end); };
  const preset = (s, e) => { setStart(s); setEnd(e); setActiveSeasonId("live"); loadLive(s, e); };

  const saveSeason = async () => {
    const label = seasonLabel.trim();
    if (!label) { toast.error("Give this season a name, e.g. Analysis 2025-26."); return; }
    setSaving(true);
    try {
      const created = await api.createSeason({ label, start: start || null, end: end || null });
      toast.success(`Saved "${created.label}". It keeps recomputing live as new weeks come in.`);
      setSeasonLabel("");
      setSaveOpen(false);
      await loadSeasons();
      selectSeason(created.id);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not save this season.");
    } finally {
      setSaving(false);
    }
  };

  const deleteSeasonById = async (id, label) => {
    try {
      await api.deleteSeason(id);
      toast.success(`Deleted "${label}".`);
      if (activeSeasonId === id) selectSeason("live");
      await loadSeasons();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not delete this season.");
    }
  };

  const uploadJoined = async () => {
    const file = fileRef.current?.files?.[0];
    if (!file) { toast.error("Choose the final 'students who reported' file first."); return; }
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const params = {};
      if (start) params.start = start;
      if (end) params.end = end;
      const res = await api.uploadJoinedStudents(fd, params);
      toast.success(
        `Matched ${res.matched_count} of ${res.total_upload_rows} rows` +
        (res.unmatched_by_appno_count != null ? ` (${res.unmatched_by_appno_count} unmatched by Application No, checked by name too)` : "") + "."
      );
      if (fileRef.current) fileRef.current.value = "";
      if (activeSeasonId === "live") loadLive(start, end); else selectSeason(activeSeasonId);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Upload failed.");
    } finally {
      setUploading(false);
    }
  };

  const runCompare = async () => {
    if (!compareA || !compareB) { toast.error("Pick two seasons to compare."); return; }
    setCompareLoading(true);
    try {
      const [a, b] = await Promise.all([api.getSeasonAnalysis(compareA), api.getSeasonAnalysis(compareB)]);
      setCompareDataA(a);
      setCompareDataB(b);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not load one of the selected seasons.");
    } finally {
      setCompareLoading(false);
    }
  };

  const programs = data?.programs || [];
  const progOptions = ["All", ...programs];
  const rows = useMemo(() => {
    if (!data) return [];
    return prog === "All" ? mergeAllPrograms(data.funnel, data.programs || []) : (data.funnel?.[prog] || []);
  }, [data, prog]);

  const compareProgOptions = ["All", ...(compareDataA?.programs || compareDataB?.programs || [])];
  const compareRowsA = useMemo(() => {
    if (!compareDataA) return null;
    return compareProg === "All"
      ? mergeAllPrograms(compareDataA.funnel, compareDataA.programs)
      : (compareDataA.funnel?.[compareProg] || []);
  }, [compareDataA, compareProg]);
  const compareRowsB = useMemo(() => {
    if (!compareDataB) return null;
    return compareProg === "All"
      ? mergeAllPrograms(compareDataB.funnel, compareDataB.programs)
      : (compareDataB.funnel?.[compareProg] || []);
  }, [compareDataB, compareProg]);

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <button onClick={() => nav(-1)} className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-[#002FA7] mb-4" data-testid="back-btn">
        <ArrowLeft size={16} weight="bold" /> Back
      </button>

      <div className="flex items-center gap-2 mb-1">
        <ChartLineUp size={26} weight="bold" color="#002FA7" />
        <h1 className="font-display text-3xl font-extrabold tracking-tight text-slate-900" data-testid="vla-title">
          Verified Lead Analysis
        </h1>
      </div>
      <p className="text-slate-500 mt-1 mb-5">
        Publisher x program funnel: Total Leads and Verified Leads come from the weekly reports, Application and
        Admission Fee Paid from payment-approved applications, and Joined from the final students-who-reported list
        you upload — the CRM's own Enrolment Status isn't kept up to date, so it isn't used here.
      </p>

      <Tabs defaultValue="funnel" data-testid="vla-tabs">
        <TabsList className="bg-slate-100 flex-wrap h-auto mb-5">
          <TabsTrigger value="funnel" data-testid="vla-tab-funnel">Funnel</TabsTrigger>
          <TabsTrigger value="compare" data-testid="vla-tab-compare">Compare Seasons</TabsTrigger>
        </TabsList>

        <TabsContent value="funnel">
          <div className="bg-white border border-slate-200 rounded-md p-5 mb-6">
            <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
              <div className="flex items-center gap-2">
                <CalendarBlank size={18} weight="bold" color="#002FA7" />
                <h3 className="font-display font-bold text-slate-900">Range / Season</h3>
              </div>
              <div className="flex items-center gap-2">
                <Select value={activeSeasonId} onValueChange={selectSeason}>
                  <SelectTrigger className="w-56" data-testid="vla-season-select">
                    <SelectValue placeholder="Live (current filters)" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="live">Live (current filters)</SelectItem>
                    {seasons.map((s) => (
                      <SelectItem key={s.id} value={s.id}>
                        {s.label} <span className="text-slate-400">({seasonRangeLabel(s)})</span>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button
                  variant="outline" size="sm" data-testid="vla-save-season-btn"
                  onClick={() => setSaveOpen((v) => !v)}
                  className="gap-1.5"
                >
                  <FloppyDisk size={16} weight="bold" /> Save as Season
                </Button>
                {activeSeasonId !== "live" && (
                  <Button
                    variant="outline" size="sm" data-testid="vla-delete-season-btn"
                    onClick={() => {
                      const s = seasons.find((x) => x.id === activeSeasonId);
                      if (s) deleteSeasonById(s.id, s.label);
                    }}
                    className="gap-1.5 text-red-600 hover:text-red-700"
                  >
                    <Trash size={16} weight="bold" />
                  </Button>
                )}
              </div>
            </div>

            {saveOpen && (
              <div className="mb-4 p-3 bg-slate-50 rounded-md border border-slate-200">
                <div className="flex flex-wrap items-end gap-3">
                  <div>
                    <Label className="text-xs uppercase tracking-wide text-slate-500">Season name</Label>
                    <Input
                      data-testid="vla-season-label-input" value={seasonLabel}
                      onChange={(e) => setSeasonLabel(e.target.value)}
                      placeholder="Analysis 2025-26" className="mt-1 w-56"
                    />
                  </div>
                  <p className="text-xs text-slate-500 pb-2">
                    Will save as <strong>{seasonRangeLabel({ start, end })}</strong>. Numbers keep recomputing live as new weeks are uploaded.
                  </p>
                  <Button data-testid="vla-save-season-confirm" onClick={saveSeason} disabled={saving} className="bg-[#002FA7] hover:bg-[#002FA7]/90">
                    {saving ? "Saving…" : "Save"}
                  </Button>
                </div>
                {!end && (
                  <div className="flex items-start gap-2 mt-3 px-3 py-2 rounded-md bg-red-50 border border-red-200 text-red-800 text-xs" data-testid="vla-season-no-end-warning">
                    <Warning size={15} weight="fill" className="mt-0.5 shrink-0" />
                    <span>
                      No <strong>To</strong> date is set — this season will always show whichever report is the single
                      latest one system-wide, not scoped to this period. That's correct for your current, still-running
                      season, but wrong for a closed/historical one (it'll silently show a different season's data
                      instead of its own). Set a To date first if this season is meant to be a bounded, past period.
                    </span>
                  </div>
                )}
                {end && !start && (
                  <div className="flex items-start gap-2 mt-3 px-3 py-2 rounded-md bg-amber-50 border border-amber-200 text-amber-800 text-xs" data-testid="vla-season-no-start-warning">
                    <Warning size={15} weight="fill" className="mt-0.5 shrink-0" />
                    <span>
                      No <strong>From</strong> date is set — minor, but a few stray records from well before this
                      period (data-entry outliers, old test rows) could get counted in Application/Admission Fee Paid.
                    </span>
                  </div>
                )}
              </div>
            )}

            <fieldset disabled={activeSeasonId !== "live"} className={activeSeasonId !== "live" ? "opacity-50" : ""}>
              <div className="flex flex-wrap items-end gap-3">
                <div>
                  <Label className="text-xs uppercase tracking-wide text-slate-500">From</Label>
                  <Input data-testid="vla-range-start" type="date" value={start} onChange={(e) => setStart(e.target.value)} className="mt-1 w-44" />
                </div>
                <div>
                  <Label className="text-xs uppercase tracking-wide text-slate-500">To</Label>
                  <Input data-testid="vla-range-end" type="date" value={end} onChange={(e) => setEnd(e.target.value)} className="mt-1 w-44" />
                </div>
                <Button data-testid="vla-range-apply" onClick={apply} className="bg-[#002FA7] hover:bg-[#002FA7]/90">Apply</Button>
              </div>
              <div className="flex flex-wrap gap-2 mt-4">
                <Preset label="All time" onClick={() => preset("", "")} testid="vla-preset-all" />
                <Preset label="This year" onClick={() => preset(yearStart(), today())} testid="vla-preset-year" />
                <Preset label="Last 4 weeks" onClick={() => preset(isoDaysAgo(28), today())} testid="vla-preset-4w" />
                <Preset label="Last 12 weeks" onClick={() => preset(isoDaysAgo(84), today())} testid="vla-preset-12w" />
              </div>
            </fieldset>
          </div>

          <div className="bg-white border border-slate-200 rounded-md p-5 mb-6">
            <div className="flex items-center gap-2 mb-3">
              <CloudArrowUp size={18} weight="bold" color="#002FA7" />
              <h3 className="font-display font-bold text-slate-900">Upload Joined Students</h3>
            </div>
            <p className="text-xs text-slate-500 mb-3">
              Final list of students who actually reported/joined (post refunds &amp; cancellations) — matched by
              Application No first, then by Name. Marks those applicant records as Joined.
            </p>
            <div className="flex flex-wrap items-center gap-3">
              <input ref={fileRef} type="file" accept=".xlsx,.xls,.csv" data-testid="vla-joined-file-input"
                     className="text-sm text-slate-600" />
              <Button data-testid="vla-joined-upload-btn" onClick={uploadJoined} disabled={uploading} variant="outline">
                {uploading ? "Uploading…" : "Upload & Match"}
              </Button>
            </div>
          </div>

          {loading ? (
            <div className="h-72 bg-slate-100 rounded-md animate-pulse" />
          ) : (
            <>
              <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
                <Chips options={progOptions} value={prog} onChange={setProg} testidPrefix="vla-prog" />
                <p className="text-xs text-slate-400">
                  {fmtInt(data?.reports_included)} report{data?.reports_included === 1 ? "" : "s"} · {fmtInt(data?.applications_included)} application{data?.applications_included === 1 ? "" : "s"} in range
                </p>
              </div>
              <div className="bg-white border border-slate-200 rounded-md p-5">
                <FunnelTable rows={rows} testid="vla-funnel-table" />
              </div>
            </>
          )}
        </TabsContent>

        <TabsContent value="compare">
          <div className="bg-white border border-slate-200 rounded-md p-5 mb-6">
            <div className="flex items-center gap-2 mb-4">
              <ArrowsLeftRight size={18} weight="bold" color="#002FA7" />
              <h3 className="font-display font-bold text-slate-900">Compare two seasons</h3>
            </div>
            {seasons.length < 2 ? (
              <p className="text-sm text-slate-500" data-testid="vla-compare-empty">
                Save at least two seasons (e.g. "Analysis 2025-26" and "Analysis 2024-25") on the Funnel tab first.
              </p>
            ) : (
              <>
                <div className="flex flex-wrap items-end gap-3">
                  <div>
                    <Label className="text-xs uppercase tracking-wide text-slate-500">Season A</Label>
                    <Select value={compareA} onValueChange={setCompareA}>
                      <SelectTrigger className="w-56 mt-1" data-testid="vla-compare-a-select"><SelectValue placeholder="Choose season" /></SelectTrigger>
                      <SelectContent>{seasons.map((s) => <SelectItem key={s.id} value={s.id}>{s.label}</SelectItem>)}</SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label className="text-xs uppercase tracking-wide text-slate-500">Season B</Label>
                    <Select value={compareB} onValueChange={setCompareB}>
                      <SelectTrigger className="w-56 mt-1" data-testid="vla-compare-b-select"><SelectValue placeholder="Choose season" /></SelectTrigger>
                      <SelectContent>{seasons.map((s) => <SelectItem key={s.id} value={s.id}>{s.label}</SelectItem>)}</SelectContent>
                    </Select>
                  </div>
                  <Button data-testid="vla-compare-run" onClick={runCompare} disabled={compareLoading} className="bg-[#002FA7] hover:bg-[#002FA7]/90">
                    {compareLoading ? "Loading…" : "Compare"}
                  </Button>
                </div>

                {(compareDataA || compareDataB) && (
                  <div className="mt-4">
                    <Chips options={compareProgOptions} value={compareProg} onChange={setCompareProg} testidPrefix="vla-compare-prog" />
                  </div>
                )}
              </>
            )}
          </div>

          {compareDataA && compareDataB && (
            <>
              {compareDataA.season?.id === compareDataB.season?.id && (
                <div className="flex items-start gap-2 mb-4 px-4 py-3 rounded-md bg-red-50 border border-red-200 text-red-800 text-sm" data-testid="vla-compare-same-season-warning">
                  <Warning size={16} weight="fill" className="mt-0.5 shrink-0" />
                  <span>Season A and Season B are the same saved season — pick two different ones to compare.</span>
                </div>
              )}
              <div className="grid lg:grid-cols-2 gap-4">
                <div className="bg-white border border-slate-200 rounded-md p-5">
                  <h4 className="text-sm font-bold text-slate-800">{compareDataA.season?.label}</h4>
                  <p className="text-xs text-slate-400 mb-3">{seasonRangeLabel(compareDataA.season)}</p>
                  <FunnelTable rows={compareRowsA || []} testid="vla-compare-table-a" />
                </div>
                <div className="bg-white border border-slate-200 rounded-md p-5">
                  <h4 className="text-sm font-bold text-slate-800">{compareDataB.season?.label}</h4>
                  <p className="text-xs text-slate-400 mb-3">{seasonRangeLabel(compareDataB.season)}</p>
                  <FunnelTable rows={compareRowsB || []} testid="vla-compare-table-b" />
                </div>
              </div>
            </>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
