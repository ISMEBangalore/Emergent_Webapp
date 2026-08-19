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
} from "@phosphor-icons/react";
import { fmtInt, fmtPct1 } from "@/lib/format";

const isoDaysAgo = (days) => {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
};
const yearStart = () => `${new Date().getFullYear()}-01-01`;
const today = () => new Date().toISOString().slice(0, 10);

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
  return Object.values(map).sort((a, b) => b.application - a.application);
}

function totals(rows) {
  return rows.reduce((t, r) => ({
    total_leads: t.total_leads + r.total_leads,
    verified_leads: t.verified_leads + r.verified_leads,
    application: t.application + r.application,
    admission_fee_paid: t.admission_fee_paid + r.admission_fee_paid,
    joined: t.joined + r.joined,
  }), { total_leads: 0, verified_leads: 0, application: 0, admission_fee_paid: 0, joined: 0 });
}

const FunnelTable = ({ rows, testid }) => {
  const t = totals(rows);
  return (
    <div className="overflow-x-auto thin-scroll">
      <table className="border-collapse min-w-full" data-testid={testid}>
        <thead>
          <tr>
            <th className={`${cell} bg-[#9DC3E6] text-left font-bold`}>Source (Publisher)</th>
            <th className={`${cell} bg-[#C6EFCE] text-right font-bold`}>Total Leads</th>
            <th className={`${cell} bg-[#C6EFCE] text-right font-bold`}>Verified Leads</th>
            <th className={`${cell} bg-[#C6EFCE] text-right font-bold`}>Application</th>
            <th className={`${cell} bg-[#C6EFCE] text-right font-bold`}>Admission Fee Paid</th>
            <th className={`${cell} bg-[#FFE699] text-right font-bold`}>Joined</th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr><td className={`${cell} text-slate-400 text-center`} colSpan={6}>No data in this range.</td></tr>
          ) : rows.map((r) => (
            <tr key={r.publisher} className="hover:bg-slate-50">
              <td className={`${cell} font-medium text-slate-800`}>{r.publisher}</td>
              <td className={`${cell} text-right`}>{fmtInt(r.total_leads)}</td>
              <td className={`${cell} text-right`}>{fmtInt(r.verified_leads)}</td>
              <td className={`${cell} text-right`}>{fmtInt(r.application)}</td>
              <td className={`${cell} text-right`}>{fmtInt(r.admission_fee_paid)}</td>
              <td className={`${cell} text-right font-semibold text-emerald-700`}>{fmtInt(r.joined)}</td>
            </tr>
          ))}
        </tbody>
        {rows.length > 0 && (
          <tfoot>
            <tr className="bg-slate-50 font-bold">
              <td className={cell}>Total</td>
              <td className={`${cell} text-right`}>{fmtInt(t.total_leads)}</td>
              <td className={`${cell} text-right`}>{fmtInt(t.verified_leads)}</td>
              <td className={`${cell} text-right`}>{fmtInt(t.application)}</td>
              <td className={`${cell} text-right`}>{fmtInt(t.admission_fee_paid)}</td>
              <td className={`${cell} text-right text-emerald-700`}>{fmtInt(t.joined)}</td>
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
                      <SelectItem key={s.id} value={s.id}>{s.label}</SelectItem>
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
              <div className="flex flex-wrap items-end gap-3 mb-4 p-3 bg-slate-50 rounded-md border border-slate-200">
                <div>
                  <Label className="text-xs uppercase tracking-wide text-slate-500">Season name</Label>
                  <Input
                    data-testid="vla-season-label-input" value={seasonLabel}
                    onChange={(e) => setSeasonLabel(e.target.value)}
                    placeholder="Analysis 2025-26" className="mt-1 w-56"
                  />
                </div>
                <p className="text-xs text-slate-500 pb-2">Saves the current date range below as a named view. Numbers keep recomputing live as new weeks are uploaded.</p>
                <Button data-testid="vla-save-season-confirm" onClick={saveSeason} disabled={saving} className="bg-[#002FA7] hover:bg-[#002FA7]/90">
                  {saving ? "Saving…" : "Save"}
                </Button>
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
            <div className="grid lg:grid-cols-2 gap-4">
              <div className="bg-white border border-slate-200 rounded-md p-5">
                <h4 className="text-sm font-bold text-slate-800 mb-3">{compareDataA.season?.label}</h4>
                <FunnelTable rows={compareRowsA || []} testid="vla-compare-table-a" />
              </div>
              <div className="bg-white border border-slate-200 rounded-md p-5">
                <h4 className="text-sm font-bold text-slate-800 mb-3">{compareDataB.season?.label}</h4>
                <FunnelTable rows={compareRowsB || []} testid="vla-compare-table-b" />
              </div>
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
