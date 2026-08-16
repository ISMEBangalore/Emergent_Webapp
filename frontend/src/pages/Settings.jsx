import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import { FloppyDisk, Info } from "@phosphor-icons/react";

export default function Settings() {
  const [s, setS] = useState(null);
  const [saving, setSaving] = useState(false);
  const [avail, setAvail] = useState({ courses: [], publishers: [] });

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    api.getSettings().then(setS);
    api.getAvailable().then(setAvail).catch(() => {});
  }, []);
  if (!s) return <div className="p-8">Loading…</div>;

  const save = async () => {
    setSaving(true);
    try {
      const payload = {
        programs: s.programs,
        program_aliases: s.program_aliases,
        verified_logic: s.verified_logic,
        relevant_stages: s.relevant_stages,
        api_patterns: s.api_patterns,
        redirect_patterns: s.redirect_patterns,
        application_code_field: s.application_code_field,
        application_code_field_apps: s.application_code_field_apps,
        exclude_test_leads: s.exclude_test_leads,
        test_keywords: s.test_keywords,
        included_publishers: s.included_publishers,
        excluded_publishers: s.excluded_publishers,
        applications_payment_approved_only: s.applications_payment_approved_only,
      };
      await api.updateSettings(payload);
      toast.success("Settings saved — regenerate a report to apply");
    } catch { toast.error("Save failed"); }
    setSaving(false);
  };

  const toggleCourse = (name) => {
    const cur = s.programs || [];
    setS({ ...s, programs: cur.includes(name) ? cur.filter((x) => x !== name) : [...cur, name] });
  };
  const setAlias = (prog, text) => {
    const list = text.split(",").map((x) => x.trim()).filter(Boolean);
    const aliases = { ...(s.program_aliases || {}) };
    if (list.length) aliases[prog] = list; else delete aliases[prog];
    setS({ ...s, program_aliases: aliases });
  };
  const togglePublisher = (name) => {
    const inc = s.included_publishers || [];
    setS({ ...s, included_publishers: inc.includes(name) ? inc.filter((x) => x !== name) : [...inc, name] });
  };

  const listField = (label, key, help) => (
    <div>
      <Label className="text-sm font-semibold text-slate-700">{label}</Label>
      {help && <p className="text-xs text-slate-400 mb-1.5">{help}</p>}
      <Input data-testid={`setting-${key}`} value={(s[key] || []).join(", ")}
             onChange={(e) => setS({ ...s, [key]: e.target.value.split(",").map((x) => x.trim()).filter(Boolean) })}
             className="mt-1" />
    </div>
  );

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <h1 className="font-display text-3xl font-extrabold tracking-tight text-slate-900">Settings & Rules</h1>
      <p className="text-slate-500 mt-1 mb-6">Configure how leads are classified. Changes apply to newly generated reports.</p>

      <div className="flex items-start gap-3 bg-blue-50 border border-blue-200 rounded-md px-4 py-3 text-sm text-blue-800 mb-6">
        <Info size={18} weight="fill" className="mt-0.5 shrink-0" />
        <span>These are the business rules used by the report engine. Defaults are pre-filled to match your reference report.</span>
      </div>

      <div className="bg-white border border-slate-200 rounded-md p-6 space-y-6">
        {listField("Programs / Courses (columns)", "programs", "Comma-separated, or pick from detected courses below. Total = sum of these.")}
        {avail.courses.length > 0 && (
          <div className="flex flex-wrap gap-2" data-testid="available-courses">
            {avail.courses.map((c) => {
              const on = (s.programs || []).includes(c.name);
              return (
                <button key={c.name} data-testid={`course-chip-${c.name}`} onClick={() => toggleCourse(c.name)}
                        className={`px-3 py-1 rounded-full text-sm border transition-colors ${on ? "bg-[#002FA7] text-white border-[#002FA7]" : "border-slate-200 text-slate-600 hover:border-[#002FA7]"}`}>
                  {c.name} <span className="opacity-60">({c.count.toLocaleString()})</span>
                </button>
              );
            })}
          </div>
        )}

        {(s.programs || []).length > 0 && (
          <div className="border-t border-slate-100 pt-5">
            <Label className="text-sm font-semibold text-slate-700">Program aliases</Label>
            <p className="text-xs text-slate-400 mb-2">
              Merge other raw CRM course text into a program above instead of it showing as its own column
              — e.g. "PGDM(MKT/FIN/HR/BA/IA)" as an alias of "PGDM" folds those leads into the PGDM total.
            </p>
            <div className="space-y-2">
              {s.programs.map((p) => (
                <div key={p} className="flex items-center gap-2">
                  <span className="text-xs font-semibold text-slate-600 w-28 shrink-0 truncate" title={p}>{p}</span>
                  <Input data-testid={`alias-${p}`} value={(s.program_aliases?.[p] || []).join(", ")}
                         onChange={(e) => setAlias(p, e.target.value)}
                         placeholder="Other raw course text to merge in, comma-separated" className="text-sm" />
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="border-t border-slate-100 pt-5">
          <Label className="text-sm font-semibold text-slate-700">Publishers to include (columns)</Label>
          <p className="text-xs text-slate-400 mb-2">Pick which publishers appear in the By-Publisher report. None selected = show all detected.</p>
          {avail.publishers.length === 0 ? (
            <p className="text-xs text-slate-400">Generate a report first to detect publishers from your file.</p>
          ) : (
            <div className="flex flex-wrap gap-2" data-testid="available-publishers">
              {avail.publishers.map((p) => {
                const inc = s.included_publishers || [];
                const on = inc.length === 0 || inc.includes(p.name);
                return (
                  <button key={p.name} data-testid={`pub-chip-${p.name}`} onClick={() => togglePublisher(p.name)}
                          className={`px-3 py-1 rounded-full text-sm border transition-colors ${on ? "bg-[#002FA7] text-white border-[#002FA7]" : "border-slate-200 text-slate-400 hover:border-[#002FA7]"}`}>
                    {p.name} <span className="opacity-60">({p.count.toLocaleString()})</span>
                  </button>
                );
              })}
            </div>
          )}
          {(s.included_publishers || []).length > 0 && (
            <button data-testid="pub-clear" onClick={() => setS({ ...s, included_publishers: [] })}
                    className="mt-2 text-xs text-[#002FA7] underline">Clear selection (show all)</button>
          )}
        </div>

        <div>
          <Label className="text-sm font-semibold text-slate-700">Verified lead definition</Label>
          <p className="text-xs text-slate-400 mb-1.5">When is a lead counted as "Verified"?</p>
          <Select value={s.verified_logic} onValueChange={(v) => setS({ ...s, verified_logic: v })}>
            <SelectTrigger data-testid="setting-verified-logic" className="mt-1"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="any">Mobile OR Email verified</SelectItem>
              <SelectItem value="all">Mobile AND Email verified</SelectItem>
              <SelectItem value="mobile">Mobile verified only</SelectItem>
              <SelectItem value="email">Email verified only</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {listField("Relevant lead stages", "relevant_stages", "Raw CRM stages counted as 'Relevant Leads'.")}
        {listField("API lead patterns", "api_patterns", "Lead Origin text patterns that mark a lead as API-sourced.")}
        {listField("Redirect lead patterns", "redirect_patterns", "Lead Origin text patterns that mark a lead as redirect-sourced.")}

        <div className="border-t border-slate-100 pt-5">
          <div className="flex items-center justify-between">
            <div>
              <Label className="text-sm font-semibold text-slate-700">Exclude TEST leads</Label>
              <p className="text-xs text-slate-400 mt-0.5">Drop leads whose name/remark/email contains a test keyword (also the "TEST LEADS" stage).</p>
            </div>
            <button type="button" data-testid="setting-exclude-test"
                    onClick={() => setS({ ...s, exclude_test_leads: !s.exclude_test_leads })}
                    className={`relative h-6 w-11 rounded-full transition-colors ${s.exclude_test_leads ? "bg-[#002FA7]" : "bg-slate-300"}`}>
              <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white transition-all ${s.exclude_test_leads ? "left-[22px]" : "left-0.5"}`} />
            </button>
          </div>
          <div className="mt-3">
            <Label className="text-xs uppercase tracking-wide text-slate-500">Test keywords</Label>
            <Input data-testid="setting-test-keywords" value={(s.test_keywords || []).join(", ")}
                   onChange={(e) => setS({ ...s, test_keywords: e.target.value.split(",").map((x) => x.trim()).filter(Boolean) })}
                   className="mt-1" placeholder="test" />
          </div>
        </div>

        <div className="border-t border-slate-100 pt-5">
          <div className="flex items-center justify-between">
            <div>
              <Label className="text-sm font-semibold text-slate-700">Count only payment-approved applications</Label>
              <p className="text-xs text-slate-400 mt-0.5">When on, an application counts only if its Payment Status is "PAYMENT APPROVED" (then split into with/without code).</p>
            </div>
            <button type="button" data-testid="setting-payment-approved"
                    onClick={() => setS({ ...s, applications_payment_approved_only: !(s.applications_payment_approved_only ?? true) })}
                    className={`relative h-6 w-11 rounded-full transition-colors ${(s.applications_payment_approved_only ?? true) ? "bg-[#002FA7]" : "bg-slate-300"}`}>
              <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white transition-all ${(s.applications_payment_approved_only ?? true) ? "left-[22px]" : "left-0.5"}`} />
            </button>
          </div>
        </div>

        <div className="grid sm:grid-cols-2 gap-4">
          <div>
            <Label className="text-sm font-semibold text-slate-700">Lead "code" field</Label>
            <Input data-testid="setting-code-field" value={s.application_code_field || ""}
                   onChange={(e) => setS({ ...s, application_code_field: e.target.value })} className="mt-1.5" />
          </div>
          <div>
            <Label className="text-sm font-semibold text-slate-700">Application "code" field</Label>
            <Input data-testid="setting-code-field-apps" value={s.application_code_field_apps || "Discount Coupon"}
                   onChange={(e) => setS({ ...s, application_code_field_apps: e.target.value })} className="mt-1.5" />
          </div>
        </div>

        <div className="flex justify-end pt-2">
          <Button data-testid="save-settings-btn" onClick={save} disabled={saving} className="bg-[#002FA7] hover:bg-[#002FA7]/90 gap-2">
            <FloppyDisk size={18} weight="bold" /> {saving ? "Saving…" : "Save settings"}
          </Button>
        </div>
      </div>
    </div>
  );
}
