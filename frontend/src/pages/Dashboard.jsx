import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { KpiCards } from "@/components/KpiCards";
import { fmtInt, fmtMoney } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { ArrowRight, Sparkle, UploadSimple, TrendUp, ChartLineUp, ArrowsDownUp } from "@phosphor-icons/react";
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, LineChart, Line, Legend,
} from "recharts";

export default function Dashboard() {
  const nav = useNavigate();
  const [reports, setReports] = useState([]);
  const [latest, setLatest] = useState(null);
  const [trends, setTrends] = useState([]);
  const [loading, setLoading] = useState(true);
  const [sampling, setSampling] = useState(false);

  const load = async () => {
    setLoading(true);
    const list = await api.listReports();
    setReports(list);
    const ready = list.find((r) => r.status === "ready");
    if (ready) setLatest(await api.getReport(ready.id));
    setTrends(await api.trends());
    setLoading(false);
  };
  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const runSample = async () => {
    setSampling(true);
    try {
      const { id } = await api.createSample();
      toast.success("Generating sample report…");
      nav(`/report/${id}`);
    } catch { toast.error("Failed to create sample"); }
    setSampling(false);
  };

  if (loading) return <PageWrap><Skeleton /></PageWrap>;

  if (!latest) {
    return (
      <PageWrap>
        <div className="border-2 border-dashed border-slate-300 rounded-lg bg-white p-16 flex flex-col items-center text-center"
             data-testid="empty-state">
          <div className="h-14 w-14 rounded-lg bg-[#002FA7]/10 flex items-center justify-center mb-5">
            <TrendUp size={28} weight="bold" color="#002FA7" />
          </div>
          <h2 className="font-display text-2xl font-bold text-slate-900 mb-2">No reports yet</h2>
          <p className="text-slate-500 max-w-md mb-6">
            Upload your weekly Lead & Application dumps to auto-generate the program-wise report,
            or try it instantly with sample data.
          </p>
          <div className="flex gap-3">
            <Button data-testid="empty-generate-btn" onClick={() => nav("/generate")} className="bg-[#002FA7] hover:bg-[#002FA7]/90 gap-2">
              <UploadSimple size={18} weight="bold" /> Upload files
            </Button>
            <Button data-testid="empty-sample-btn" variant="outline" onClick={runSample} disabled={sampling} className="gap-2">
              <Sparkle size={18} weight="bold" /> Load sample report
            </Button>
          </div>
        </div>
      </PageWrap>
    );
  }

  const programBar = latest.result.programs.map((p) => ({
    program: p,
    Leads: latest.kpis.per_program[p],
    Verified: latest.result.summary.find((s) => s.label === "Verified Leads")?.values[p] || 0,
  }));
  const trendData = trends.map((t) => ({
    name: t.week_label?.slice(0, 16) || t.week_date,
    Leads: t.kpis?.total_leads || 0,
    Applications: t.kpis?.total_applications || 0,
    CPA: t.kpis?.blended_cpa || 0,
  }));

  return (
    <PageWrap>
      <div className="flex items-center justify-between mb-6">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-slate-400 mb-1">Latest report</p>
          <h2 className="font-display text-xl font-bold text-slate-900">{latest.week_label}</h2>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button data-testid="dash-compare-btn" variant="outline" onClick={() => nav("/compare")} className="gap-2">
            <ArrowsDownUp size={16} weight="bold" /> Compare weeks
          </Button>
          <Button data-testid="dash-tilldate-btn" variant="outline" onClick={() => nav("/cumulative")} className="gap-2">
            <ChartLineUp size={16} weight="bold" /> Report till date
          </Button>
          <Button data-testid="view-latest-btn" onClick={() => nav(`/report/${latest.id}`)}
                  className="bg-[#002FA7] hover:bg-[#002FA7]/90 gap-2">
            Open full report <ArrowRight size={16} weight="bold" />
          </Button>
        </div>
      </div>

      <KpiCards kpis={latest.kpis} />

      <div className="grid lg:grid-cols-2 gap-6 mt-6">
        <ChartCard title="Leads by Program">
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={programBar} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" vertical={false} />
              <XAxis dataKey="program" tick={{ fontSize: 12, fill: "#64748b" }} />
              <YAxis tick={{ fontSize: 12, fill: "#64748b" }} />
              <Tooltip />
              <Legend />
              <Bar dataKey="Leads" fill="#002FA7" radius={[4, 4, 0, 0]} />
              <Bar dataKey="Verified" fill="#10B981" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Week-over-Week Trend">
          {trendData.length < 2 ? (
            <EmptyChart label="Generate more weekly reports to see trends" />
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={trendData} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" vertical={false} />
                <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#64748b" }} />
                <YAxis tick={{ fontSize: 12, fill: "#64748b" }} />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="Leads" stroke="#002FA7" strokeWidth={2} dot={{ r: 3 }} />
                <Line type="monotone" dataKey="Applications" stroke="#F59E0B" strokeWidth={2} dot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          )}
        </ChartCard>
      </div>

      <div className="mt-6 bg-white border border-slate-200 rounded-md">
        <div className="px-5 py-3 border-b border-slate-200 flex items-center justify-between">
          <h3 className="font-display font-bold text-slate-900">Recent reports</h3>
          <Button size="sm" variant="ghost" onClick={() => nav("/history")}>View all</Button>
        </div>
        <div className="divide-y divide-slate-100">
          {reports.slice(0, 5).map((r) => (
            <button key={r.id} data-testid={`recent-${r.id}`} onClick={() => nav(`/report/${r.id}`)}
                    className="w-full flex items-center justify-between px-5 py-3 hover:bg-slate-50 transition-colors text-left">
              <div>
                <p className="font-medium text-slate-800 text-sm">{r.week_label}</p>
                <p className="text-xs text-slate-400">{r.week_date} · {r.source}</p>
              </div>
              <div className="flex items-center gap-6 text-sm">
                <StatusBadge status={r.status} />
                {r.kpis && <span className="text-slate-500">{fmtInt(r.kpis.total_leads)} leads</span>}
                {r.kpis && <span className="text-slate-500">{fmtMoney(r.kpis.amount_spent)}</span>}
              </div>
            </button>
          ))}
        </div>
      </div>
    </PageWrap>
  );
}

