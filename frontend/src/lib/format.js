export const fmtInt = (n) =>
  n === null || n === undefined ? "-" : Number(n).toLocaleString("en-IN");

export const fmtMoney = (n) =>
  n === null || n === undefined || n === 0
    ? n === 0 ? "0" : "-"
    : "₹" + Number(n).toLocaleString("en-IN");

export const fmtPct = (n) =>
  n === null || n === undefined ? "-" : `${Math.round(n)}%`;

export const fmtPct1 = (n) =>
  n === null || n === undefined ? "-" : `${n}%`;
