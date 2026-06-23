const test = require("node:test");
const assert = require("node:assert");
const cm = require("./colormath.js");

test("parseHex handles #rrggbb", () => {
  assert.deepStrictEqual(cm.parseHex("#0032CB"), { r: 0, g: 50, b: 203 });
});

test("parseHex expands #rgb shorthand", () => {
  assert.deepStrictEqual(cm.parseHex("#abc"), { r: 170, g: 187, b: 204 });
});

test("parseHex rejects malformed input", () => {
  assert.throws(() => cm.parseHex("#xyz123"));
  assert.throws(() => cm.parseHex("0032CB!"));
});

test("mix midpoint of black and white is mid-grey", () => {
  assert.strictEqual(cm.mix("#000000", "#ffffff", 0.5), "#808080");
});

test("withAlpha builds rgba() from a hex", () => {
  assert.strictEqual(cm.withAlpha("#586e75", 0.2), "rgba(88, 110, 117, 0.2)");
});

test("onColor picks white on a dark accent", () => {
  const on = cm.onColor("#0032CB");
  assert.strictEqual(on, "#ffffff");
  assert.ok(cm.contrastRatio("#0032CB", on) >= 4.5);
});

test("onColor picks dark on a light accent (Flash yellow) where #fff would fail", () => {
  const on = cm.onColor("#F2B705");
  assert.strictEqual(on, "#0d0d0d");
  assert.ok(cm.contrastRatio("#F2B705", on) >= 4.5);
  assert.ok(cm.contrastRatio("#F2B705", "#ffffff") < 4.5); // the old hardcoded white was unreadable
});

test("derivePalette returns all 12 keys", () => {
  const p = cm.derivePalette({
    bg: "#F4F1E9", panel: "#E7E8E2", fg: "#1A1A1A",
    accent: "#0032CB", good: "#2E7D32", bad: "#D90000",
  });
  for (const k of ["bg","panel","fg","accent","good","bad",
                   "line","dim","tile-bg","on-accent","on-good","on-bad"]) {
    assert.ok(k in p, `missing ${k}`);
  }
  assert.strictEqual(p["on-accent"], "#ffffff");
});

test("derivePalette lets an explicit key override the derived value", () => {
  const p = cm.derivePalette({
    bg: "#ffffff", panel: "#eeeeee", fg: "#000000",
    accent: "#0032CB", good: "#2E7D32", bad: "#D90000",
    "on-accent": "#123456",
  });
  assert.strictEqual(p["on-accent"], "#123456");
});

test("derivePalette ignores keys outside the 12-key palette", () => {
  const p = cm.derivePalette({
    bg: "#ffffff", panel: "#eeeeee", fg: "#000000",
    accent: "#0032CB", good: "#2E7D32", bad: "#D90000",
    "a}html{display:none": "#000000",
  });
  assert.ok(!("a}html{display:none" in p));
});
