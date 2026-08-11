import { fmtInt, fmtMoney } from "@/lib/format";
import { Users, FileText, CurrencyInr, SealCheck } from "@phosphor-icons/react";

const cards = [
  { key: "total_leads", label: "Total Leads", icon: Users, fmt: fmtInt, tint: "#002FA7" },
  { key: "total_applications", label: "Applications", icon: FileText, fmt: fmtInt, tint: "#10B981" },
  { key: "amount_spent", label: "Amount Spent", icon: CurrencyInr, fmt: fmtMoney, tint: "#F59E0B" },
  { key: "blended_cpa", label: "Blended CPA", icon: SealCheck, fmt: fmtMoney, tint: "#EF4444" },
];

export const KpiCards = ({ kpis }) => {
  if (!kpis) return null;
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4" data-testid="kpi-cards">
      {cards.map((c) => {
        const Icon = c.icon;
        return (
          <div key={c.key} className="bg-white border border-slate-200 rounded-md p-5 hover:shadow-sm transition-transform hover:-translate-y-[2px]"
               data-testid={`kpi-${c.key}`}>
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-semibold uppercase tracking-[0.15em] text-slate-500">{c.label}</span>
              <div className="h-8 w-8 rounded-md flex items-center justify-center" style={{ background: c.tint + "1a" }}>
                <Icon size={18} weight="bold" color={c.tint} />
              </div>
            </div>
            <p className="font-display text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900 truncate">{c.fmt(kpis[c.key])}</p>
          </div>
        );
      })}
    </div>
  );
};
