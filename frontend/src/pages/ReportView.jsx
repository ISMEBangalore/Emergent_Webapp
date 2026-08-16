import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { ReportTabs } from "@/components/ReportTabs";
import { KpiCards } from "@/components/KpiCards";
import { StatusBadge } from "@/pages/Dashboard";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { DownloadSimple, ArrowLeft, Warning, FloppyDisk, Info, ArrowsClockwise, CalendarBlank, BookmarkSimple, Trash } from "@phosphor-icons/react";

export default function ReportView() {
  const { id } = useParams();
  const nav = useNavigate();
  const [doc, setDoc] = useState(null);
  const [amount, setAmount] = useState({});
  const [addAttr, setAddAttr] = useState({});
  const [saving, setSaving] = useState(false);
  const [pubAmount, setPubAmount] = useState({});
  const [pubCpa, setPubCpa] = useState({});
  const [pubSaving, setPubSaving] = useState(false);
  const [rStart, setRStart] = useState("");
  const [rEnd, setREnd] = useState("");
  const [regen, setRegen] = useState(false);
  const [views, setViews] = useState([]);
  const [viewName, setViewName] = useState("");
  const [topPublishers, setTopPublishers] = useState("0");

  const fetchDoc = useCallback(async () => {
    const d = await api.getReport(id);
    setDoc(d);
    if (d.status === "ready") {
      setAmount(d.amount_spent || {});
      setAddAttr(d.additional_attributed || {});
      setPubAmount(d.publisher_amount_spent || {});
      setPubCpa(d.publisher_cpa || {});
      setRStart(d.date_range?.start || "");
      setREnd(d.date_range?.end || "");
    }
    return d;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  useEffect(() => {
    let timer;
    const poll = async () => {
      const d = await fetchDoc();
      if (d.status === "processing") timer = setTimeout(poll, 2000);
    };
    poll();
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
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

  const savePublisherAmounts = async () => {
    setPubSaving(true);
    try {
      const clean = (o) => Object.fromEntries(Object.entries(o).map(([k, v]) => [k, Number(v) || 0]));
      const d = await api.updatePublisherAmounts(id, { amount_spent: clean(pubAmount), cpa: clean(pubCpa) });
      setDoc(d);
      toast.success("Publisher spend updated");
    } catch { toast.error("Could not update publisher spend"); }
    setPubSaving(false);
  };

  const loadViews = useCallback(() => { api.listViews().then(setViews).catch(() => {}); }, []);
  useEffect(() => { loadViews(); }, [loadViews]);

  const pollUntilReady = () => {
    const poll = async () => {
      const d = await fetchDoc();
      if (d.status === "processing") setTimeout(poll, 2000);
      else setRegen(false);
    };
    poll();
  };

  const regenerate = async (start = rStart, end = rEnd) => {
    setRegen(true);
    try {
      await api.regenerateReport(id, { start, end });
      toast.success("Regenerating with your current settings…");
      pollUntilReady();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not regenerate");
      setRegen(false);
    }
  };

  const saveView = async () => {
    const name = viewName.trim();
    if (!name) { toast.error("Name your view first"); return; }
    try {
      await api.createView({ name, programs: doc.result.programs, start: rStart || null, end: rEnd || null });
      setViewName("");
      loadViews();
      toast.success(`Saved view "${name}"`);
    } catch { toast.error("Could not save view"); }
  };

  const applyView = async (v) => {
    setRegen(true);
    try {
      await api.updateSettings({ programs: v.programs });
      setRStart(v.start || ""); setREnd(v.end || "");
      await api.regenerateReport(id, { start: v.start || "", end: v.end || "" });
      toast.success(`Applied view "${v.name}"`);
      pollUntilReady();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not apply view");
      setRegen(false);
    }
  };

  const removeView = async (v) => {
    try { await api.deleteView(v.id); loadViews(); toast.success("View deleted"); }
    catch { toast.error("Could not delete view"); }
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
            data-testid="export-btn"
            className="bg-[#002FA7] hover:bg-[#002FA7]/90 gap-2"
            onClick={() => api.downloadReport(id, { top_publishers: Number(topPublishers) })
              .catch(() => toast.error("Could not download the export."))}
          >
            <DownloadSimple size={18} weight="bold" /> Export to Excel
          </Button>
        </div>
      </div>

      {doc.lead_file_id && (
        <div className="mb-5 bg-white border border-slate-200 rounded-md p-4" data-testid="regen-panel">
          <div className="flex items-center gap-1.5 mb-1">
            <CalendarBlank size={16} weight="bold" color="#002FA7" />
            <span className="text-sm font-semibold text-slate-700">Date range — User Registration Date</span>
          </div>
          {dq?.data_date_min ? (
            <p className="text-xs text-slate-400" data-testid="date-coverage">
              This upload covers <b>{dq.data_date_min}</b> → <b>{dq.data_date_max}</b>. Leave dates empty for the complete file.
            </p>
          ) : (
            <p className="text-xs text-slate-400">No date column detected — the report uses the complete uploaded file.</p>
          )}
          <div className="flex flex-wrap items-end gap-3 mt-3">
            <div>
              <label className="text-xs uppercase tracking-wide text-slate-500">From</label>
              <Input data-testid="regen-start" type="date" value={rStart} onChange={(e) => setRStart(e.target.value)} className="mt-1 w-44" />
            </div>
            <div>
              <label className="text-xs uppercase tracking-wide text-slate-500">To</label>
              <Input data-testid="regen-end" type="date" value={rEnd} onChange={(e) => setREnd(e.target.value)} className="mt-1 w-44" />
            </div>
            <Button data-testid="regen-btn" onClick={() => regenerate()} disabled={regen} className="bg-[#002FA7] hover:bg-[#002FA7]/90 gap-2">
              <ArrowsClockwise size={16} weight="bold" /> {regen ? "Working…" : "Apply & Regenerate"}
            </Button>
            {(rStart || rEnd) && (
              <button data-testid="regen-clear" onClick={() => { setRStart(""); setREnd(""); }} className="text-xs text-[#002FA7] underline">Clear (full data)</button>
            )}
          </div>
          <p className="text-xs text-slate-400 mt-2">Regenerate re-runs on the saved upload using your current Settings (selected programs, publishers, rules) — no re-upload needed.</p>

          <div className="border-t border-slate-100 mt-4 pt-4">
            <div className="flex items-center gap-1.5 mb-2">
              <BookmarkSimple size={16} weight="bold" color="#002FA7" />
              <span className="text-sm font-semibold text-slate-700">Saved views</span>
            </div>
            {views.length > 0 ? (
              <div className="flex flex-wrap gap-2 mb-3" data-testid="saved-views">
                {views.map((v) => (
                  <div key={v.id} data-testid={`view-chip-${v.id}`}
                       className="group flex items-center gap-1.5 pl-3 pr-1.5 py-1 rounded-full border border-slate-200 text-sm text-slate-700 hover:border-[#002FA7]">
                    <button data-testid={`view-apply-${v.id}`} onClick={() => applyView(v)} disabled={regen} className="hover:text-[#002FA7]">
                      {v.name}
                      <span className="opacity-50 ml-1">
                        · {v.programs?.length || 0} prog{(v.start || v.end) ? " · dated" : ""}
                      </span>
                    </button>
                    <button data-testid={`view-delete-${v.id}`} onClick={() => removeView(v)} className="text-slate-300 hover:text-red-500">
                      <Trash size={13} weight="bold" />
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-400 mb-3">No saved views yet. Save the current program selection + date range as a one-click view.</p>
            )}
            <div className="flex flex-wrap items-center gap-2">
              <Input data-testid="view-name-input" value={viewName} onChange={(e) => setViewName(e.target.value)}
                     placeholder="e.g. PGDM · Oct–Dec" className="w-56 h-9" />
              <Button data-testid="view-save-btn" onClick={saveView} variant="outline" size="sm" className="gap-1.5">
                <BookmarkSimple size={15} weight="bold" /> Save current view
              </Button>
            </div>
          </div>
        </div>
      )}

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

      <ReportTabs result={doc.result} publisherPanel={
        doc.result.publisher_report && doc.result.publisher_report.programs?.length ? (
          <div className="mb-4 bg-white border border-slate-200 rounded-md p-5" data-testid="publisher-spend-panel">
            <div className="flex items-center justify-between mb-1">
              <h3 className="font-display font-bold text-slate-900">Publisher Ad Spend & CPA</h3>
              <Button size="sm" onClick={savePublisherAmounts} disabled={pubSaving}
                      className="gap-2 bg-[#002FA7] hover:bg-[#002FA7]/90" data-testid="save-publisher-btn">
                <FloppyDisk size={16} weight="bold" /> {pubSaving ? "Saving…" : "Recalculate"}
              </Button>
            </div>
            <p className="text-xs text-slate-400 mb-4">
              Enter Amount Spent directly, OR a known CPA — total cost = CPA × applied leads. Cost/Application uses applied leads as the application proxy.
            </p>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
              {doc.result.publisher_report.programs.map((pub) => (
                <div key={pub} className="border border-slate-200 rounded-md p-3">
                  <p className="font-semibold text-sm text-slate-700 mb-2 truncate" title={pub}>{pub}</p>
                  <label className="text-xs text-slate-500">Amount spent</label>
                  <Input data-testid={`pub-amount-${pub}`} type="number" value={pubAmount[pub] ?? ""} className="mt-1 mb-2"
                         onChange={(e) => setPubAmount({ ...pubAmount, [pub]: e.target.value })} />
                  <label className="text-xs text-slate-500">Known CPA (₹)</label>
                  <Input data-testid={`pub-cpa-${pub}`} type="number" value={pubCpa[pub] ?? ""} className="mt-1"
                         onChange={(e) => setPubCpa({ ...pubCpa, [pub]: e.target.value })} />
                </div>
              ))}
            </div>
          </div>
        ) : null
      } />
    </div>
  );
}
