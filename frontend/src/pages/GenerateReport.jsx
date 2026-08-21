import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { toast } from "sonner";
import { UploadSimple, FileXls, X, Sparkle, CurrencyInr } from "@phosphor-icons/react";

export default function GenerateReport() {
  const nav = useNavigate();
  const [settings, setSettings] = useState(null);
  const [weekLabel, setWeekLabel] = useState("");
  const [weekDate, setWeekDate] = useState(new Date().toISOString().slice(0, 10));
  const [leadFile, setLeadFile] = useState(null);
  const [appFiles, setAppFiles] = useState([]);
  const [joinedFile, setJoinedFile] = useState(null);
  const [showJoined, setShowJoined] = useState(false);
  const [amount, setAmount] = useState({});
  const [addAttr, setAddAttr] = useState({});
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.getSettings().then((s) => {
      setSettings(s);
      setWeekLabel(`Week of ${new Date().toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" })}`);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const programs = settings?.programs || ["B.Com", "BBA", "PGDM"];

  const submit = async () => {
    if (!leadFile) { toast.error("Please upload the Lead dump file"); return; }
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("week_label", weekLabel);
      fd.append("week_date", weekDate);
      fd.append("amount_spent", JSON.stringify(amount));
      fd.append("additional_attributed", JSON.stringify(addAttr));
      fd.append("lead_file", leadFile);
      appFiles.forEach((f) => fd.append("application_files", f));
      if (joinedFile) fd.append("joined_file", joinedFile);
      const { id } = await api.createReport(fd);
      toast.success("Uploaded — generating report…");
      nav(`/report/${id}`);
    } catch (e) {
      toast.error("Upload failed. Check the file and try again.");
      setBusy(false);
    }
  };

  const runSample = async () => {
    setBusy(true);
    try {
      const { id } = await api.createSample();
      toast.success("Generating sample report…");
      nav(`/report/${id}`);
    } catch { toast.error("Failed"); setBusy(false); }
  };

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="font-display text-3xl font-extrabold tracking-tight text-slate-900">Generate Report</h1>
          <p className="text-slate-500 mt-1">Upload this Monday's CRM dumps to auto-build the weekly report.</p>
        </div>
        <Button variant="outline" onClick={runSample} disabled={busy} data-testid="sample-btn" className="gap-2">
          <Sparkle size={16} weight="bold" /> Use sample data
        </Button>
      </div>

      <div className="bg-white border border-slate-200 rounded-md p-6 space-y-6">
        <div className="grid sm:grid-cols-2 gap-4">
          <div>
            <Label className="text-xs uppercase tracking-wide text-slate-500">Report label</Label>
            <Input data-testid="week-label-input" value={weekLabel} onChange={(e) => setWeekLabel(e.target.value)} className="mt-1.5" />
          </div>
          <div>
            <Label className="text-xs uppercase tracking-wide text-slate-500">Week date</Label>
            <Input data-testid="week-date-input" type="date" value={weekDate} onChange={(e) => setWeekDate(e.target.value)} className="mt-1.5" />
          </div>
        </div>

        <Dropzone label="Lead Dump (.xlsx) — required" file={leadFile}
                  onFile={(f) => setLeadFile(f)} onClear={() => setLeadFile(null)} testid="lead-dropzone" />

        <MultiDropzone files={appFiles} setFiles={setAppFiles} />

        <div>
          <div className="flex items-center justify-between">
            <Label className="text-xs uppercase tracking-wide text-slate-500">
              I also have a Joined Students file for this upload
            </Label>
            <Switch
              data-testid="joined-toggle"
              checked={showJoined}
              onCheckedChange={(v) => { setShowJoined(v); if (!v) setJoinedFile(null); }}
            />
          </div>
          {showJoined && (
            <div className="mt-2">
              <Dropzone label="Joined Students (.xlsx) — final list of who actually reported"
                        file={joinedFile} onFile={(f) => setJoinedFile(f)} onClear={() => setJoinedFile(null)}
                        testid="joined-dropzone" />
            </div>
          )}
        </div>

        <div>
          <Label className="text-xs uppercase tracking-wide text-slate-500 flex items-center gap-1.5">
            <CurrencyInr size={14} weight="bold" /> Amount spent per program (this week)
          </Label>
          <div className="grid sm:grid-cols-3 gap-3 mt-2">
            {programs.map((p) => (
              <div key={p}>
                <span className="text-xs text-slate-500">{p}</span>
                <Input data-testid={`amount-${p}`} type="number" placeholder="0"
                       value={amount[p] ?? ""} onChange={(e) => setAmount({ ...amount, [p]: e.target.value })} className="mt-1" />
              </div>
            ))}
          </div>
        </div>

        <div className="flex justify-end gap-3 pt-2">
          <Button data-testid="generate-submit-btn" onClick={submit} disabled={busy}
                  className="bg-[#002FA7] hover:bg-[#002FA7]/90 gap-2">
            <UploadSimple size={18} weight="bold" /> {busy ? "Working…" : "Generate report"}
          </Button>
        </div>
      </div>
    </div>
  );
}

const Dropzone = ({ label, file, onFile, onClear, testid }) => (
  <div>
    <Label className="text-xs uppercase tracking-wide text-slate-500">{label}</Label>
    {file ? (
      <div className="mt-1.5 flex items-center justify-between border border-slate-200 rounded-md px-4 py-3 bg-slate-50" data-testid={`${testid}-file`}>
        <div className="flex items-center gap-2 text-sm text-slate-700">
          <FileXls size={20} weight="fill" color="#10B981" /> {file.name}
        </div>
        <button onClick={onClear} className="text-slate-500 hover:text-red-500"><X size={16} weight="bold" /></button>
      </div>
    ) : (
      <label data-testid={testid}
             className="mt-1.5 flex flex-col items-center justify-center border-2 border-dashed border-slate-300 rounded-md bg-slate-50 p-8 cursor-pointer hover:border-[#002FA7] transition-colors">
        <UploadSimple size={26} className="text-slate-500 mb-2" />
        <span className="text-sm text-slate-500">Click to select .xlsx file</span>
        <input type="file" accept=".xlsx,.xls" className="hidden"
               onChange={(e) => e.target.files[0] && onFile(e.target.files[0])} />
      </label>
    )}
  </div>
);

const MultiDropzone = ({ files, setFiles }) => (
  <div>
    <Label className="text-xs uppercase tracking-wide text-slate-500">Application Dumps (.xlsx) — optional, one per program</Label>
    <label data-testid="app-dropzone"
           className="mt-1.5 flex flex-col items-center justify-center border-2 border-dashed border-slate-300 rounded-md bg-slate-50 p-6 cursor-pointer hover:border-[#002FA7] transition-colors">
      <UploadSimple size={22} className="text-slate-500 mb-1" />
      <span className="text-sm text-slate-500">Add application files</span>
      <input type="file" accept=".xlsx,.xls" multiple className="hidden"
             onChange={(e) => setFiles([...files, ...Array.from(e.target.files)])} />
    </label>
    {files.length > 0 && (
      <div className="mt-2 space-y-1.5">
        {files.map((f, i) => (
          <div key={`${f.name}-${f.size}`} className="flex items-center justify-between border border-slate-200 rounded-md px-3 py-2 bg-white text-sm">
            <span className="flex items-center gap-2 text-slate-700"><FileXls size={18} weight="fill" color="#10B981" /> {f.name}</span>
            <button onClick={() => setFiles(files.filter((_, x) => x !== i))} className="text-slate-500 hover:text-red-500"><X size={14} weight="bold" /></button>
          </div>
        ))}
      </div>
    )}
  </div>
);
