# Logo-friendly Theming + Theme Builder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a non-expert build a dashboard theme from a logo's colors via an in-app builder, and ship the RARA palette as the example — with text-on-color and border/muted/tile shades derived automatically so any palette stays readable.

**Architecture:** Pure color math lives in a new browser+Node module `colormath.js` (`derivePalette` turns 6 base colors into the full CSS-variable set, including contrast-correct `on-*` colors). `theme.js` derives at inject time; a new `builder.html`/`builder.js` page authors light+dark palettes with a live preview and saves them into the existing `colors` config block. The dashboard CSS gains `--on-*` variables, replacing 5 hardcoded contrast colors.

**Tech Stack:** Vanilla JS (no build step, classic scripts), CSS custom properties, FastAPI + Pydantic backend, pytest, Node's built-in `node --test`.

## Global Constraints

- Target runtime is a Raspberry Pi; keep it lightweight. **Node is dev/test-only — never a runtime dependency.** The app is served as static files.
- Frontend is **classic scripts** (no ES modules, no bundler). Shared code is exposed on the global scope; `colormath.js` adds a UMD footer for Node.
- Python venv is 3.11: run tests with `.venv/bin/python -m pytest -q`.
- Derivation constants (matched to Solarized): `line` = fg @ alpha **0.20**, `tile-bg` = fg @ alpha **0.10**, `dim` = `mix(fg, bg, 0.40)`.
- On-color constants: near-white `#ffffff`, near-black `#0d0d0d`; pick by max WCAG contrast.
- The 6 base color keys, in order: `bg`, `panel`, `fg`, `accent`, `good`, `bad`.
- All commits end with the trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`
- `config.yaml` is gitignored — changes to it are local and NOT committed.

---

## File Structure

- `src/openfieldday/static/colormath.js` — NEW. Pure color math + UMD footer. One responsibility: color computation.
- `src/openfieldday/static/colormath.test.js` — NEW. `node --test` coverage of the math.
- `package.json` — NEW. Dev-only test script, no dependencies.
- `src/openfieldday/static/styles.css` — MODIFY. Add `--on-*` vars; replace 5 hardcoded colors; add builder + preview styles.
- `src/openfieldday/static/theme.js` — MODIFY. `injectThemeColors` derives full palettes via `colormath`.
- `src/openfieldday/static/index.html`, `settings.html` — MODIFY. Load `colormath.js` before `theme.js`.
- `src/openfieldday/static/builder.html` / `builder.js` — NEW. The builder page.
- `src/openfieldday/app.py` — MODIFY. Optional `power_multiplier`/`bonuses`; validate+persist `colors`.
- `tests/test_app.py` — MODIFY. Colors validation/persistence tests.
- `README.md` — MODIFY. Document the builder + RARA example.
- `config.yaml` — MODIFY (local only). RARA base palette.

---

## Task 1: colormath.js — pure color math under `node --test`

**Files:**
- Create: `src/openfieldday/static/colormath.js`
- Create: `src/openfieldday/static/colormath.test.js`
- Create: `package.json`
- Modify: `.gitignore` (add `node_modules/`)

**Interfaces:**
- Produces (global in browser; `module.exports` in Node):
  - `parseHex(hex: string) -> {r,g,b}`
  - `relativeLuminance({r,g,b}) -> number`
  - `contrastRatio(a: string|{r,g,b}, b: string|{r,g,b}) -> number`
  - `onColor(bg: string) -> "#ffffff" | "#0d0d0d"`
  - `withAlpha(hex: string, a: number) -> "rgba(r, g, b, a)"`
  - `mix(hexA: string, hexB: string, t: number) -> "#rrggbb"`
  - `derivePalette(base: {bg,panel,fg,accent,good,bad, ...overrides}) -> {bg,panel,fg,accent,good,bad,line,dim,"tile-bg","on-accent","on-good","on-bad"}`

- [ ] **Step 1: Write the failing test**

Create `src/openfieldday/static/colormath.test.js`:

```js
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `node --test src/openfieldday/static/colormath.test.js`
Expected: FAIL — `Cannot find module './colormath.js'`.

- [ ] **Step 3: Write the implementation**

Create `src/openfieldday/static/colormath.js`:

```js
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
```

- [ ] **Step 4: Create `package.json` (dev-only test runner)**

