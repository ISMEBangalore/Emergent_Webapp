import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import {
  ArrowLeft, CalendarBlank, Lightbulb, Warning, WarningCircle, Sparkle, Funnel,
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

const AlertBanner = ({ alert }) => {
  const critical = alert.severity === "critical";
  return (
    <div
      className={`flex items-start gap-3 rounded-md px-4 py-3 text-sm border ${
        critical ? "bg-red-50 border-red-200 text-red-800" : "bg-amber-50 border-amber-200 text-amber-800"
      }`}
      data-testid={`alert-${alert.severity}`}
    >
      {critical ? <WarningCircle size={18} weight="fill" className="mt-0.5 shrink-0" />
                : <Warning size={18} weight="fill" className="mt-0.5 shrink-0" />}
      <div>
        <p className="font-semibold">{alert.title}</p>
        <p className="mt-0.5">{alert.message}</p>
      </div>
    </div>
  );
};

const Bar = ({ pct, color = "#002FA7" }) => (
  <div className="h-1.5 w-full bg-slate-100 rounded-full overflow-hidden">
    <div className="h-full rounded-full" style={{ width: `${Math.min(100, Math.max(0, pct || 0))}%`, background: color }} />
  </div>
);

const BreakdownList = ({ title, rows, total }) => (
  <div className="bg-white border border-slate-200 rounded-md p-4" data-testid={`breakdown-${title}`}>
    <h4 className="text-sm font-bold text-slate-800 mb-3">{title}</h4>
    {!rows?.length ? (
      <p className="text-xs text-slate-400">No data</p>
    ) : (
      <div className="space-y-2.5">
        {rows.map((r) => {
          const pct = total ? (r.count / total) * 100 : 0;
          return (
            <div key={r.name}>
              <div className="flex items-center justify-between text-xs mb-1">
                <span className="text-slate-700 font-medium truncate mr-2" title={r.name}>{r.name}</span>
                <span className="text-slate-400 shrink-0">{fmtInt(r.count)} · {fmtPct1(Math.round(pct * 10) / 10)}</span>
              </div>
              <Bar pct={pct} />
            </div>
          );
        })}
      </div>
    )}
  </div>
);

const cell = "border border-slate-200 px-3 py-1.5 text-sm whitespace-nowrap";

export default function ApplicationInsight() {
  const nav = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [prog, setProg] = useState("All");
  const [aiLoading, setAiLoading] = useState(false);
  const [aiText, setAiText] = useState("");

  const load = useCallback(async (s, e) => {
    setLoading(true);
    try {
      const params = {};
      if (s) params.start = s;
      if (e) params.end = e;
      const d = await api.getInsights(params);
      setData(d);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not load insights. Please try again.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load("", ""); }, [load]);

  const apply = () => load(start, end);
  const preset = (s, e) => { setStart(s); setEnd(e); load(s, e); };

  const askAi = async () => {
    setAiLoading(true);
    setAiText("");
    try {
      const params = {};
      if (start) params.start = start;
      if (end) params.end = end;
      const res = await api.getAiInsight(params);
      setAiText(res.insight);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "AI Insight failed — check that it's configured.");
    } finally {
      setAiLoading(false);
    }
  };

  const summary = data?.summary?.[prog];
  const empty = !summary || summary.applications === 0;
  const progOptions = ["All", ...(data?.programs || [])];

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <button onClick={() => nav(-1)} className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-[#002FA7] mb-4" data-testid="back-btn">
        <ArrowLeft size={16} weight="bold" /> Back
      </button>

      <div className="flex items-center gap-2 mb-1">
        <Lightbulb size={26} weight="bold" color="#002FA7" />
        <h1 className="font-display text-3xl font-extrabold tracking-tight text-slate-900" data-testid="insight-title">
          Application Insight
        </h1>
      </div>
      <p className="text-slate-500 mt-1 mb-5">
        Payment-approved applications only, aggregated across every stored report — including the admission-fee
        conversion, which is usually paid weeks after the application fee, so it's tracked here rather than in
        any single week's report.
      </p>

      <div className="bg-white border border-slate-200 rounded-md p-5 mb-6">
        <div className="flex items-center gap-2 mb-3">
          <CalendarBlank size={18} weight="bold" color="#002FA7" />
          <h3 className="font-display font-bold text-slate-900">Date range</h3>
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <Label className="text-xs uppercase tracking-wide text-slate-500">From</Label>
            <Input data-testid="insight-range-start" type="date" value={start} onChange={(e) => setStart(e.target.value)} className="mt-1 w-44" />
          </div>
          <div>
            <Label className="text-xs uppercase tracking-wide text-slate-500">To</Label>
            <Input data-testid="insight-range-end" type="date" value={end} onChange={(e) => setEnd(e.target.value)} className="mt-1 w-44" />
          </div>
          <Button data-testid="insight-range-apply" onClick={apply} className="bg-[#002FA7] hover:bg-[#002FA7]/90">Apply</Button>
        </div>
        <div className="flex flex-wrap gap-2 mt-4">
          <Preset label="All time" onClick={() => preset("", "")} testid="insight-preset-all" />
          <Preset label="This year" onClick={() => preset(yearStart(), today())} testid="insight-preset-year" />
          <Preset label="Last 4 weeks" onClick={() => preset(isoDaysAgo(28), today())} testid="insight-preset-4w" />
          <Preset label="Last 12 weeks" onClick={() => preset(isoDaysAgo(84), today())} testid="insight-preset-12w" />
        </div>
      </div>

      {loading ? (
        <div className="h-72 bg-slate-100 rounded-md animate-pulse" />
      ) : empty ? (
        <div className="bg-white border border-dashed border-slate-300 rounded-md p-12 text-center text-slate-500" data-testid="insight-empty">
          No payment-approved applications in this range yet.
        </div>
      ) : (
        <>
          {data.alerts?.length > 0 && (
            <div className="space-y-2 mb-6" data-testid="alerts-panel">
              {data.alerts.map((a, i) => <AlertBanner key={i} alert={a} />)}
            </div>
          )}

          <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
            <Chips options={progOptions} value={prog} onChange={setProg} testidPrefix="insight-prog" />
            <Button
              data-testid="ai-insight-btn"
              onClick={askAi}
              disabled={aiLoading}
              className="bg-gradient-to-r from-[#002FA7] to-[#1c5cab] hover:opacity-90 gap-2"
            >
              <Sparkle size={18} weight="fill" /> {aiLoading ? "Thinking…" : "AI Insight"}
            </Button>
          </div>

          {aiText && (
            <div className="bg-white border border-[#002FA7]/30 rounded-md p-5 mb-6 whitespace-pre-wrap text-sm text-slate-700 leading-relaxed"
                 data-testid="ai-insight-panel">
              <div className="flex items-center gap-2 mb-3">
                <Sparkle size={18} weight="fill" color="#002FA7" />
                <h3 className="font-display font-bold text-slate-900">AI Insight</h3>
              </div>
              {aiText}
            </div>
          )}

          <div className="grid sm:grid-cols-3 gap-4 mb-6">
            <div className="bg-white border border-slate-200 rounded-md p-5" data-testid="kpi-applications">
              <p className="text-xs uppercase tracking-wide text-slate-500 mb-1">Payment-Approved Applications</p>
              <p className="font-display text-3xl font-extrabold text-slate-900">{fmtInt(summary.applications)}</p>
            </div>
            <div className="bg-white border border-slate-200 rounded-md p-5" data-testid="kpi-admitted">
              <p className="text-xs uppercase tracking-wide text-slate-500 mb-1">Admission Fee Paid</p>
              <p className="font-display text-3xl font-extrabold text-slate-900">{fmtInt(summary.admission_paid)}</p>
            </div>
            <div className="bg-white border border-slate-200 rounded-md p-5" data-testid="kpi-conversion">
              <div className="flex items-center gap-1.5 mb-1">
                <Funnel size={14} color="#64748B" />
                <p className="text-xs uppercase tracking-wide text-slate-500">Admission Conversion</p>
              </div>
              <p className="font-display text-3xl font-extrabold text-[#002FA7]">{fmtPct1(summary.admission_conversion_pct)}</p>
            </div>
          </div>

          <div className="bg-white border border-slate-200 rounded-md p-5 mb-6">
            <h3 className="font-display font-bold text-slate-900 mb-1">Publisher quality</h3>
            <p className="text-xs text-slate-400 mb-4">Applications submitted vs. payment-approved rate — not just volume.</p>
            <div className="overflow-x-auto thin-scroll">
              <table className="border-collapse min-w-full" data-testid="publisher-quality-table">
                <thead>
                  <tr>
                    <th className={`${cell} bg-[#9DC3E6] text-left font-bold`}>Publisher</th>
                    <th className={`${cell} bg-[#C6EFCE] text-right font-bold`}>Submitted</th>
                    <th className={`${cell} bg-[#C6EFCE] text-right font-bold`}>Approved</th>
                    <th className={`${cell} bg-[#C6EFCE] text-right font-bold`}>Approval %</th>
                  </tr>
                </thead>
                <tbody>
                  {summary.publisher_quality.map((r) => (
                    <tr key={r.name} className="hover:bg-slate-50">
                      <td className={`${cell} font-medium text-slate-800`}>{r.name}</td>
                      <td className={`${cell} text-right`}>{fmtInt(r.total)}</td>
                      <td className={`${cell} text-right`}>{fmtInt(r.approved)}</td>
                      <td className={`${cell} text-right ${r.approval_pct != null && r.approval_pct < 25 ? "text-red-600 font-semibold" : "text-slate-600"}`}>
                        {fmtPct1(r.approval_pct)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
            <BreakdownList title="Gender" rows={summary.gender} total={summary.applications} />
            <BreakdownList title="Category" rows={summary.category} total={summary.applications} />
            <BreakdownList title="Hostel requirement" rows={summary.hostel} total={summary.applications} />
            <BreakdownList title="Finance mode" rows={summary.finance} total={summary.applications} />
            <BreakdownList title="Father's occupation" rows={summary.father_occupation} total={summary.applications} />
            <BreakdownList title="Mother's occupation" rows={summary.mother_occupation} total={summary.applications} />
            <BreakdownList title="12th board" rows={summary.board_12th} total={summary.applications} />
            <BreakdownList title="Self-reported source" rows={summary.self_reported_source} total={summary.applications} />
            <BreakdownList title="Tracked publisher" rows={summary.tracked_publisher} total={summary.applications} />
          </div>

          <div className="grid sm:grid-cols-3 gap-4">
            <div className="bg-white border border-slate-200 rounded-md p-4">
              <p className="text-xs uppercase tracking-wide text-slate-500 mb-1">12th % average</p>
              <p className="font-display text-xl font-bold text-slate-900">
                {summary.pct_12th_avg ?? "-"}{summary.pct_12th_avg != null && "%"}
              </p>
              <p className="text-xs text-slate-400 mt-0.5">n = {fmtInt(summary.pct_12th_sample_size)}</p>
            </div>
            <div className="bg-white border border-slate-200 rounded-md p-4">
              <p className="text-xs uppercase tracking-wide text-slate-500 mb-1">Discount coupon usage</p>
              <p className="font-display text-xl font-bold text-slate-900">{fmtPct1(summary.discount_usage_pct)}</p>
              <p className="text-xs text-slate-400 mt-0.5">{fmtInt(summary.discount_used)} of {fmtInt(summary.discount_total)}</p>
            </div>
            <div className="bg-white border border-slate-200 rounded-md p-4">
              <p className="text-xs uppercase tracking-wide text-slate-500 mb-1">Reports included</p>
              <p className="font-display text-xl font-bold text-slate-900">{fmtInt(data.reports_included)}</p>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
