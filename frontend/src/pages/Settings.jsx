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

  useEffect(() => { api.getSettings().then(setS); }, []);
  if (!s) return <div className="p-8">Loading…</div>;

  const save = async () => {
    setSaving(true);
    try {
      const payload = {
        programs: s.programs,
        verified_logic: s.verified_logic,
        relevant_stages: s.relevant_stages,
        api_patterns: s.api_patterns,
        redirect_patterns: s.redirect_patterns,
        application_code_field: s.application_code_field,
        application_code_field_apps: s.application_code_field_apps,
      };
      await api.updateSettings(payload);
      toast.success("Settings saved — applied to new reports");
    } catch { toast.error("Save failed"); }
    setSaving(false);
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
        {listField("Programs (columns)", "programs", "Comma-separated. Total = sum of these programs.")}

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
