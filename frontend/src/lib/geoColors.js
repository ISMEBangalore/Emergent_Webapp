// Sequential blue ramp anchored on the app's brand color (#002FA7), light -> dark,
// mixed toward white in sRGB. Six steps, monotonically decreasing lightness —
// matches the "sequential = one hue, light->dark" rule for magnitude encoding.
export const GEO_RAMP = ["#E0E6F4", "#B2C1E5", "#859BD5", "#5776C5", "#2950B5", "#002FA7"];
export const GEO_EMPTY = "#F1F3F9"; // no data for this location

function hexToRgb(hex) {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}
function rgbToHex([r, g, b]) {
  const h = (v) => Math.round(Math.max(0, Math.min(255, v))).toString(16).padStart(2, "0");
  return `#${h(r)}${h(g)}${h(b)}`;
}

// Continuous interpolation across a ramp of hex stops for a value in [0,1].
// `stops` gives each color's position along [0,1] (defaults to evenly spaced) —
// e.g. [0, 0.3, 1] makes the middle color sit at 30% instead of the midpoint, so
// one segment covers more of the range than the other.
export function rampColor(ramp, t, stops) {
  if (t <= 0) return ramp[0];
  if (t >= 1) return ramp[ramp.length - 1];
  const pos = stops || ramp.map((_, i) => i / (ramp.length - 1));
  let i = 0;
  while (i < pos.length - 2 && t > pos[i + 1]) i++;
  const frac = (t - pos[i]) / (pos[i + 1] - pos[i]);
  const a = hexToRgb(ramp[i]);
  const b = hexToRgb(ramp[i + 1]);
  return rgbToHex(a.map((v, idx) => v + (b[idx] - v) * frac));
}

// Continuous interpolation across GEO_RAMP for a value in [0,1].
export function geoRampColor(t) {
  return rampColor(GEO_RAMP, t);
}

// sqrt scale: keeps small values visible rather than compressing everything near zero
export function makeScale(max) {
  if (!max || max <= 0) return () => GEO_EMPTY;
  return (value) => (value > 0 ? geoRampColor(Math.sqrt(value / max)) : GEO_EMPTY);
}

// Green -> amber -> red grading scale for conversion-rate values. Validated
// colorblind-safe via the dataviz skill's palette checker.
export const GRADE_RAMP = ["#DC2626", "#F59E0B", "#10B981"];

// Relative to the actual min/max of the values on screen, not a fixed absolute
// percentage scale — the highest figure currently shown always reads green, the
// lowest always reads red, and the rest fade linearly between them. This matters
// because "good" varies wildly by metric (a 5% conversion rate can be the best
// state on the board): a fixed 0-100 scale would paint everything red for a
// column whose real values never approach 100%, while range-relative grading
// always spreads the full ramp across whatever range is actually present.
export function gradeColor(pctVal, min, max) {
  if (pctVal === null || pctVal === undefined || min === null || max === null) return null;
  if (min === max) return null; // every value on screen ties -> nothing to rank, so nothing to grade
  const t = (pctVal - min) / (max - min);
  return rampColor(GRADE_RAMP, Math.max(0, Math.min(1, t)));
}

// Min/max of a set of values, ignoring null/undefined/NaN — for feeding gradeColor
// the range of exactly what's currently rendered (one table column, one metric).
export function rangeOf(values) {
  const nums = values.filter((v) => typeof v === "number" && !Number.isNaN(v));
  if (!nums.length) return { min: null, max: null };
  return { min: Math.min(...nums), max: Math.max(...nums) };
}

export function relLuminance(hex) {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  const lin = (c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}
export function contrastRatio(hexA, hexB) {
  const [l1, l2] = [relLuminance(hexA), relLuminance(hexB)].sort((a, b) => b - a);
  return (l1 + 0.05) / (l2 + 0.05);
}
// Picks whichever of white/dark ink has higher contrast against a given fill, so
// text stays legible across the whole light-to-dark ramp.
export function textOn(bgHex) {
  const white = "#ffffff", dark = "#0f172a";
  return contrastRatio(bgHex, white) >= contrastRatio(bgHex, dark) ? white : dark;
}
