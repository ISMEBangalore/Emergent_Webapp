import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { ReportTabs } from "@/components/ReportTabs";
import { KpiCards } from "@/components/KpiCards";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { DownloadSimple, ArrowLeft, ChartLineUp, CalendarBlank } from "@phosphor-icons/react";

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
        <Button
          data-testid="export-cumulative-btn"
          className="bg-[#002FA7] hover:bg-[#002FA7]/90 gap-2"
          onClick={() => api.downloadCumulative({ start, end }).catch(() => toast.error("Could not download the export."))}
        >
          <DownloadSimple size={18} weight="bold" /> Export to Excel
        </Button>
      </div>

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
