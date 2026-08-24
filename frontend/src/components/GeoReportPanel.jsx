import { useMemo, useState } from "react";
import { IndiaChoropleth } from "@/components/IndiaChoropleth";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
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

// geo_by_state/geo_by_city are nested [program_or_All][publisher_or_All] -> {location: {...}},
// so Program-wise, Publisher-wise, and Publisher-per-Program are all the same lookup with
// different keys - falls back to the program's "All"-publisher slice if a specific
// program+publisher combination has no precomputed entry (e.g. settings changed since upload).
const pickGeo = (byLoc, prog, pub) => {
  const progBucket = (byLoc && (byLoc[prog] || byLoc.All)) || {};
  return progBucket[pub] || progBucket.All || {};
};

export const GeoReportPanel = ({ result }) => {
  const byState = result.geo_by_state;
  const byCity = result.geo_by_city;
  const [prog, setProg] = useState("All");
  const [pub, setPub] = useState("All");
  const [metric, setMetric] = useState("leads");

  const progOptions = useMemo(() => ["All", ...(result.programs || [])], [result.programs]);
  const pubOptions = useMemo(
    () => ["All", ...Object.keys(byState?.All || {}).filter((k) => k !== "All")],
    [byState]
  );

  if (!byState || !Object.keys(byState.All?.All || {}).length) {
    return (
      <div className="border border-dashed border-slate-300 rounded-md p-10 text-center text-slate-500"
           data-testid="geo-empty">
        No State/City data found in this file. Your CRM export needs a <b>State</b> (and
        optionally <b>City</b>) column for this to populate automatically.
      </div>
    );
  }

  const stateData = pickGeo(byState, prog, pub);
  const cityData = pickGeo(byCity, prog, pub);
  const unknownState = stateData.UNKNOWN;

  const stateRows = sortRows(stateData, metric);
  const cityRows = sortRows(cityData, "applications").slice(0, 15);
  const conversionRange = rangeOf(stateRows.map(([, v]) => v.conversion_pct));

  const metricLabel = METRICS.find((m) => m.value === metric)?.label || "Leads";
  const filterSuffix = [prog !== "All" ? prog : null, pub !== "All" ? pub : null].filter(Boolean).join(" · ");

  return (
    <div data-testid="geo-panel">
      <div className="flex flex-wrap items-start justify-between gap-4 mb-4">
        <div className="flex flex-wrap items-center gap-4">
          <Chips options={progOptions} value={prog} onChange={setProg} testidPrefix="geo-prog" labelFor="Program" />
          <div className="flex items-center gap-2" data-testid="geo-pub-filter">
            <span className="text-xs uppercase tracking-wide text-slate-500">Publisher:</span>
            <Select value={pub} onValueChange={setPub}>
              <SelectTrigger className="w-52" data-testid="geo-pub-select">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {pubOptions.map((p) => (
                  <SelectItem key={p} value={p} data-testid={`geo-pub-opt-${p}`}>{p}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
        <Chips options={METRICS} value={metric} onChange={setMetric} testidPrefix="geo-metric" labelFor="Color by" />
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        <div className="bg-white border border-slate-200 rounded-md p-5">
          <h3 className="font-display font-bold text-slate-900 mb-3">
            State-wise ({metricLabel}){filterSuffix && <span className="text-slate-500 font-normal"> — {filterSuffix}</span>}
          </h3>
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
        <h3 className="font-display font-bold text-slate-900 mb-1">
          Top performing cities{filterSuffix && <span className="text-slate-500 font-normal"> — {filterSuffix}</span>}
        </h3>
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
