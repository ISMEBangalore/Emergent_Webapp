import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { ReportTabs } from "@/components/ReportTabs";
import { KpiCards } from "@/components/KpiCards";
import { Button } from "@/components/ui/button";
import { DownloadSimple, ArrowLeft, ChartLineUp } from "@phosphor-icons/react";

export default function CumulativeView() {
  const nav = useNavigate();
  const [doc, setDoc] = useState(null);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { api.getCumulative().then(setDoc); }, []);

  if (!doc) return <div className="p-8"><div className="h-96 bg-slate-100 rounded-md animate-pulse" /></div>;

  const empty = !doc.result?.matrix?.length || doc.kpis?.total_leads === 0;

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <button onClick={() => nav(-1)} className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-[#002FA7] mb-4" data-testid="back-btn">
        <ArrowLeft size={16} weight="bold" /> Back
      </button>

      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <div>
          <div className="flex items-center gap-2">
            <ChartLineUp size={26} weight="bold" color="#002FA7" />
            <h1 className="font-display text-3xl font-extrabold tracking-tight text-slate-900">{doc.week_label}</h1>
          </div>
          <p className="text-slate-500 mt-1">Cumulative totals across all generated weekly reports.</p>
        </div>
        <a href={api.cumulativeExportUrl()} data-testid="export-cumulative-btn">
          <Button className="bg-[#002FA7] hover:bg-[#002FA7]/90 gap-2">
            <DownloadSimple size={18} weight="bold" /> Export to Excel
          </Button>
        </a>
      </div>

      {empty ? (
        <div className="bg-white border border-dashed border-slate-300 rounded-md p-12 text-center text-slate-500">
          No report data yet. Generate at least one weekly report first.
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
