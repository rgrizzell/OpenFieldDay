let rateChart;

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

// --- Theme mode -----------------------------------------------------------
// Light/dark theme resolution lives in theme.js (shared with the settings page).
// The rate-chart color refresh below is registered there as an onThemeChange hook.

// Complete ARRL/RAC section list (contests.arrl.org), grouped by US call area and
// Canada. Worked sections are shaded; the rest render dim so the board shows what's
// still missing.
const SECTIONS = [
  { region: "0", secs: ["CO", "IA", "KS", "MN", "MO", "ND", "NE", "SD"] },
  { region: "1", secs: ["CT", "EMA", "ME", "NH", "RI", "VT", "WMA"] },
  { region: "2", secs: ["ENY", "NLI", "NNJ", "NNY", "SNJ", "WNY"] },
  { region: "3", secs: ["DE", "EPA", "MDC", "WPA"] },
  { region: "4", secs: ["AL", "GA", "KY", "NC", "NFL", "PR", "SC", "SFL", "TN", "VA", "VI", "WCF"] },
  { region: "5", secs: ["AR", "LA", "MS", "NM", "NTX", "OK", "STX", "WTX"] },
  { region: "6", secs: ["EB", "LAX", "ORG", "PAC", "SB", "SCV", "SDG", "SF", "SJV", "SV"] },
  { region: "7", secs: ["AK", "AZ", "EWA", "ID", "MT", "NV", "OR", "UT", "WWA", "WY"] },
  { region: "8", secs: ["MI", "OH", "WV"] },
  { region: "9", secs: ["IL", "IN", "WI"] },
  { region: "Canada", secs: ["AB", "BC", "GH", "MB", "NB", "NL", "NS", "ONE", "ONN", "ONS", "PE", "QC", "SK", "TER"] },
  // DX isn't an ARRL/RAC section, so it lights up when worked but doesn't count
  // toward the "/ 85" total.
  { region: "DX", secs: ["DX"], bonus: true },
];
const SECTION_TOTAL = SECTIONS
  .filter((g) => !g.bonus)
  .reduce((n, g) => n + g.secs.length, 0);
const COUNTABLE = new Set(SECTIONS.filter((g) => !g.bonus).flatMap((g) => g.secs));
const secTiles = {};

function initSections() {
  const grid = document.getElementById("secGrid");
  for (const g of SECTIONS) {
    const group = document.createElement("div");
    group.className = "sec-group";
    const label = document.createElement("div");
    label.className = "sec-region";
    label.textContent = g.region;
    const tiles = document.createElement("div");
    tiles.className = "sec-tiles";
    for (const s of g.secs) {
      const el = document.createElement("span");
      el.className = "sec";
      el.textContent = s;
      secTiles[s] = el;
      tiles.appendChild(el);
    }
    group.append(label, tiles);
    grid.appendChild(group);
  }
}

function renderSections(worked) {
  const set = new Set(worked);
  let hit = 0;
  for (const [s, el] of Object.entries(secTiles)) {
    const on = set.has(s);
    el.classList.toggle("worked", on);
    if (on && COUNTABLE.has(s)) hit += 1;
  }
  document.getElementById("secCount").textContent = `${hit} / ${SECTION_TOTAL}`;
}

function initRateChart() {
  const ctx = document.getElementById("rateChart");
  // Match the accent color; the "40" suffix is an 8-digit-hex alpha for the fill.
  const accent = cssVar("--accent");
  rateChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: [],
      datasets: [{
        data: [], borderColor: accent, borderWidth: 2,
        backgroundColor: accent + "40", fill: true,
        tension: 0.35, pointRadius: 0,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      animation: { duration: 400 },
      scales: { x: { display: false }, y: { display: false, beginAtZero: true } },
      plugins: { legend: { display: false }, tooltip: { enabled: false } },
    },
  });
}

function localTzAbbr() {
  const parts = new Intl.DateTimeFormat(undefined, { timeZoneName: "short" })
    .formatToParts(new Date());
  const p = parts.find((x) => x.type === "timeZoneName");
  return p ? p.value : "LOCAL";
}