Create `package.json` at the repo root:

```json
{
  "name": "openfieldday-frontend-tests",
  "private": true,
  "version": "0.0.0",
  "description": "Dev-only Node tests for the static frontend (no runtime deps).",
  "scripts": {
    "test": "node --test src/openfieldday/static"
  }
}
```

- [ ] **Step 5: Add `node_modules/` to `.gitignore`**

Append a line `node_modules/` to `.gitignore` (guards against accidental commits even though there are no deps today).

- [ ] **Step 6: Run the tests to verify they pass**

Run: `node --test src/openfieldday/static/colormath.test.js`
Expected: PASS — all tests pass (`# pass 9`).

- [ ] **Step 7: Commit**

```bash
git add src/openfieldday/static/colormath.js src/openfieldday/static/colormath.test.js package.json .gitignore
git commit -m "feat: colormath.js — pure theme color math with node --test" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: CSS on-color variables (palette-proof contrast)

**Files:**
- Modify: `src/openfieldday/static/styles.css`

**Interfaces:**
- Produces: CSS variables `--on-accent`, `--on-good`, `--on-bad` on both palettes.

- [ ] **Step 1: Add `--on-*` to the light palette**

In `src/openfieldday/static/styles.css`, in the `:root, [data-theme="light"]` block, add to the existing declarations:

```css
  --on-accent:#fff; --on-good:#003; --on-bad:#fdf6e3;
```

- [ ] **Step 2: Add `--on-*` to the dark palette**

In the `[data-theme="dark"]` block, add the same line (Solarized's good/bad/accent keep these same on-colors in both modes):

```css
  --on-accent:#fff; --on-good:#003; --on-bad:#fdf6e3;
```

- [ ] **Step 3: Replace the 5 hardcoded contrast colors**

Make these exact replacements in `styles.css`:

```css
/* was: #conn.connected { background:var(--good); color:#003; } */
#conn.connected { background:var(--good); color:var(--on-good); }
/* was: #conn.disconnected { background:var(--bad); color:#fdf6e3; } */
#conn.disconnected { background:var(--bad); color:var(--on-bad); }
/* was: #contest.active { background:var(--good); color:#003; } */
#contest.active { background:var(--good); color:var(--on-good); }
/* was: .sec.worked { background:var(--good); color:#003; } */
.sec.worked { background:var(--good); color:var(--on-good); }
```

And in the settings submit button rule, change `color:#fff` to `color:var(--on-accent)`:

```css
#form button[type="submit"] { align-self:flex-start; padding:0.5rem 1.2rem;
  font:inherit; font-weight:700; color:var(--on-accent); background:var(--accent);
  border:none; border-radius:0.5rem; cursor:pointer; }
```

- [ ] **Step 4: Verify no hardcoded contrast colors remain on var-backed elements**

Run: `grep -nE "color:#(003|fdf6e3|fff)\b" src/openfieldday/static/styles.css`
Expected: no matches (exit status 1 / empty output). The only literal hex left should be inside the `--on-*` variable *definitions*, which the grep's `color:` prefix excludes.

- [ ] **Step 5: Visually verify the Solarized dashboard is unchanged**

Run this from the repo root (writes a temp config, screenshots the dashboard):

```bash
.venv/bin/python -c "from openfieldday.config import Config; Config().save('/tmp/ofd_t.yaml')"
.venv/bin/python -c "
import uvicorn, threading, time, subprocess
from openfieldday.app import create_app
app = create_app(config_path='/tmp/ofd_t.yaml', start_source=False)
s = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=8013, log_level='error'))
threading.Thread(target=s.run, daemon=True).start(); time.sleep(1.5)
subprocess.run(['chromium-browser','--headless','--no-sandbox','--disable-gpu','--hide-scrollbars','--window-size=1280,720','--screenshot=/tmp/ofd_task2.png','http://127.0.0.1:8013/index.html'], timeout=40)
s.should_exit=True; time.sleep(0.3)
" 2>/dev/null
```

Open `/tmp/ofd_task2.png` and confirm the connected pill, contest pill, and any worked section tiles look identical to before (dark text on green, etc.).

- [ ] **Step 6: Commit**