export const PageWrap = ({ children }) => (
  <div className="p-8 max-w-7xl mx-auto">
    <div className="mb-6">
      <h1 className="font-display text-3xl font-extrabold tracking-tight text-slate-900">Dashboard</h1>
      <p className="text-slate-500 mt-1">Weekly lead & application performance overview.</p>
    </div>
    {children}
  </div>
);

const ChartCard = ({ title, children }) => (
  <div className="bg-white border border-slate-200 rounded-md p-5">
    <h3 className="font-display font-bold text-slate-900 mb-4">{title}</h3>
    {children}
  </div>
);
const EmptyChart = ({ label }) => (
  <div className="h-[280px] flex items-center justify-center text-slate-400 text-sm border border-dashed border-slate-200 rounded-md">{label}</div>
);
export const StatusBadge = ({ status }) => {
  const map = {
    ready: "bg-emerald-50 text-emerald-700 border-emerald-200",
    processing: "bg-amber-50 text-amber-700 border-amber-200",
    error: "bg-red-50 text-red-700 border-red-200",
  };
  return <span className={`text-xs px-2 py-0.5 rounded-full border ${map[status] || ""}`}>{status}</span>;
};
const Skeleton = () => (
  <div className="animate-pulse space-y-4">
    <div className="grid grid-cols-4 gap-4">{[...Array(4)].map((_, i) => <div key={`sk-${i}`} className="h-28 bg-slate-100 rounded-md" />)}</div>
    <div className="h-72 bg-slate-100 rounded-md" />
  </div>
);
