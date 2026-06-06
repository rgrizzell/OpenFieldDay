async function load() {
  const [cfg, catalog] = await Promise.all([
    fetch("/api/config").then((r) => r.json()),
    fetch("/api/bonus-catalog").then((r) => r.json()),
  ]);
  document.querySelector(`input[name=mult][value="${cfg.power_multiplier}"]`).checked = true;
  const box = document.getElementById("bonuses");
  for (const [name, points] of Object.entries(catalog)) {
    const checked = name in cfg.bonuses ? "checked" : "";
    const label = document.createElement("label");
    label.innerHTML = `<input type="checkbox" data-points="${points}" value="${name}" ${checked}> ${name} (${points})`;
    box.appendChild(label);
  }
}

document.getElementById("form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const mult = Number(document.querySelector("input[name=mult]:checked").value);
  const bonuses = {};
  document.querySelectorAll("#bonuses input:checked").forEach((c) => {
    bonuses[c.value] = Number(c.dataset.points);
  });
  const r = await fetch("/api/config", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ power_multiplier: mult, bonuses }),
  });
  document.getElementById("saved").textContent = r.ok ? "Saved ✓" : "Error";
});

load();