```bash
git add src/openfieldday/static/styles.css
git commit -m "feat: derive text-on-color via --on-* CSS variables" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: theme.js derives palettes via colormath

**Files:**
- Modify: `src/openfieldday/static/theme.js`
- Modify: `src/openfieldday/static/index.html`
- Modify: `src/openfieldday/static/settings.html`

**Interfaces:**
- Consumes: `derivePalette` (global, from Task 1).
- Produces: `injectThemeColors(colors)` that derives full palettes from 6-base entries; partial entries inject raw (legacy behavior).

- [ ] **Step 1: Load `colormath.js` before `theme.js` in `index.html`**

In `src/openfieldday/static/index.html`, change the script block to:

```html
  <script src="/vendor/chart.min.js"></script>
  <script src="/colormath.js"></script>
  <script src="/theme.js"></script>
  <script src="/app.js"></script>
```

- [ ] **Step 2: Load `colormath.js` before `theme.js` in `settings.html`**

In `src/openfieldday/static/settings.html`, change the script block to:

```html
  <script src="/colormath.js"></script>
  <script src="/theme.js"></script>
  <script src="/settings.js"></script>
```

- [ ] **Step 3: Update `injectThemeColors` in `theme.js`**

Replace the existing `injectThemeColors` function with:

```js
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
```

- [ ] **Step 4: Verify a base-color config derives a full theme**

Run from the repo root (writes a RARA-light config, screenshots the dashboard):

```bash
.venv/bin/python -c "
from openfieldday.config import Config
Config(colors={'light':{'bg':'#F4F1E9','panel':'#E7E8E2','fg':'#1A1A1A','accent':'#0032CB','good':'#2E7D32','bad':'#D90000'},
               'dark':{'bg':'#0A1A3F','panel':'#11254F','fg':'#E7E8E2','accent':'#5A9CF2','good':'#43A047','bad':'#D90000'}}).save('/tmp/ofd_t3.yaml')
"
.venv/bin/python -c "
import uvicorn, threading, time, subprocess
from openfieldday.app import create_app
app = create_app(config_path='/tmp/ofd_t3.yaml', start_source=False)
s = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=8014, log_level='error'))
threading.Thread(target=s.run, daemon=True).start(); time.sleep(1.5)
subprocess.run(['chromium-browser','--headless','--no-sandbox','--disable-gpu','--hide-scrollbars','--window-size=1280,720','--screenshot=/tmp/ofd_task3.png','http://127.0.0.1:8014/index.html'], timeout=40)
s.should_exit=True; time.sleep(0.3)
" 2>/dev/null
```

Open `/tmp/ofd_task3.png`: the dashboard should show the cream/cobalt RARA look (light mode is active midday), with readable text on the connected pill and worked tiles — proving `line`/`dim`/`tile-bg`/`on-*` were derived.

- [ ] **Step 5: Commit**

```bash
git add src/openfieldday/static/theme.js src/openfieldday/static/index.html src/openfieldday/static/settings.html
git commit -m "feat: derive full palettes from base colors in theme.js" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Backend — accept and validate `colors`

**Files:**
- Modify: `src/openfieldday/app.py`
- Test: `tests/test_app.py`

**Interfaces:**
- Consumes: `Config.colors` (dict), `Config.save`, `Config.to_public_dict` (already returns `colors` as `{light, dark}`).
- Produces: `POST /api/config` accepts optional `colors`, `power_multiplier`, `bonuses`; validates hex; persists.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_app.py`:

```python
def test_post_config_accepts_colors(tmp_path):
    app, client = make_client(tmp_path)
    palette = {
        "light": {"bg": "#F4F1E9", "panel": "#E7E8E2", "fg": "#1A1A1A",
                  "accent": "#0032CB", "good": "#2E7D32", "bad": "#D90000"},
        "dark": {"bg": "#0A1A3F", "panel": "#11254F", "fg": "#E7E8E2",
                 "accent": "#5A9CF2", "good": "#43A047", "bad": "#D90000"},
    }
    r = client.post("/api/config", json={"colors": palette})
    assert r.status_code == 200
    cfg = client.get("/api/config").json()
    assert cfg["colors"]["light"]["accent"] == "#0032CB"
    assert cfg["colors"]["dark"]["bg"] == "#0A1A3F"


def test_post_config_rejects_bad_hex(tmp_path):
    app, client = make_client(tmp_path)
    r = client.post("/api/config", json={"colors": {"light": {"bg": "red"}}})
    assert r.status_code == 422


