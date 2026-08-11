import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { ReportTable } from "@/components/ReportTable";
import { KpiCards } from "@/components/KpiCards";
import { StatusBadge } from "@/pages/Dashboard";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { DownloadSimple, ArrowLeft, Warning, FloppyDisk, Info } from "@phosphor-icons/react";

export default function ReportView() {
  const { id } = useParams();
  const nav = useNavigate();
  const [doc, setDoc] = useState(null);
  const [amount, setAmount] = useState({});
  const [addAttr, setAddAttr] = useState({});
  const [saving, setSaving] = useState(false);

  const fetchDoc = useCallback(async () => {
    const d = await api.getReport(id);
    setDoc(d);
    if (d.status === "ready") {
      setAmount(d.amount_spent || {});
      setAddAttr(d.additional_attributed || {});
    }
    return d;
  }, [id]);

  useEffect(() => {
    let timer;
    const poll = async () => {
      const d = await fetchDoc();
      if (d.status === "processing") timer = setTimeout(poll, 2000);
    };
    poll();
    return () => clearTimeout(timer);
  }, [fetchDoc]);

  const saveAmounts = async () => {
    setSaving(true);
    try {
      const clean = (o) => Object.fromEntries(Object.entries(o).map(([k, v]) => [k, Number(v) || 0]));
      const d = await api.updateAmounts(id, { amount_spent: clean(amount), additional_attributed: clean(addAttr) });
      setDoc(d);
      toast.success("Amounts updated — CPA recalculated");
    } catch { toast.error("Could not update"); }
    setSaving(false);
  };

  if (!doc) return <div className="p-8"><div className="h-96 bg-slate-100 rounded-md animate-pulse" /></div>;

  if (doc.status === "processing") {
    return (
      <div className="p-8 max-w-2xl mx-auto">
        <div className="bg-white border border-slate-200 rounded-md p-16 text-center">
          <div className="h-12 w-12 rounded-full border-4 border-slate-200 border-t-[#002FA7] animate-spin mx-auto mb-5" />
          <h2 className="font-display text-xl font-bold text-slate-900">Crunching your data…</h2>
          <p className="text-slate-500 mt-2">Parsing the lead dump and computing metrics. Large files may take up to a minute.</p>
        </div>
      </div>
    );
  }

  if (doc.status === "error") {
    return (
      <div className="p-8 max-w-2xl mx-auto">
        <div className="bg-white border border-red-200 rounded-md p-10 text-center">
          <Warning size={40} weight="fill" color="#EF4444" className="mx-auto mb-3" />
          <h2 className="font-display text-xl font-bold text-slate-900">Processing failed</h2>
          <p className="text-slate-500 mt-2 break-words">{doc.error}</p>
          <Button className="mt-5" variant="outline" onClick={() => nav("/generate")}>Try again</Button>
        </div>
      </div>
    );
  }

  const programs = doc.result.programs;
  const dq = doc.result.data_quality;
  const showDqWarn = dq && dq.unclassified_program > dq.total_rows * 0.5;

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <button onClick={() => nav(-1)} className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-[#002FA7] mb-4" data-testid="back-btn">
        <ArrowLeft size={16} weight="bold" /> Back
      </button>

      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="font-display text-3xl font-extrabold tracking-tight text-slate-900">{doc.week_label}</h1>
            <StatusBadge status={doc.status} />
          </div>
          <p className="text-slate-500 mt-1">{doc.week_date} · Source file: {doc.lead_filename}</p>
        </div>
        <a href={api.exportUrl(id)} data-testid="export-btn">
          <Button className="bg-[#002FA7] hover:bg-[#002FA7]/90 gap-2">
            <DownloadSimple size={18} weight="bold" /> Export to Excel
          </Button>
        </a>
      </div>

      {showDqWarn && (
        <div className="mb-5 flex items-start gap-3 bg-amber-50 border border-amber-200 rounded-md px-4 py-3 text-sm text-amber-800" data-testid="dq-warning">
          <Info size={18} weight="fill" className="mt-0.5 shrink-0" />
          <span>
            {dq.unclassified_program.toLocaleString()} of {dq.total_rows.toLocaleString()} leads had no recognisable
            <b> Course</b> value and were excluded from program columns. Your real Monday export should have the Course
            column populated for a complete split.
          </span>
        </div>
      )}

      <KpiCards kpis={doc.kpis} />

      <div className="mt-6 bg-white border border-slate-200 rounded-md p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-display font-bold text-slate-900">Amount Spent & CPA</h3>
          <Button size="sm" onClick={saveAmounts} disabled={saving} className="gap-2 bg-[#002FA7] hover:bg-[#002FA7]/90" data-testid="save-amounts-btn">
            <FloppyDisk size={16} weight="bold" /> {saving ? "Saving…" : "Recalculate"}
          </Button>
        </div>
        <div className="grid sm:grid-cols-3 gap-4">
          {programs.map((p) => (
            <div key={p} className="border border-slate-200 rounded-md p-3">
              <p className="font-semibold text-sm text-slate-700 mb-2">{p}</p>
              <label className="text-xs text-slate-500">Amount spent</label>
              <Input data-testid={`edit-amount-${p}`} type="number" value={amount[p] ?? ""} className="mt-1 mb-2"
                     onChange={(e) => setAmount({ ...amount, [p]: e.target.value })} />
              <label className="text-xs text-slate-500">Additional attributed applications</label>
              <Input data-testid={`edit-addattr-${p}`} type="number" value={addAttr[p] ?? ""} className="mt-1"
                     onChange={(e) => setAddAttr({ ...addAttr, [p]: e.target.value })} />
            </div>
          ))}
        </div>
      </div>

      <h3 className="font-display font-bold text-slate-900 mt-8 mb-3">Program × Lead-Stage Report</h3>
      <ReportTable result={doc.result} />
    </div>
  );
}
