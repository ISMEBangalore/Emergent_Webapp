import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { StatusBadge } from "@/pages/Dashboard";
import { fmtInt, fmtMoney } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { Trash, ArrowRight, ClockCounterClockwise, ChartLineUp, ArrowsDownUp } from "@phosphor-icons/react";
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, Legend,
} from "recharts";

export default function History() {
  const nav = useNavigate();
  const [reports, setReports] = useState([]);
  const [trends, setTrends] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    setReports(await api.listReports());
    setTrends(await api.trends());
    setLoading(false);
  };
  useEffect(() => { load(); }, []);

  const del = async (id, e) => {
    e.stopPropagation();
    if (!window.confirm("Delete this report?")) return;
    await api.deleteReport(id);
    toast.success("Report deleted");
    load();
  };

  const trendData = trends.map((t) => ({
    name: (t.week_label || t.week_date)?.slice(0, 18),
    Leads: t.kpis?.total_leads || 0,
    Applications: t.kpis?.total_applications || 0,
    CPA: t.kpis?.blended_cpa || 0,
  }));

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="font-display text-3xl font-extrabold tracking-tight text-slate-900">History</h1>
          <p className="text-slate-500 mt-1 mb-6">All generated weekly reports and week-over-week trends.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button data-testid="hist-compare-btn" variant="outline" onClick={() => nav("/compare")} className="gap-2">
            <ArrowsDownUp size={16} weight="bold" /> Compare weeks
          </Button>
          <Button data-testid="hist-tilldate-btn" variant="outline" onClick={() => nav("/cumulative")} className="gap-2">
            <ChartLineUp size={16} weight="bold" /> Report till date
          </Button>
        </div>
      </div>

      {trendData.length >= 2 && (
        <div className="bg-white border border-slate-200 rounded-md p-5 mb-6">
          <h3 className="font-display font-bold text-slate-900 mb-4">Trends across weeks</h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={trendData} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" vertical={false} />
              <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#64748b" }} />
              <YAxis tick={{ fontSize: 12, fill: "#64748b" }} />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="Leads" stroke="#002FA7" strokeWidth={2} />
              <Line type="monotone" dataKey="Applications" stroke="#F59E0B" strokeWidth={2} />
              <Line type="monotone" dataKey="CPA" stroke="#EF4444" strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="bg-white border border-slate-200 rounded-md">
        {loading ? (
          <div className="p-10 text-center text-slate-400">Loading…</div>
        ) : reports.length === 0 ? (
          <div className="p-16 flex flex-col items-center text-center">
            <ClockCounterClockwise size={36} className="text-slate-300 mb-3" />
            <p className="text-slate-500">No reports generated yet.</p>
            <Button className="mt-4 bg-[#002FA7] hover:bg-[#002FA7]/90" onClick={() => nav("/generate")}>Generate one</Button>
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {reports.map((r) => (
              <div key={r.id} data-testid={`history-row-${r.id}`}
                   onClick={() => nav(`/report/${r.id}`)}
                   className="flex items-center justify-between px-5 py-4 hover:bg-slate-50 cursor-pointer transition-colors">
                <div>
                  <p className="font-medium text-slate-800">{r.week_label}</p>
                  <p className="text-xs text-slate-400">{r.week_date} · {r.source} · {r.lead_filename}</p>
                </div>
                <div className="flex items-center gap-6">
                  <StatusBadge status={r.status} />
                  {r.kpis && <span className="text-sm text-slate-500">{fmtInt(r.kpis.total_leads)} leads</span>}
                  {r.kpis && <span className="text-sm text-slate-500 hidden sm:inline">{fmtMoney(r.kpis.blended_cpa)} CPA</span>}
                  <button onClick={(e) => del(r.id, e)} data-testid={`delete-${r.id}`}
                          className="text-slate-300 hover:text-red-500 transition-colors"><Trash size={18} /></button>
                  <ArrowRight size={16} className="text-slate-300" />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
