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

// Continuous interpolation across GEO_RAMP for a value in [0,1].
export function geoRampColor(t) {
  if (t <= 0) return GEO_RAMP[0];
  if (t >= 1) return GEO_RAMP[GEO_RAMP.length - 1];
  const scaled = t * (GEO_RAMP.length - 1);
  const i = Math.floor(scaled);
  const frac = scaled - i;
  const a = hexToRgb(GEO_RAMP[i]);
  const b = hexToRgb(GEO_RAMP[Math.min(i + 1, GEO_RAMP.length - 1)]);
  return rgbToHex(a.map((v, idx) => v + (b[idx] - v) * frac));
}

// sqrt scale: keeps small values visible rather than compressing everything near zero
export function makeScale(max) {
  if (!max || max <= 0) return () => GEO_EMPTY;
  return (value) => (value > 0 ? geoRampColor(Math.sqrt(value / max)) : GEO_EMPTY);
}