function startClock() {
  const local = document.getElementById("clock");
  const utc = document.getElementById("clockUtc");
  document.getElementById("clockTz").textContent = localTzAbbr();
  const tick = () => {
    const now = new Date();
    local.textContent = now.toTimeString().slice(0, 8);   // HH:MM:SS, device local
    utc.textContent = now.toISOString().slice(11, 19);    // HH:MM:SS, UTC
  };
  tick();
  setInterval(tick, 1000);
}

// Re-read theme CSS variables into the rate sparkline after a theme switch, since
// Chart.js captures colors at construction and won't otherwise track the palette.
function applyChartColors() {
  if (rateChart) {
    const accent = cssVar("--accent");
    rateChart.data.datasets[0].borderColor = accent;
    rateChart.data.datasets[0].backgroundColor = accent + "40";
    rateChart.update();
  }
}

function render(s) {
  document.getElementById("score").textContent = s.score.toLocaleString();
  document.getElementById("total").textContent = s.total_qsos;
  document.getElementById("points").textContent = s.qso_points;
  document.getElementById("mult").textContent = s.power_multiplier;
  document.getElementById("bonus").textContent = s.bonus_points;
  document.getElementById("rate").textContent = Math.round(s.qsos_per_hour);

  // Background sparkline: QSOs per 5-min bucket over the trailing hour (oldest
  // → newest), computed server-side from QSO timestamps.
  const buckets = s.rate_buckets || [];
  rateChart.data.labels = buckets.map((_, i) => i);
  rateChart.data.datasets[0].data = buckets;
  rateChart.update();

  const conn = document.getElementById("conn");
  conn.className = s.connected ? "connected" : "disconnected";
  conn.textContent = s.connected ? "● Connected" : "⚠ Disconnected — reconnecting…";

  const CONTEST = {
    active: ["active", "● Contest Live"],
    pending: ["inactive", "Contest: Pending"],
    ended: ["inactive", "Contest: Ended"],
    unset: ["inactive", "Contest: Not Set"],
  };
  const contest = document.getElementById("contest");
  const [contestCls, contestText] = CONTEST[s.contest_state] || CONTEST.unset;
  contest.className = contestCls;
  contest.textContent = contestText;

  const tbody = document.querySelector("#opTable tbody");
  tbody.innerHTML = "";
  for (const op of s.top_operators || []) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${op.operator}</td><td>${op.count}</td>`;
    tbody.appendChild(tr);
  }

  const logBody = document.querySelector("#logTable tbody");
  logBody.innerHTML = "";
  for (const e of s.recent_qsos || []) {
    const tr = document.createElement("tr");
    for (const value of [e.call, e.band, e.mode, e.qso_class, e.section, e.operator]) {
      const td = document.createElement("td");
      td.textContent = value ?? "";  // textContent: avoid injecting raw log text
      tr.appendChild(td);
    }
    logBody.appendChild(tr);
  }

  renderSections(s.worked_sections || []);
}

async function applyConfig() {
  // theme.js fetches config and applies color overrides + the auto window; we
  // reuse the parsed config here for the dashboard-only logo tile.
  const cfg = await loadThemeConfig();
  if (cfg?.has_logo) {
    // Cache-bust so a swapped logo file shows without a hard refresh.
    document.getElementById("logoImg").src = "/logo?ts=" + Date.now();
    document.getElementById("logoPanel").hidden = false;
  }
}

function connect() {
  const es = new EventSource("/events");
  es.onmessage = (e) => render(JSON.parse(e.data));
  es.onerror = () => {
    document.getElementById("conn").className = "disconnected";
  };
}

// theme.js already applied the stored theme synchronously before first paint.
async function start() {
  onThemeChange(applyChartColors);  // refresh rate-chart palette on every theme switch
  await applyConfig();              // inject per-theme overrides + read the auto window
  initRateChart();
  initSections();
  startClock();
  setupThemeToggle();
  connect();
}
start();
