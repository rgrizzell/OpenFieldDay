const BASE_FIELDS = [
  ["bg", "Background"], ["panel", "Panel / tiles"], ["fg", "Text"],
  ["accent", "Accent"], ["good", "Good (status)"], ["bad", "Bad (status)"],
];

// Solarized base colors — used to seed inputs when no custom palette is saved.
const DEFAULTS = {
  light: { bg: "#fdf6e3", panel: "#eee8d5", fg: "#586e75", accent: "#268bd2", good: "#859900", bad: "#dc322f" },
  dark:  { bg: "#002b36", panel: "#073642", fg: "#93a1a1", accent: "#268bd2", good: "#859900", bad: "#dc322f" },
};

const state = { light: { ...DEFAULTS.light }, dark: { ...DEFAULTS.dark } };
let mode = "light";

function isFullBase(o) { return o && BASE_FIELDS.every(([k]) => o[k]); }

async function loadConfig() {
  try {
    const cfg = await fetch("/api/config").then((r) => r.json());
    for (const m of ["light", "dark"]) {
      if (isFullBase(cfg.colors && cfg.colors[m])) {
        for (const [k] of BASE_FIELDS) state[m][k] = cfg.colors[m][k];
      }
    }
  } catch { /* keep Solarized defaults */ }
}

function renderInputs() {
  const box = document.getElementById("inputs");
  box.innerHTML = "";
  for (const [key, label] of BASE_FIELDS) {
    const row = document.createElement("div");
    row.className = "builder-row";
    row.innerHTML =
      `<label for="c_${key}">${label}</label>` +
      `<input type="color" id="c_${key}" value="${state[mode][key]}">` +
      `<input type="text" id="t_${key}" value="${state[mode][key]}" spellcheck="false">`;
    box.appendChild(row);
    const color = row.querySelector(`#c_${key}`);
    const text = row.querySelector(`#t_${key}`);
    const set = (v) => { state[mode][key] = v; color.value = v; text.value = v; renderPreview(); };
    color.addEventListener("input", () => set(color.value));
    text.addEventListener("change", () => {
      if (/^#[0-9a-fA-F]{6}$/.test(text.value)) set(text.value);
      else text.value = state[mode][key];
    });
  }
}

function renderPreview() {
  const pane = document.getElementById("previewPane");
  pane.setAttribute("data-theme", mode);
  const vars = derivePalette(state[mode]);
  for (const [k, v] of Object.entries(vars)) pane.style.setProperty(`--${k}`, v);
}

function setMode(m) {
  mode = m;
  document.querySelectorAll(".tabs button").forEach((b) =>
    b.classList.toggle("active", b.dataset.mode === m));
  renderInputs();
  renderPreview();
}

async function save() {
  const r = await fetch("/api/config", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ colors: { light: state.light, dark: state.dark } }),
  });
  document.getElementById("status").textContent = r.ok ? "Saved ✓" : "Error";
}

async function reset() {
  await fetch("/api/config", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ colors: {} }),
  });
  state.light = { ...DEFAULTS.light };
  state.dark = { ...DEFAULTS.dark };
  renderInputs();
  renderPreview();
  document.getElementById("status").textContent = "Reset to default ✓";
}

document.querySelectorAll(".tabs button").forEach((b) =>
  b.addEventListener("click", () => setMode(b.dataset.mode)));
document.getElementById("save").addEventListener("click", save);
document.getElementById("reset").addEventListener("click", reset);

(async () => { await loadConfig(); setMode("light"); })();
