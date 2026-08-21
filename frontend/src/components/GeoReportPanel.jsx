import { useMemo, useState } from "react";
import { IndiaChoropleth } from "@/components/IndiaChoropleth";
import { fmtInt, fmtPct1 } from "@/lib/format";
import { gradeColor, rangeOf, textOn } from "@/lib/geoColors";

const cell = "border border-slate-200 px-3 py-1.5 text-sm whitespace-nowrap";

const Chips = ({ options, value, onChange, testidPrefix, labelFor }) => (
  <div className="flex flex-wrap items-center gap-2 mb-3" data-testid={`${testidPrefix}-filter`}>
    <span className="text-xs uppercase tracking-wide text-slate-500 mr-1">{labelFor}:</span>
    {options.map((opt) => (
      <button
        key={opt.value ?? opt}
        data-testid={`${testidPrefix}-${opt.value ?? opt}`}
        onClick={() => onChange(opt.value ?? opt)}
        className={`px-3 py-1 rounded-full text-sm border transition-colors ${
          value === (opt.value ?? opt)
            ? "bg-[#002FA7] text-white border-[#002FA7]"
            : "border-slate-200 text-slate-600 hover:border-[#002FA7] hover:text-[#002FA7]"
        }`}
      >
        {opt.label ?? opt}
      </button>
    ))}
  </div>
);

const METRICS = [
  { value: "leads", label: "Leads" },
  { value: "applications", label: "Applications" },
  { value: "conversion_pct", label: "Conversion %" },
];

const sortRows = (data, metric) =>
  Object.entries(data || {})
    .filter(([name]) => name !== "UNKNOWN")
    .sort((a, b) => (b[1][metric] ?? -1) - (a[1][metric] ?? -1));

export const GeoReportPanel = ({ result }) => {
  const byState = result.geo_by_state;
  const byCity = result.geo_by_city;
  const [prog, setProg] = useState("All");
  const [metric, setMetric] = useState("leads");

  const progOptions = useMemo(() => ["All", ...(result.programs || [])], [result.programs]);

  if (!byState || !Object.keys(byState.All || {}).length) {
    return (
      <div className="border border-dashed border-slate-300 rounded-md p-10 text-center text-slate-500"
           data-testid="geo-empty">
        No State/City data found in this file. Your CRM export needs a <b>State</b> (and
        optionally <b>City</b>) column for this to populate automatically.
      </div>
    );
  }

  const stateData = byState[prog] || byState.All;
  const cityData = (byCity && (byCity[prog] || byCity.All)) || {};
  const unknownState = stateData.UNKNOWN;

  const stateRows = sortRows(stateData, metric);
  const cityRows = sortRows(cityData, "applications").slice(0, 15);
  const conversionRange = rangeOf(stateRows.map(([, v]) => v.conversion_pct));

  const metricLabel = METRICS.find((m) => m.value === metric)?.label || "Leads";

  return (
    <div data-testid="geo-panel">
      <div className="flex flex-wrap items-start justify-between gap-4 mb-4">
        <Chips options={progOptions} value={prog} onChange={setProg} testidPrefix="geo-prog" labelFor="Program" />
        <Chips options={METRICS} value={metric} onChange={setMetric} testidPrefix="geo-metric" labelFor="Color by" />
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        <div className="bg-white border border-slate-200 rounded-md p-5">
          <h3 className="font-display font-bold text-slate-900 mb-3">State-wise ({metricLabel})</h3>
          <IndiaChoropleth data={stateData} metric={metric} label={metricLabel} />
        </div>

        <div className="overflow-x-auto thin-scroll border border-slate-200 rounded-md bg-white" data-testid="geo-state-table">
          <table className="border-collapse min-w-full">
            <thead>
              <tr>
                <th className={`${cell} bg-[#9DC3E6] text-left font-bold`}>State</th>
                <th className={`${cell} bg-[#C6EFCE] text-right font-bold`}>Leads</th>
                <th className={`${cell} bg-[#C6EFCE] text-right font-bold`}>Applications</th>
                <th className={`${cell} bg-[#C6EFCE] text-right font-bold`}>Conversion</th>
              </tr>
            </thead>
            <tbody>
              {stateRows.map(([name, v]) => {
                const fill = gradeColor(v.conversion_pct, conversionRange.min, conversionRange.max);
                return (
                  <tr key={name} className="hover:bg-slate-50" data-testid={`geo-state-row-${name}`}>
                    <td className={`${cell} font-medium text-slate-800`}>{name}</td>
                    <td className={`${cell} text-right`}>{fmtInt(v.leads)}</td>
                    <td className={`${cell} text-right`}>{fmtInt(v.applications)}</td>
                    <td
                      className={`${cell} text-right`}
                      style={fill ? { backgroundColor: fill, color: textOn(fill) } : undefined}
                    >
                      {fmtPct1(v.conversion_pct)}
                    </td>
                  </tr>
                );
              })}
              {stateRows.length === 0 && (
                <tr><td className={`${cell} text-center text-slate-500`} colSpan={4}>No data</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="mt-6 bg-white border border-slate-200 rounded-md p-5">
        <h3 className="font-display font-bold text-slate-900 mb-1">Top performing cities</h3>
        <p className="text-xs text-slate-500 mb-4">Ranked by applications — the cities actually converting, not just generating traffic.</p>
        {cityRows.length === 0 ? (
          <p className="text-sm text-slate-500">No application data with a city breakdown yet.</p>
        ) : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {cityRows.map(([name, v], i) => (
              <div key={name} className="border border-slate-200 rounded-md p-3 flex items-center justify-between"
                   data-testid={`geo-city-${name}`}>
                <div>
                  <span className="text-xs text-slate-500 mr-1.5">#{i + 1}</span>
                  <span className="font-semibold text-sm text-slate-800">{name}</span>
                  <p className="text-xs text-slate-500 mt-0.5">{fmtInt(v.leads)} leads · {fmtPct1(v.conversion_pct)} conv.</p>
                </div>
                <span className="font-display font-bold text-[#002FA7]">{fmtInt(v.applications)}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {unknownState && unknownState.leads > 0 && (
        <p className="text-xs text-slate-500 mt-3">
          {fmtInt(unknownState.leads)} lead{unknownState.leads === 1 ? "" : "s"} had no usable State value and are excluded from the map/table above.
        </p>
      )}
    </div>
  );
};