def test_post_config_colors_only_keeps_other_fields(tmp_path):
    app, client = make_client(tmp_path)
    client.post("/api/config", json={"power_multiplier": 5, "bonuses": {}})
    client.post("/api/config", json={"colors": {"light": {"bg": "#112233", "panel": "#223344",
                "fg": "#ffffff", "accent": "#0032CB", "good": "#2E7D32", "bad": "#D90000"}}})
    cfg = client.get("/api/config").json()
    assert cfg["power_multiplier"] == 5          # untouched by a colors-only POST
    assert cfg["colors"]["light"]["bg"] == "#112233"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_app.py -q -k "colors"`
Expected: FAIL — `test_post_config_accepts_colors` and `_colors_only` fail (colors not persisted / 422 from required `power_multiplier`), `_rejects_bad_hex` may pass for the wrong reason.

- [ ] **Step 3: Make `power_multiplier`/`bonuses` optional and add the `colors` field + validator**

In `src/openfieldday/app.py`, add `import re` near the top, and replace the `ConfigUpdate` model with:

```python
_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


class ConfigUpdate(BaseModel):
    # All optional so a caller can update just one concern (e.g. the theme builder
    # posts only `colors`); post_config applies whichever fields are present.
    power_multiplier: int | None = None
    bonuses: dict[str, int] | None = None
    n3fjp_host: str | None = None
    n3fjp_port: int | None = None
    colors: dict | None = None

    @field_validator("power_multiplier")
    @classmethod
    def _check_multiplier(cls, v: int | None) -> int | None:
        if v is not None and v not in POWER_MULTIPLIERS:
            raise ValueError(f"power_multiplier must be one of {sorted(POWER_MULTIPLIERS)}")
        return v

    @field_validator("n3fjp_host")
    @classmethod
    def _check_host(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("n3fjp_host must not be empty")
        return v

    @field_validator("n3fjp_port")
    @classmethod
    def _check_port(cls, v: int | None) -> int | None:
        if v is not None and not (1 <= v <= 65535):
            raise ValueError("n3fjp_port must be between 1 and 65535")
        return v

    @field_validator("colors")
    @classmethod
    def _check_colors(cls, v: dict | None) -> dict | None:
        if v is None:
            return v
        for mode, vars in v.items():
            if mode not in ("light", "dark"):
                raise ValueError("colors keys must be 'light' or 'dark'")
            if not isinstance(vars, dict):
                raise ValueError(f"colors.{mode} must be a mapping")
            for key, val in vars.items():
                if not isinstance(val, str) or not _HEX_RE.match(val):
                    raise ValueError(f"colors.{mode}.{key} must be a #rrggbb hex string")
        return v
```

- [ ] **Step 4: Apply provided fields in `post_config`**

In `src/openfieldday/app.py`, replace the body of `post_config` with this guarded version (keeps the live source re-point from the existing host/port feature):

```python
    @app.post("/api/config")
    async def post_config(update: ConfigUpdate) -> dict:
        cfg = state["config"]
        if update.power_multiplier is not None:
            cfg.power_multiplier = update.power_multiplier
        if update.bonuses is not None:
            cfg.bonuses = update.bonuses
        if update.colors is not None:
            cfg.colors = update.colors
        target_changed = False
        if update.n3fjp_host is not None and update.n3fjp_host != cfg.n3fjp_host:
            cfg.n3fjp_host = update.n3fjp_host
            target_changed = True
        if update.n3fjp_port is not None and update.n3fjp_port != cfg.n3fjp_port:
            cfg.n3fjp_port = update.n3fjp_port
            target_changed = True
        cfg.save(config_path)
        recompute()
        if start_source and target_changed:
            await stop_source_task()
            await start_source_task()
        return cfg.to_public_dict()
```

- [ ] **Step 5: Run the full app test suite to verify pass + no regressions**

Run: `.venv/bin/python -m pytest tests/test_app.py -q`
Expected: PASS — all tests pass, including the existing multiplier/host/port tests.

- [ ] **Step 6: Commit**

```bash
git add src/openfieldday/app.py tests/test_app.py
git commit -m "feat: accept and validate theme colors on POST /api/config" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Theme builder page

**Files:**
- Create: `src/openfieldday/static/builder.html`
- Create: `src/openfieldday/static/builder.js`
- Modify: `src/openfieldday/static/styles.css` (builder + preview styles)
- Modify: `src/openfieldday/static/settings.html` (link to the builder)

**Interfaces:**
- Consumes: `derivePalette` (global), `GET`/`POST /api/config` with `colors` (Task 4).

- [ ] **Step 1: Add the builder + preview styles to `styles.css`**

Append to `src/openfieldday/static/styles.css`:

```css
/* ---- Theme builder ---- */
.builder { display:flex; gap:1.5rem; padding:1.5rem; align-items:flex-start; }
.builder-controls { flex:0 0 340px; }
.builder-preview { flex:1 1 0; min-width:0; }
.tabs { display:flex; gap:0.5rem; margin-bottom:1rem; }
.tabs button { flex:1; padding:0.5rem; font:inherit; font-weight:700; cursor:pointer;
  background:var(--tile-bg); color:var(--fg); border:1px solid var(--line); border-radius:0.5rem; }
.tabs button.active { background:var(--accent); color:var(--on-accent); border-color:var(--accent); }
.builder-row { display:flex; align-items:center; gap:0.6rem; margin-bottom:0.7rem; }
.builder-row label { flex:1; }
.builder-row input[type="color"] { width:2.4rem; height:2.4rem; padding:0; cursor:pointer;
  border:1px solid var(--line); border-radius:0.4rem; background:none; }
.builder-row input[type="text"] { width:6.5rem; font:inherit; padding:0.35rem 0.5rem;
  background:var(--bg); color:var(--fg); border:1px solid var(--line); border-radius:0.4rem; }
.builder-actions { margin-top:1.2rem; display:flex; align-items:center; gap:0.8rem; }
.builder-actions button { padding:0.5rem 1.1rem; font:inherit; font-weight:700;
  cursor:pointer; border-radius:0.5rem; }
#save { color:var(--on-accent); background:var(--accent); border:none; }
#reset { color:var(--fg); background:var(--tile-bg); border:1px solid var(--line); }
#status { color:var(--good); font-weight:700; }

/* Preview pane colors come from inline --vars set by builder.js (the candidate
   palette), so it reflects edits live regardless of the page's own theme. */
.preview-pane { background:var(--bg); color:var(--fg);
  border:1px solid var(--line); border-radius:1rem; padding:1.25rem; }
.preview-header { display:flex; align-items:center; gap:0.6rem; flex-wrap:wrap;
  border-bottom:1px solid var(--line); padding-bottom:0.9rem; margin-bottom:1rem; }
.preview-title { color:var(--accent); font-size:1.3rem; margin-right:auto; }
.preview-pill { font-weight:700; padding:0.2rem 0.6rem; border-radius:0.4rem; font-size:0.9rem; }
.preview-pill.good { background:var(--good); color:var(--on-good); }
.preview-pill.bad { background:var(--bad); color:var(--on-bad); }
.preview-pill.accent { background:var(--accent); color:var(--on-accent); }
.preview-row { display:flex; gap:1rem; }
.preview-panel { flex:1; background:var(--panel); border-radius:0.8rem; padding:1.1rem; }
.preview-big { font-size:2.6rem; font-weight:800; color:var(--accent); line-height:1; }
.preview-label { text-transform:uppercase; letter-spacing:0.1em; opacity:0.7; margin-top:0.3rem; }
.preview-secs { display:flex; gap:0.5rem; flex-wrap:wrap; margin-bottom:0.9rem; }
.preview-sec { padding:0.35rem 0.55rem; border-radius:0.35rem; font-weight:700;
  background:var(--tile-bg); color:var(--dim); }
.preview-sec.worked { background:var(--good); color:var(--on-good); }
.preview-btn { padding:0.45rem 1rem; font:inherit; font-weight:700; border:none;
  border-radius:0.5rem; color:var(--on-accent); background:var(--accent); cursor:pointer; }
```

- [ ] **Step 2: Create `builder.html`**

Create `src/openfieldday/static/builder.html`:

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>OpenFieldDay Theme Builder</title>
  <link rel="stylesheet" href="/styles.css">
</head>
<body>
  <header><h1>Theme Builder</h1><a class="settings-link" href="/settings.html">← Settings</a></header>
  <main class="builder">
    <div class="builder-controls">
      <div class="tabs">
        <button data-mode="light" class="active" type="button">Light</button>
        <button data-mode="dark" type="button">Dark</button>
      </div>
      <div id="inputs"></div>
      <div class="builder-actions">
        <button id="save" type="button">Save</button>
        <button id="reset" type="button">Reset to default</button>
        <span id="status"></span>
      </div>
    </div>
    <div class="builder-preview">
      <div id="previewPane" class="preview-pane" data-theme="light">
        <div class="preview-header">
          <strong class="preview-title">OpenFieldDay</strong>
          <span class="preview-pill good">● Connected</span>
          <span class="preview-pill bad">⚠ Disconnected</span>
          <span class="preview-pill accent">● Contest Live</span>
        </div>
        <div class="preview-row">
          <div class="preview-panel">
            <div class="preview-big">1,234</div>
            <div class="preview-label">Score</div>
          </div>
          <div class="preview-panel">
            <div class="preview-secs">
              <span class="preview-sec worked">CT</span>
              <span class="preview-sec worked">EMA</span>
              <span class="preview-sec">NH</span>
              <span class="preview-sec">VT</span>
            </div>
            <button class="preview-btn" type="button">Save</button>
          </div>
        </div>
      </div>
    </div>
  </main>
  <script src="/colormath.js"></script>
  <script src="/theme.js"></script>
  <script src="/builder.js"></script>
</body>
</html>
```

- [ ] **Step 3: Create `builder.js`**

Create `src/openfieldday/static/builder.js`:

```js
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
```

- [ ] **Step 4: Link the builder from `settings.html`**

In `src/openfieldday/static/settings.html`, change the header to include a builder link before the Dashboard link:

```html
  <header><h1>Settings</h1><a class="settings-link" href="/builder.html">Theme builder</a><a class="settings-link" href="/">← Dashboard</a></header>
```

- [ ] **Step 5: Visually verify the builder (both tabs + live preview)**

Run from the repo root:

```bash
.venv/bin/python -c "from openfieldday.config import Config; Config().save('/tmp/ofd_t5.yaml')"
.venv/bin/python -c "
import uvicorn, threading, time, subprocess
from openfieldday.app import create_app
app = create_app(config_path='/tmp/ofd_t5.yaml', start_source=False)
s = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=8015, log_level='error'))
threading.Thread(target=s.run, daemon=True).start(); time.sleep(1.5)
base=['chromium-browser','--headless','--no-sandbox','--disable-gpu','--hide-scrollbars','--window-size=1100,760','--virtual-time-budget=2500']
subprocess.run(base+['--screenshot=/tmp/ofd_builder.png','http://127.0.0.1:8015/builder.html'], timeout=40)
s.should_exit=True; time.sleep(0.3)
" 2>/dev/null
```

Open `/tmp/ofd_builder.png`: confirm the Light tab shows 6 color rows and a preview pane with readable pills, score tile, worked/unworked section tiles, and an accent button. (Interactive tab-switch/edit is exercised in Task 6's RARA verification.)

- [ ] **Step 6: Commit**

```bash
git add src/openfieldday/static/builder.html src/openfieldday/static/builder.js src/openfieldday/static/styles.css src/openfieldday/static/settings.html
git commit -m "feat: in-app theme builder with live preview" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Ship the RARA palette + docs

