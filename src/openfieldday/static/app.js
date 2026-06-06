let chart;

function initChart() {
  const ctx = document.getElementById("bandModeChart");
  chart = new Chart(ctx, {
    type: "bar",
    data: { labels: [], datasets: [] },
    options: {
      responsive: true, maintainAspectRatio: false,
      scales: { x: { stacked: true, ticks: { color: "#f5f7ff" } },
                y: { stacked: true, ticks: { color: "#f5f7ff" } } },
      plugins: { legend: { labels: { color: "#f5f7ff" } } },
    },
  });
}

const GROUP_COLORS = { Phone: "#118ab2", CW: "#ffd166", Digital: "#06d6a0" };

function render(s) {
  document.getElementById("score").textContent = s.score.toLocaleString();
  document.getElementById("total").textContent = s.total_qsos;
  document.getElementById("points").textContent = s.qso_points;
  document.getElementById("mult").textContent = s.power_multiplier;
  document.getElementById("bonus").textContent = s.bonus_points;
  document.getElementById("rate10").textContent = Math.round(s.rate_10min);
  document.getElementById("rate60").textContent = Math.round(s.rate_60min);

  const conn = document.getElementById("conn");
  conn.className = s.connected ? "connected" : "disconnected";
  conn.textContent = s.connected ? "● Connected" : "⚠ Disconnected — reconnecting…";

  const bands = [...new Set(s.band_mode.map((b) => b.band))].sort();
  const groups = ["Phone", "CW", "Digital"];
  chart.data.labels = bands;
  chart.data.datasets = groups.map((g) => ({
    label: g,
    backgroundColor: GROUP_COLORS[g],
    data: bands.map((band) => {
      const hit = s.band_mode.find((b) => b.band === band && b.mode_group === g);
      return hit ? hit.count : 0;
    }),
  }));
  chart.update();

  const tbody = document.querySelector("#opTable tbody");
  tbody.innerHTML = "";
  for (const op of s.by_operator) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${op.operator}</td><td>${op.count}</td>`;
    tbody.appendChild(tr);
  }
}

function connect() {
  const es = new EventSource("/events");
  es.onmessage = (e) => render(JSON.parse(e.data));
  es.onerror = () => {
    document.getElementById("conn").className = "disconnected";
  };
}

initChart();
connect();
