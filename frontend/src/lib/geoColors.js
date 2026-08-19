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