**Files:**
- Modify: `config.yaml` (LOCAL ONLY — gitignored, not committed)
- Modify: `README.md`

**Interfaces:**
- Consumes: everything above.

- [ ] **Step 1: Apply the RARA base palette to the local `config.yaml`**

Edit `config.yaml` (read it first; preserve all existing keys like `n3fjp_host`, `logo_path`, etc.) so the `colors` key is exactly:

```yaml
colors:
  light:
    bg: "#F4F1E9"
    panel: "#E7E8E2"
    fg: "#1A1A1A"
    accent: "#0032CB"
    good: "#2E7D32"
    bad: "#D90000"
  dark:
    bg: "#0A1A3F"
    panel: "#11254F"
    fg: "#E7E8E2"
    accent: "#5A9CF2"
    good: "#43A047"
    bad: "#D90000"
```

- [ ] **Step 2: Verify the RARA dashboard in light and dark**

Run from the repo root (forces each mode via a localStorage helper, screenshots both):

```bash
HELPER=src/openfieldday/static/_ttest.html
.venv/bin/python -c "
import uvicorn, threading, time, subprocess
from openfieldday.app import create_app
app = create_app(config_path='config.yaml', start_source=False)
s = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=8016, log_level='error'))
threading.Thread(target=s.run, daemon=True).start(); time.sleep(1.5)
base=['chromium-browser','--headless','--no-sandbox','--disable-gpu','--hide-scrollbars','--window-size=1280,720']
# light mode (force via the theme switcher's localStorage key)
open('$HELPER','w').write('<script>localStorage.setItem(\"ofd-theme-mode\",\"light\");location.replace(\"/index.html\")</script>')
subprocess.run(base+['--virtual-time-budget=3500','--screenshot=/tmp/ofd_rara_light.png','http://127.0.0.1:8016/_ttest.html'], timeout=40)
open('$HELPER','w').write('<script>localStorage.setItem(\"ofd-theme-mode\",\"dark\");location.replace(\"/index.html\")</script>')
subprocess.run(base+['--virtual-time-budget=3500','--screenshot=/tmp/ofd_rara_dark.png','http://127.0.0.1:8016/_ttest.html'], timeout=40)
s.should_exit=True; time.sleep(0.3)
" 2>/dev/null
rm -f "$HELPER"
```

