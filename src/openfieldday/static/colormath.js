// Pure color math for theme derivation. No DOM/browser dependencies, so the same
// file runs as a classic browser script (functions on the global scope) and as a
// Node module (see the UMD footer) for `node --test`.

function parseHex(hex) {
  let h = String(hex).trim().replace(/^#/, "");
  if (h.length === 3) h = h.split("").map((c) => c + c).join("");
  if (!/^[0-9a-fA-F]{6}$/.test(h)) throw new Error(`bad hex: ${hex}`);
  return {
    r: parseInt(h.slice(0, 2), 16),
    g: parseInt(h.slice(2, 4), 16),
    b: parseInt(h.slice(4, 6), 16),
  };
}

function _clampHex(n) {
  return Math.max(0, Math.min(255, Math.round(n))).toString(16).padStart(2, "0");
}

function _toLinear(c) {
  const cs = c / 255;
  return cs <= 0.03928 ? cs / 12.92 : Math.pow((cs + 0.055) / 1.055, 2.4);
}

function relativeLuminance(rgb) {
  return 0.2126 * _toLinear(rgb.r) + 0.7152 * _toLinear(rgb.g) + 0.0722 * _toLinear(rgb.b);
}

function contrastRatio(a, b) {
  const la = relativeLuminance(typeof a === "string" ? parseHex(a) : a);
  const lb = relativeLuminance(typeof b === "string" ? parseHex(b) : b);
  const hi = Math.max(la, lb), lo = Math.min(la, lb);
  return (hi + 0.05) / (lo + 0.05);
}

const ON_DARK = "#ffffff";
const ON_LIGHT = "#0d0d0d";

function onColor(bg) {
  return contrastRatio(bg, ON_DARK) >= contrastRatio(bg, ON_LIGHT) ? ON_DARK : ON_LIGHT;
}

function withAlpha(hex, a) {
  const { r, g, b } = parseHex(hex);
  return `rgba(${r}, ${g}, ${b}, ${a})`;
}

function mix(hexA, hexB, t) {
  const a = parseHex(hexA), b = parseHex(hexB);
  return "#" + _clampHex(a.r + (b.r - a.r) * t)
             + _clampHex(a.g + (b.g - a.g) * t)
             + _clampHex(a.b + (b.b - a.b) * t);
}

function derivePalette(base) {
  const { bg, fg, accent, good, bad } = base;
  const derived = {
    bg, panel: base.panel, fg, accent, good, bad,
    line: withAlpha(fg, 0.2),
    dim: mix(fg, bg, 0.4),
    "tile-bg": withAlpha(fg, 0.1),
    "on-accent": onColor(accent),
    "on-good": onColor(good),
    "on-bad": onColor(bad),
  };
  // Any explicit key in `base` (advanced raw override) wins over the derived value.
  return Object.assign(derived, base);
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { parseHex, relativeLuminance, contrastRatio, onColor, withAlpha, mix, derivePalette };
}
