import { Fragment } from "react";
import { fmtInt, fmtMoney, fmtPct } from "@/lib/format";

const cell = "border border-slate-200 px-3 py-1.5 text-sm whitespace-nowrap";

export const ReportTable = ({ result }) => {
  const programs = result.programs;

  const renderVal = (v, fmt) => {
    if (fmt === "money") return fmtMoney(v);
    return fmtInt(v);
  };

  return (
    <div className="overflow-x-auto thin-scroll border border-slate-200 rounded-md bg-white" data-testid="report-table">
      <table className="border-collapse min-w-full">
        <thead>
          <tr>
            <th className={`${cell} bg-[#9DC3E6] text-left font-bold sticky left-0 z-10`} style={{ minWidth: 240 }}>
              Lead Stage
            </th>
            {programs.map((p) => (
              <Fragment key={p}>
                <th className={`${cell} bg-[#C6EFCE] text-right font-bold`}>{p}</th>
                <th className={`${cell} bg-[#C6EFCE] text-center font-bold`}>%</th>
              </Fragment>
            ))}
            <th className={`${cell} bg-[#C6EFCE] text-right font-bold`}>Total</th>
          </tr>
        </thead>
        <tbody>
          {result.matrix.map((m) => (
            <tr key={m.stage} className="hover:bg-slate-50" data-testid={`matrix-row-${m.stage}`}>
              <td className={`${cell} font-medium text-slate-800 sticky left-0 bg-white z-10`}>{m.stage}</td>
              {programs.map((p) => (
                <Fragment key={p}>
                  <td className={`${cell} text-right bg-[#FFFBEB]`}>{fmtInt(m.values[p])}</td>
                  <td className={`${cell} text-center text-slate-500 bg-[#F0FDF4]`}>{fmtPct(m.pct[p])}</td>
                </Fragment>
              ))}
              <td className={`${cell} text-right font-semibold`}>{fmtInt(m.total)}</td>
            </tr>
          ))}

          {result.summary.map((s, idx) => {
            if (s.kind === "section") {
              return (
                <tr key={idx}>
                  <td colSpan={programs.length * 2 + 2}
                      className={`${cell} bg-[#FFE699] text-center font-bold italic text-[#C00000]`}>
                    {s.label}
                  </td>
                </tr>
              );
            }
            const isHeader = s.kind === "header";
            const pctOnly = s.fmt === "pct_only";
            return (
              <tr key={idx} className="hover:bg-slate-50" data-testid={`summary-row-${s.label}`}>
                <td className={`${cell} font-semibold sticky left-0 z-10 ${isHeader ? "bg-[#BDD7EE]" : "bg-[#FFF6DA]"}`}>
                  {s.label}
                </td>
                {programs.map((p) => (
                  <Fragment key={p}>
                    <td className={`${cell} text-right`}>
                      {pctOnly ? fmtPct(s.pct?.[p]) : renderVal(s.values?.[p], s.fmt)}
                    </td>
                    <td className={`${cell} text-center text-slate-400`}>
                      {!pctOnly && s.pct ? fmtPct(s.pct?.[p]) : ""}
                    </td>
                  </Fragment>
                ))}
                <td className={`${cell} text-right font-semibold`}>
                  {pctOnly ? fmtPct(s.total_pct) : renderVal(s.total, s.fmt)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};