Open `/tmp/ofd_rara_light.png` and `/tmp/ofd_rara_dark.png`. Confirm: light = cream bg / ink text / cobalt accent / green worked tiles / red disconnected pill, all readable; dark = navy bg / bone text / sky-blue accent, all readable. If a `good` green clashes, adjust the hex in `config.yaml` and re-run.

- [ ] **Step 3: Update the README theme section**

In `README.md`, replace the body of the `### Theme` section's color-override guidance (the paragraph starting "To override palette colors" through the "Overridable keys" paragraph) with builder-first guidance:

```markdown
The easiest way to make a theme from your logo is the **Theme Builder** (Settings →
Theme builder, or `/builder.html`). Pick six colors per mode — background, panel,
text, accent, and the good/bad status colors — with a live preview, then Save. The
app derives borders, muted text, tile fill, and guaranteed-readable text-on-color
automatically, so any palette stays legible.

The builder writes the six base colors per mode into `config.yaml`:

```yaml
colors:
  light:
    bg: "#F4F1E9"      # Cream — page background
    panel: "#E7E8E2"   # Bone — tile background
    fg: "#1A1A1A"      # Ink — text
    accent: "#0032CB"  # Cobalt
    good: "#2E7D32"    # status: connected / worked
    bad: "#D90000"     # status: disconnected (Race Red)
  dark:
    bg: "#0A1A3F"      # Midnight
    panel: "#11254F"
    fg: "#E7E8E2"
    accent: "#5A9CF2"  # Sky Blue
    good: "#43A047"
    bad: "#D90000"
