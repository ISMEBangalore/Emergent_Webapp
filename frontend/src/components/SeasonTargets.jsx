import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Target, PencilSimple, FloppyDisk } from "@phosphor-icons/react";
import { fmtInt } from "@/lib/format";

const MS_PER_DAY = 86400000;

function currentAdmitted(funnel, program) {
  const rows = funnel?.[program] || [];
  return rows.reduce((sum, r) => sum + (r.admission_fee_paid || 0), 0);
}

// Simple linear pace projection: whatever fraction of the season's calendar
// days has elapsed, assume progress continues at that same average rate.
// Deliberately not fancier than that - a mid-season CRM export doesn't carry
// enough signal (seasonality, marketing-spend changes) to justify more, and a
// naive linear read is easy for a non-technical viewer to sanity-check.
function projectPace(current, start, end) {
  if (!start || !end) return null;
  const startMs = new Date(`${start}T00:00:00Z`).getTime();
  const endMs = new Date(`${end}T00:00:00Z`).getTime();
  const nowMs = Date.now();
  if (!(endMs > startMs) || nowMs <= startMs) return null;
  const elapsedMs = Math.min(nowMs, endMs) - startMs;
  const totalMs = endMs - startMs;
  const daysElapsed = Math.max(1, Math.round(elapsedMs / MS_PER_DAY));
  if (elapsedMs >= totalMs) return null; // season already over - no projection needed
  return { projected: Math.round((current / elapsedMs) * totalMs), daysElapsed };
}

export const SeasonTargets = ({ season, programs, funnel, onSave }) => {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState({});
  const [saving, setSaving] = useState(false);

  const targets = season?.targets || {};
  const hasAnyTarget = programs.some((p) => targets[p] > 0);

  useEffect(() => {
    if (editing) {
      const next = {};
      for (const p of programs) next[p] = targets[p] ? String(targets[p]) : "";
      setDraft(next);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editing]);

  if (!programs?.length) return null;

  const save = async () => {
    setSaving(true);
    try {
      const parsed = {};
      for (const p of programs) {
        const n = parseInt(draft[p], 10);
        if (n > 0) parsed[p] = n;
      }
      await onSave(parsed);
      setEditing(false);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="bg-white border border-slate-200 rounded-md p-5 mb-6" data-testid="season-targets">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Target size={18} weight="bold" color="#002FA7" />
          <h3 className="font-display font-bold text-slate-900">Admission targets</h3>
        </div>
        {!editing && (
          <Button variant="outline" size="sm" data-testid="targets-edit-btn" onClick={() => setEditing(true)} className="gap-1.5">
            <PencilSimple size={14} weight="bold" /> {hasAnyTarget ? "Edit targets" : "Set targets"}
          </Button>
        )}
      </div>

      {editing ? (
        <div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3 mb-4">
            {programs.map((p) => (
              <div key={p}>
                <label className="text-xs uppercase tracking-wide text-slate-500 block mb-1">{p}</label>
                <Input
                  type="number" min="0" data-testid={`targets-input-${p}`}
                  placeholder="No target set"
                  value={draft[p] || ""}
                  onChange={(e) => setDraft((d) => ({ ...d, [p]: e.target.value }))}
                />
              </div>
            ))}
          </div>
          <div className="flex items-center gap-2">
            <Button size="sm" data-testid="targets-save-btn" onClick={save} disabled={saving} className="bg-[#002FA7] hover:bg-[#002FA7]/90 gap-1.5">
              <FloppyDisk size={14} weight="bold" /> {saving ? "Saving…" : "Save targets"}
            </Button>
            <Button size="sm" variant="outline" data-testid="targets-cancel-btn" onClick={() => setEditing(false)}>Cancel</Button>
          </div>
        </div>
      ) : !hasAnyTarget ? (
        <p className="text-sm text-slate-500" data-testid="targets-empty">
          No admission targets set for this season yet — set one per program to track progress and see a pace-based projection.
        </p>
      ) : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {programs.filter((p) => targets[p] > 0).map((p) => {
            const current = currentAdmitted(funnel, p);
            const target = targets[p];
            const pct = Math.min(100, Math.round((current / target) * 100));
            const pace = projectPace(current, season?.start, season?.end);
            return (
              <div key={p} className="border border-slate-200 rounded-md p-4" data-testid={`targets-card-${p}`}>
                <p className="text-sm font-bold text-slate-800 mb-1">{p}</p>
                <p className="font-display text-xl font-extrabold text-slate-900">
                  {fmtInt(current)} <span className="text-sm font-medium text-slate-400">/ {fmtInt(target)}</span>
                </p>
                <div className="h-2 bg-slate-100 rounded-full overflow-hidden mt-2 mb-1.5">
                  <div
                    className={`h-full rounded-full ${pct >= 100 ? "bg-emerald-500" : "bg-[#002FA7]"}`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <p className="text-xs text-slate-500">{pct}% of target · admission fee paid</p>
                {pace && (
                  <p className="text-xs text-slate-500 mt-1.5 pt-1.5 border-t border-slate-100">
                    At the current pace ({pace.daysElapsed}d in): projected{" "}
                    <span className={`font-semibold ${pace.projected >= target ? "text-emerald-600" : "text-amber-600"}`}>
                      ~{fmtInt(pace.projected)}
                    </span>{" "}
                    by season end
                  </p>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
