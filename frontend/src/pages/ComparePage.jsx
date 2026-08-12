import { useEffect, useState, useMemo } from "react";
import { api } from "@/lib/api";
import { fmtInt, fmtMoney, fmtPct } from "@/lib/format";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { TrendUp, TrendDown, Minus, ArrowsDownUp } from "@phosphor-icons/react";
import { ResponsiveContainer, BarChart, Bar, XAxis, Tooltip, Cell } from "recharts";

const extract = (res, label, prog, isMatrix) => {
  if (isMatrix) {
    const m = res.matrix.find((x) => x.stage === label);
    if (!m) return null;
    return prog === "Total" ? m.total : m.values[prog];
  }
  const s = res.summary.find((x) => x.label === label);
  if (!s || s.kind === "section") return null;
  if (s.fmt === "pct_only") return prog === "Total" ? s.total_pct : s.pct?.[prog];
  return prog === "Total" ? s.total : s.values?.[prog];
};

export default function ComparePage() {
  const [reports, setReports] = useState([]);
  const [curId, setCurId] = useState("");
  const [prevId, setPrevId] = useState("");
  const [cur, setCur] = useState(null);
  const [prev, setPrev] = useState(null);
  const [prog, setProg] = useState("Total");

  useEffect(() => {
    api.listReports().then((list) => {
      const ready = list.filter((r) => r.status === "ready");
      setReports(ready);
      if (ready[0]) setCurId(ready[0].id);
      if (ready[1]) setPrevId(ready[1].id);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => { if (curId) api.getReport(curId).then(setCur); }, [curId]);
  useEffect(() => { if (prevId) api.getReport(prevId).then(setPrev); }, [prevId]);

  const programs = cur?.result?.programs || ["B.Com", "BBA", "PGDM"];

  const rows = useMemo(() => {
    if (!cur?.result) return [];
    const out = [];
    cur.result.matrix.forEach((m) =>
      out.push({ label: m.stage, fmt: "int", isMatrix: true, group: "Lead Stage" }));
    cur.result.summary.forEach((s) => {
      if (s.kind === "section") return;
      out.push({ label: s.label, fmt: s.fmt, isMatrix: false, group: "Metrics" });
    });
    return out;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cur]);

  const fmtVal = (v, fmt) =>
    v === null || v === undefined ? "-" : fmt === "money" ? fmtMoney(v) : fmt === "pct_only" ? fmtPct(v) : fmtInt(v);

  const delta = (c, p, fmt) => {
    if (c === null || c === undefined || p === null || p === undefined) return { txt: "-", dir: 0 };
    const diff = c - p;
    const dir = diff > 0 ? 1 : diff < 0 ? -1 : 0;
    let txt;
    if (fmt === "money") txt = (diff >= 0 ? "+" : "-") + fmtMoney(Math.abs(diff)).replace("₹", "₹");
    else if (fmt === "pct_only") txt = (diff >= 0 ? "+" : "") + Math.round(diff) + " pp";
    else txt = (diff >= 0 ? "+" : "") + fmtInt(diff);
    return { txt, dir };
  };

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex items-center gap-2 mb-1">
        <ArrowsDownUp size={26} weight="bold" color="#002FA7" />
        <h1 className="font-display text-3xl font-extrabold tracking-tight text-slate-900">Week Compare</h1>
      </div>
      <p className="text-slate-500 mb-6">Compare any two weekly reports side-by-side with up/down movement on every metric.</p>

      <div className="grid sm:grid-cols-3 gap-4 mb-6 bg-white border border-slate-200 rounded-md p-5">
        <div>
          <label className="text-xs uppercase tracking-wide text-slate-500">This week</label>
          <Select value={curId} onValueChange={setCurId}>
            <SelectTrigger data-testid="compare-cur-select" className="mt-1"><SelectValue placeholder="Select" /></SelectTrigger>
            <SelectContent>{reports.map((r) => <SelectItem key={r.id} value={r.id}>{r.week_label}</SelectItem>)}</SelectContent>
          </Select>
        </div>
        <div>
          <label className="text-xs uppercase tracking-wide text-slate-500">Compared with</label>
          <Select value={prevId} onValueChange={setPrevId}>
            <SelectTrigger data-testid="compare-prev-select" className="mt-1"><SelectValue placeholder="Select" /></SelectTrigger>
            <SelectContent>{reports.map((r) => <SelectItem key={r.id} value={r.id}>{r.week_label}</SelectItem>)}</SelectContent>
          </Select>
        </div>
        <div>
          <label className="text-xs uppercase tracking-wide text-slate-500">Program</label>
          <Select value={prog} onValueChange={setProg}>
            <SelectTrigger data-testid="compare-prog-select" className="mt-1"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="Total">All (Total)</SelectItem>
              {programs.map((p) => <SelectItem key={p} value={p}>{p}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
      </div>

      {cur && prev && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6" data-testid="compare-charts">
          {["Total Leads", "Verified Leads", "Total No. of Applications", "Relevant Leads"].map((label) => {
            const c = extract(cur.result, label, prog, false) || 0;
            const p = extract(prev.result, label, prog, false) || 0;
            const up = c >= p;
            const data = [{ name: "Prev", v: p }, { name: "This", v: c }];
            return (
              <div key={label} className="bg-white border border-slate-200 rounded-md p-4" data-testid={`compare-chart-${label}`}>
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1 truncate">{label}</p>
                <p className="font-display text-xl font-extrabold text-slate-900">{fmtInt(c)}</p>
                <ResponsiveContainer width="100%" height={64}>
                  <BarChart data={data} margin={{ top: 6, right: 0, left: 0, bottom: 0 }}>
                    <XAxis dataKey="name" tick={{ fontSize: 10, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
                    <Tooltip cursor={{ fill: "#f1f5f9" }} formatter={(v) => fmtInt(v)} />
                    <Bar dataKey="v" radius={[3, 3, 0, 0]}>
                      <Cell fill="#cbd5e1" />
                      <Cell fill={up ? "#10B981" : "#EF4444"} />
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            );
          })}
        </div>
      )}

      {!cur || !prev ? (
        <div className="bg-white border border-dashed border-slate-300 rounded-md p-12 text-center text-slate-500">
          Select two ready reports to compare. You need at least two generated reports.
        </div>
      ) : (
        <div className="overflow-x-auto thin-scroll border border-slate-200 rounded-md bg-white" data-testid="compare-table">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="bg-slate-50">
                <th className="text-left px-4 py-2.5 border-b border-slate-200 font-bold">Metric</th>
                <th className="text-right px-4 py-2.5 border-b border-slate-200 font-bold">{cur.week_label}</th>
                <th className="text-right px-4 py-2.5 border-b border-slate-200 font-bold text-slate-500">{prev.week_label}</th>
                <th className="text-right px-4 py-2.5 border-b border-slate-200 font-bold">Change</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const c = extract(cur.result, r.label, prog, r.isMatrix);
                const p = extract(prev.result, r.label, prog, r.isMatrix);
                const d = delta(c, p, r.fmt);
                const Icon = d.dir > 0 ? TrendUp : d.dir < 0 ? TrendDown : Minus;
                const color = d.dir > 0 ? "#10B981" : d.dir < 0 ? "#EF4444" : "#94A3B8";
                return (
                  <tr key={r.label} className="hover:bg-slate-50 border-b border-slate-100" data-testid={`compare-row-${r.label}`}>
                    <td className="px-4 py-2 font-medium text-slate-800">{r.label}</td>
                    <td className="px-4 py-2 text-right font-semibold">{fmtVal(c, r.fmt)}</td>
                    <td className="px-4 py-2 text-right text-slate-500">{fmtVal(p, r.fmt)}</td>
                    <td className="px-4 py-2 text-right">
                      <span className="inline-flex items-center gap-1 font-medium" style={{ color }}>
                        <Icon size={15} weight="bold" /> {d.txt}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