```

(The example above is the bundled RARA palette.) Advanced users can still pin any
derived variable — `panel`, `line`, `dim`, `tile-bg`, `on-accent`, `on-good`,
`on-bad` — by adding it alongside the six base colors; an explicit value wins over
the derived one.
```

- [ ] **Step 4: Run all tests as a final regression gate**

Run: `.venv/bin/python -m pytest -q && node --test src/openfieldday/static/colormath.test.js`
Expected: PASS — pytest all green; node `# pass 9`.

- [ ] **Step 5: Commit (README only; config.yaml stays local)**

```bash
git add README.md
git commit -m "docs: document the theme builder and RARA palette example" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review notes

- **Spec coverage:** Part 1a (on-colors) → Task 2; Part 1b (derived shades) → Task 1 `derivePalette` + Task 3 inject; Part 2 (`colormath.js`, UMD, tests) → Task 1; Part 3 (builder page) → Task 5; Part 4 (config + validation) → Task 4; Part 5 (RARA) → Task 6; testing section → Tasks 1/4/6.
- **Backward compat:** partial `colors` entries still inject raw (Task 3 `hasFullBase` branch), preserving the documented advanced override.
- **Type consistency:** `derivePalette`/`BASE_KEYS`/`BASE_FIELDS` keys are the same six (`bg,panel,fg,accent,good,bad`) across Tasks 1, 3, 5; the `colors` shape `{light,dark}` is consistent across Tasks 4, 5, 6.
