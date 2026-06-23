// Shared light/dark theme resolution for the dashboard and the settings page.
// Both pages include this script before their own page script. The selected mode
// lives in localStorage, so switching it on the dashboard also themes the settings
// page. The dashboard registers an onThemeChange hook to refresh Chart.js colors;
// the settings page needs no hook.
//
// Behavior modes cycle on the dashboard's header icon and persist per-browser:
// "auto" follows time of day (light during the configured window), "system"
// follows the OS preference, "light"/"dark" are fixed and disable any switching.
const THEME_KEY = "ofd-theme-mode";
const THEME_MODES = ["auto", "system", "light", "dark"];
const MODE_ICON = { auto: "bx-time-five", system: "bx-desktop", light: "bx-sun", dark: "bx-moon" };
const MODE_LABEL = { auto: "Auto (time of day)", system: "Match browser", light: "Light", dark: "Dark" };
let themeMode = localStorage.getItem(THEME_KEY) || "auto";
let themeWindow = { start: 5, end: 21 };  // light-mode hours for "auto"; set from config

// Hooks run after data-theme actually changes (the dashboard refreshes its charts).
const themeChangeHooks = [];
function onThemeChange(fn) { themeChangeHooks.push(fn); }

function resolveTheme() {
  if (themeMode === "light" || themeMode === "dark") return themeMode;
  if (themeMode === "system") {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  const h = new Date().getHours();  // auto: light within [start, end), wraps midnight
  const { start, end } = themeWindow;
  const isLight = start <= end ? (h >= start && h < end) : (h >= start || h < end);
  return isLight ? "light" : "dark";
}

function applyThemeMode() {
  const theme = resolveTheme();
  const root = document.documentElement;
  if (root.getAttribute("data-theme") !== theme) {
    root.setAttribute("data-theme", theme);
    themeChangeHooks.forEach((fn) => fn());
  }
  const btn = document.getElementById("themeToggle");
  const icon = document.getElementById("themeIcon");
  if (icon) {
    const url = `url(/vendor/boxicons/${MODE_ICON[themeMode]}.svg)`;
    icon.style.maskImage = url;
    icon.style.webkitMaskImage = url;
  }
  if (btn) btn.title = `Theme: ${MODE_LABEL[themeMode]} (showing ${theme})`;
}

function setupThemeToggle() {
  const btn = document.getElementById("themeToggle");
  if (btn) {
    btn.addEventListener("click", () => {
      themeMode = THEME_MODES[(THEME_MODES.indexOf(themeMode) + 1) % THEME_MODES.length];
      localStorage.setItem(THEME_KEY, themeMode);
      applyThemeMode();
    });
  }
  window.matchMedia("(prefers-color-scheme: dark)")
    .addEventListener("change", () => { if (themeMode === "system") applyThemeMode(); });
  // Re-check every minute so "auto" flips at the window boundary without a reload.
  setInterval(() => { if (themeMode === "auto") applyThemeMode(); }, 60000);
}

// The 6 author-supplied base colors; a mode entry with all of them is a builder
// palette we derive in full, otherwise it's treated as raw overrides (legacy).
const BASE_KEYS = ["bg", "panel", "fg", "accent", "good", "bad"];

// Inject config color overrides as per-theme rules. Appended after the stylesheet
// so equal-specificity [data-theme=...] selectors win over the built-in defaults.
function injectThemeColors(colors) {
  if (!colors) return;
  let css = "";
  for (const theme of ["light", "dark"]) {
    const entry = colors[theme];
    if (!entry || Object.keys(entry).length === 0) continue;
    const hasFullBase = BASE_KEYS.every((k) => entry[k]);
    const vars = hasFullBase ? derivePalette(entry) : entry;
    const decls = Object.entries(vars).map(([k, v]) => `--${k}:${v};`).join("");
    if (decls) css += `[data-theme="${theme}"]{${decls}}`;
  }
  let el = document.getElementById("theme-overrides");
  if (!el) {
    el = document.createElement("style");
    el.id = "theme-overrides";
    document.head.appendChild(el);
  }
  el.textContent = css;
}

// Fetch config, apply its per-theme color overrides and the auto-mode window, then
// re-evaluate the theme. Returns the parsed config (or null) so the dashboard can
// also read non-theme fields like has_logo.
async function loadThemeConfig() {
  let cfg = null;
  try {
    cfg = await fetch("/api/config").then((r) => r.json());
  } catch {
    return null;  // pages still work on the built-in default theme
  }
  injectThemeColors(cfg.colors);
  if (cfg.theme) {
    themeWindow = {
      start: cfg.theme.auto_light_start ?? themeWindow.start,
      end: cfg.theme.auto_light_end ?? themeWindow.end,
    };
  }
  applyThemeMode();
  return cfg;
}

// Apply the stored mode synchronously before first paint so neither page flashes
// the wrong palette (config overrides + auto window arrive a moment later).
applyThemeMode();
