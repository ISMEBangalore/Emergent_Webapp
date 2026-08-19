import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { ReportTabs } from "@/components/ReportTabs";
import { KpiCards } from "@/components/KpiCards";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { DownloadSimple, ArrowLeft, ChartLineUp, CalendarBlank, Archive, Warning } from "@phosphor-icons/react";
import { seasonRangeLabel } from "@/components/VerifiedLeadFunnelTable";

const isoDaysAgo = (days) => {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
};
const yearStart = () => `${new Date().getFullYear()}-01-01`;
const today = () => new Date().toISOString().slice(0, 10);

export default function CumulativeView() {
  const nav = useNavigate();
  const [doc, setDoc] = useState(null);
  const [loading, setLoading] = useState(true);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [topPublishers, setTopPublishers] = useState("0");

  const [archiveOpen, setArchiveOpen] = useState(false);
  const [archiveLabel, setArchiveLabel] = useState("");
  const [archiving, setArchiving] = useState(false);

  const load = useCallback(async (s, e) => {
    setLoading(true);
    try {
      const params = {};
      if (s) params.start = s;
      if (e) params.end = e;
      const d = await api.getCumulative(params);
      setDoc(d);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not load the report. Please try again.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load("", ""); }, [load]);

  const apply = () => load(start, end);
  const preset = (s, e) => { setStart(s); setEnd(e); load(s, e); };

  const archiveReport = async () => {
    const label = archiveLabel.trim();
    if (!label) { toast.error("Give this archived report a name, e.g. Analysis 2024-25."); return; }
    setArchiving(true);
    try {
      const created = await api.createSeason({ label, start: start || null, end: end || null });
      await api.freezeSeason(created.id);
      toast.success(`Archived "${label}" — it's now a permanent snapshot in Season Archive.`);
      setArchiveLabel("");
      setArchiveOpen(false);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not archive this report.");
    } finally {
      setArchiving(false);
    }
  };

  const empty = !doc?.result?.matrix?.length || doc?.kpis?.total_leads === 0;

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <button onClick={() => nav(-1)} className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-[#002FA7] mb-4" data-testid="back-btn">
        <ArrowLeft size={16} weight="bold" /> Back
      </button>

      <div className="flex flex-wrap items-center justify-between gap-3 mb-5">
        <div>
          <div className="flex items-center gap-2">
            <ChartLineUp size={26} weight="bold" color="#002FA7" />
            <h1 className="font-display text-3xl font-extrabold tracking-tight text-slate-900" data-testid="cumulative-title">
              {doc?.week_label || "Report Till Date"}
            </h1>
          </div>
          <p className="text-slate-500 mt-1">Aggregate every weekly report in a date range — leave dates empty for all-time.</p>
        </div>
        <div className="flex items-end gap-2">
          <div>
            <label className="text-xs uppercase tracking-wide text-slate-500">Programs per publisher</label>
            <Select value={topPublishers} onValueChange={setTopPublishers}>
              <SelectTrigger data-testid="export-top-publishers" className="mt-1 w-40"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="0">Off</SelectItem>
                <SelectItem value="5">Top 5 publishers</SelectItem>
                <SelectItem value="10">Top 10 publishers</SelectItem>
                <SelectItem value="15">Top 15 publishers</SelectItem>
                <SelectItem value="20">Top 20 publishers</SelectItem>
                <SelectItem value="999">All publishers</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <Button
            variant="outline" data-testid="archive-report-btn" className="gap-2"
            onClick={() => setArchiveOpen((v) => !v)}
          >
            <Archive size={18} weight="bold" /> Archive this report
          </Button>
          <Button
            data-testid="export-cumulative-btn"
            className="bg-[#002FA7] hover:bg-[#002FA7]/90 gap-2"
            onClick={() => api.downloadCumulative({ start, end, top_publishers: Number(topPublishers) })
              .catch(() => toast.error("Could not download the export."))}
          >
            <DownloadSimple size={18} weight="bold" /> Export to Excel
          </Button>
        </div>
      </div>

      {archiveOpen && (
        <div className="bg-white border border-slate-200 rounded-md p-5 mb-6" data-testid="archive-report-panel">
          <div className="flex items-center gap-2 mb-3">
            <Archive size={18} weight="bold" color="#002FA7" />
            <h3 className="font-display font-bold text-slate-900">Archive this report</h3>
          </div>
          <p className="text-xs text-slate-500 mb-3">
            Saves this exact date range as a permanent, frozen snapshot in Season Archive — the full report and its
            Verified Lead Analysis funnel both get stored once and stop depending on the underlying weekly reports,
            so you can reopen it any time without recomputing.
          </p>
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <Label className="text-xs uppercase tracking-wide text-slate-500">Name</Label>
              <Input
                data-testid="archive-report-label-input" value={archiveLabel}
                onChange={(e) => setArchiveLabel(e.target.value)}
                placeholder="Analysis 2024-25" className="mt-1 w-56"
              />
            </div>
            <p className="text-xs text-slate-500 pb-2">
              Will save as <strong>{seasonRangeLabel({ start, end })}</strong>.
            </p>
            <Button data-testid="archive-report-confirm" onClick={archiveReport} disabled={archiving} className="bg-[#002FA7] hover:bg-[#002FA7]/90 gap-2">
              <Archive size={16} weight="bold" /> {archiving ? "Archiving…" : "Archive"}
            </Button>
          </div>
          {!end && (
            <div className="flex items-start gap-2 mt-3 px-3 py-2 rounded-md bg-red-50 border border-red-200 text-red-800 text-xs" data-testid="archive-report-no-end-warning">
              <Warning size={15} weight="fill" className="mt-0.5 shrink-0" />
              <span>
                No <strong>To</strong> date is set — this will freeze whatever is the single latest data system-wide,
                not a bounded historical period. Set a To date first if this is meant to be a closed period (e.g. a
                finished admissions cycle).
              </span>
            </div>
          )}
          {end && !start && (
            <div className="flex items-start gap-2 mt-3 px-3 py-2 rounded-md bg-amber-50 border border-amber-200 text-amber-800 text-xs" data-testid="archive-report-no-start-warning">
              <Warning size={15} weight="fill" className="mt-0.5 shrink-0" />
              <span>
                No <strong>From</strong> date is set — minor, but stray records from well before this period could
                get counted in.
              </span>
            </div>
          )}
        </div>
      )}

      <div className="bg-white border border-slate-200 rounded-md p-5 mb-6">
        <div className="flex items-center gap-2 mb-3">
          <CalendarBlank size={18} weight="bold" color="#002FA7" />
          <h3 className="font-display font-bold text-slate-900">Date range</h3>
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <Label className="text-xs uppercase tracking-wide text-slate-500">From</Label>
            <Input data-testid="range-start" type="date" value={start} onChange={(e) => setStart(e.target.value)} className="mt-1 w-44" />
          </div>
          <div>
            <Label className="text-xs uppercase tracking-wide text-slate-500">To</Label>
            <Input data-testid="range-end" type="date" value={end} onChange={(e) => setEnd(e.target.value)} className="mt-1 w-44" />
          </div>
          <Button data-testid="range-apply" onClick={apply} className="bg-[#002FA7] hover:bg-[#002FA7]/90">Apply</Button>
        </div>
        <div className="flex flex-wrap gap-2 mt-4">
          <Preset label="All time" onClick={() => preset("", "")} testid="preset-all" />
          <Preset label="This year" onClick={() => preset(yearStart(), today())} testid="preset-year" />
          <Preset label="Last 4 weeks" onClick={() => preset(isoDaysAgo(28), today())} testid="preset-4w" />
          <Preset label="Last 12 weeks" onClick={() => preset(isoDaysAgo(84), today())} testid="preset-12w" />
        </div>
      </div>

      {loading ? (
        <div className="h-72 bg-slate-100 rounded-md animate-pulse" />
      ) : empty ? (
        <div className="bg-white border border-dashed border-slate-300 rounded-md p-12 text-center text-slate-500" data-testid="cumulative-empty">
          No report data in this range. Generate/upload weekly reports whose dates fall within it.
        </div>
      ) : (
        <>
          <KpiCards kpis={doc.kpis} />
          <ReportTabs result={doc.result} />
        </>
      )}
    </div>
  );
}

const Preset = ({ label, onClick, testid }) => (
  <button data-testid={testid} onClick={onClick}
          className="px-3 py-1.5 rounded-full border border-slate-200 text-sm text-slate-600 hover:border-[#002FA7] hover:text-[#002FA7] transition-colors">
    {label}
  </button>
);
