import { useMemo, useRef, useState } from "react";
import { geoMercator, geoPath } from "d3-geo";
import { feature } from "topojson-client";
import indiaTopo from "@/data/india-states-topo.json";
import { makeScale, GEO_EMPTY } from "@/lib/geoColors";

// A handful of legacy/alternate Indian state names some CRM exports still use,
// folded onto the map data's canonical (current) state names.
const STATE_NAME_ALIASES = {
  ORISSA: "ODISHA",
  PONDICHERRY: "PUDUCHERRY",
  UTTARANCHAL: "UTTARAKHAND",
  "JAMMU AND KASHMIR": "JAMMU & KASHMIR",
};

const norm = (s) => {
  const up = String(s || "").trim().toUpperCase();
  return STATE_NAME_ALIASES[up] || up;
};

const WIDTH = 480;
const HEIGHT = 520;

export const IndiaChoropleth = ({ data, metric = "leads", label = "Leads" }) => {
  const wrapRef = useRef(null);
  const [hover, setHover] = useState(null); // { name, x, y }

  const features = useMemo(() => feature(indiaTopo, indiaTopo.objects.layer).features, []);

  const projection = useMemo(() => {
    const geo = { type: "FeatureCollection", features };
    return geoMercator().fitSize([WIDTH, HEIGHT], geo);
  }, [features]);
  const path = useMemo(() => geoPath(projection), [projection]);

  const byState = data || {};
  const maxVal = useMemo(() => {
    let m = 0;
    for (const v of Object.values(data || {})) {
      const n = Number(v?.[metric]) || 0;
      if (n > m) m = n;
    }
    return m;
  }, [data, metric]);
  const scale = useMemo(() => makeScale(maxVal), [maxVal]);

  const valueFor = (stateName) => byState[norm(stateName)];

  const onMove = (e, stateName) => {
    const rect = wrapRef.current?.getBoundingClientRect();
    if (!rect) return;
    setHover({ name: stateName, x: e.clientX - rect.left, y: e.clientY - rect.top });
  };

  return (
    <div ref={wrapRef} className="relative" data-testid="india-choropleth">
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="w-full h-auto max-w-md mx-auto">
        {features.map((f) => {
          const name = f.properties?.ST_NM || "";
          const v = valueFor(name);
          const fill = v ? scale(Number(v[metric]) || 0) : GEO_EMPTY;
          return (
            <path
              key={name}
              d={path(f)}
              fill={fill}
              stroke="#FFFFFF"
              strokeWidth={0.75}
              onMouseMove={(e) => onMove(e, name)}
              onMouseLeave={() => setHover((h) => (h?.name === name ? null : h))}
              className="cursor-pointer transition-opacity hover:opacity-80"
              data-testid={`state-path-${name.replace(/\s+/g, "-")}`}
            />
          );
        })}
      </svg>
      {hover && (
        <div
          className="pointer-events-none absolute z-10 bg-slate-900 text-white text-xs rounded-md px-2.5 py-1.5 shadow-lg -translate-x-1/2"
          style={{ left: hover.x, top: hover.y - 12, transform: "translate(-50%, -100%)" }}
          data-testid="choropleth-tooltip"
        >
          <div className="font-semibold">{hover.name}</div>
          {valueFor(hover.name) ? (
            <>
              <div>Leads: {valueFor(hover.name).leads ?? 0}</div>
              <div>Applications: {valueFor(hover.name).applications ?? 0}</div>
              {valueFor(hover.name).conversion_pct != null && (
                <div>Conversion: {valueFor(hover.name).conversion_pct}%</div>
              )}
            </>
          ) : (
            <div className="text-slate-300">No data</div>
          )}
        </div>
      )}
      <div className="flex items-center justify-center gap-2 mt-3 text-xs text-slate-500">
        <span>Low</span>
        <div className="flex h-3 w-32 rounded-full overflow-hidden border border-slate-200">
          {[0, 0.2, 0.4, 0.6, 0.8, 1].map((t) => (
            <div key={t} className="flex-1" style={{ background: scale(t * maxVal) }} />
          ))}
        </div>
        <span>High ({label})</span>
      </div>
    </div>
  );
};
