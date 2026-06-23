# Logo-friendly theming + Theme Builder — Design

Date: 2026-06-22

## Goal

Make it easy for a non-expert to create a dashboard theme from a logo's colors,
and ship the RARA brand palette as the worked example. Today a theme requires
hand-authoring 9 CSS variables per mode (18 values), several of which are fiddly
derived shades, and 5 places in the CSS pair a theme color with a **hardcoded**
text color — so an arbitrary palette can produce unreadable text.

## Decisions (from brainstorming)

- **Authoring:** an in-app **theme builder** page with live preview, saved to config.
- **Light/dark:** author both modes **explicitly** (tabs), full control.
- **Inputs per mode:** 6 colors — background, panel/tiles, text, accent, good, bad.
  `line`, `dim`, `tile-bg`, and all text-on-color values are **derived**.
- **`good` for RARA:** a **harmonized green** (the palette has no green, and `good`
  is semantically "connected / worked / Phone"), not a brand color forced into a
  success role.

## Part 1 — Make the theme system palette-proof

This is the enabler; the builder depends on it.

### 1a. Derived "on-colors"

Add three CSS variables — `--on-accent`, `--on-good`, `--on-bad` — and replace the
hardcoded contrast colors:

| Current (styles.css) | Becomes |
| --- | --- |
| `#conn.connected { … color:#003 }` | `color:var(--on-good)` |
| `#contest.active { … color:#003 }` | `color:var(--on-good)` |
| `.sec.worked { … color:#003 }` | `color:var(--on-good)` |
| `#conn.disconnected { … color:#fdf6e3 }` | `color:var(--on-bad)` |
| `button[type=submit] { color:#fff … }` | `color:var(--on-accent)` |

The on-color is **computed for contrast**: pick near-white (`#ffffff`) or near-black
(`#0d0d0d`), whichever has the higher WCAG contrast ratio against the background
color. Threshold falls out of the contrast comparison, so it is correct for light
*and* dark backgrounds.

The built-in Solarized light/dark palettes define `--on-accent/-good/-bad`
explicitly with **today's exact values** (`#003`, `#fdf6e3`, `#fff`) so their
appearance is unchanged.

### 1b. Auto-derived shades

`line`, `dim`, `tile-bg` are computed from `fg`/`bg` using the ratios Solarized
already uses (verified against the current values):

- `line`    = `fg` at alpha **0.20**
- `tile-bg` = `fg` at alpha **0.10**
- `dim`     = `mix(fg, bg, 0.40)`  (40% toward background)

Built-in palettes keep their literal current values in CSS; derivation is only used
for builder-authored themes.

## Part 2 — Color math module (`colormath.js`)

The color math is extracted into its own file, `colormath.js`, holding only **pure
functions** (no DOM/browser dependencies) — the single source of truth used by both
the live dashboard and the builder preview (no backend round-trips, instant
preview):

- `parseHex(hex) -> {r,g,b}`
- `relativeLuminance({r,g,b}) -> 0..1`  (WCAG)
- `contrastRatio(a, b) -> number`
- `onColor(bg) -> "#ffffff" | "#0d0d0d"`  (max contrast)
- `withAlpha(hex, a) -> "rgba(...)"`
- `mix(hexA, hexB, t) -> "#rrggbb"`
- `derivePalette(base) -> {bg, panel, fg, accent, good, bad, line, dim, tile-bg,
  on-accent, on-good, on-bad}` where `base` is the 6 authored colors.

`derivePalette` merges any explicitly-provided key over the derived value, so an
advanced user can still pin a raw variable in `config.yaml`.

**Dual-environment export.** `colormath.js` ends with a 3-line UMD-style footer so
the same file works both as a classic browser script (functions on the global
scope, consistent with the existing `theme.js`/`app.js` no-build architecture) and
as a Node module (`module.exports`) for tests:

```js
if (typeof module !== "undefined" && module.exports) {
  module.exports = { parseHex, relativeLuminance, contrastRatio, onColor,
                     withAlpha, mix, derivePalette };
}
```

The browser loads `<script src="/colormath.js">` before `theme.js`; the builder and
dashboard call `derivePalette` from the global scope.

`injectThemeColors(colors)` (in `theme.js`) changes to: for each mode,
`derivePalette(base)` then inject the full set as `[data-theme=mode]{…}`. A mode
entry already containing the full set still works (extra keys pass through).

## Part 3 — Theme builder page

New static page `builder.html` + `builder.js`, reachable from a "Theme builder →"
link on the Settings page (and a link back). Uses the shared `theme.js`.

- **Light / Dark tabs.** Each: 6 rows of `label + <input type="color"> + hex text`
  (the two inputs kept in sync). Good/bad pre-filled with the harmonized
  green / Race Red.
- **Live preview panel** (right side), rendered with the derived variables under a
  scoped `data-theme`, showing one of each element that exercises every variable:
  header bar with **connected / disconnected / contest** pills and the theme/cog
  icon buttons, a **score tile** (accent number on panel), **worked + unworked
  section tiles**, an **accent button**, and **Phone / CW / Digital** bars
  (good / bad / accent). Updates on every input change.
- **Save** → POST the 6 base colors per mode to the config API. **Reset** → clear
  the override (revert to built-in Solarized).
- On load: read current config; if a custom palette exists, populate the 6 inputs
  per mode from it; otherwise seed inputs from the active built-in palette.

## Part 4 — Config + backend

- The builder writes the **6 base colors per mode** into `colors: {light:{…},
  dark:{…}}` (the existing field). The dashboard derives the rest at inject time,
  so no schema migration is needed and raw overrides still layer on top.
- `POST /api/config` accepts an optional `colors` object: `{light?:{…}, dark?:{…}}`
  with string hex values. Backend **validates** each value matches
  `^#[0-9a-fA-F]{6}$` (rejects with 422 otherwise) and persists via `Config.save`.
- `Config.theme_color_overrides()` / `to_public_dict()` already surface `colors`
  as `{light, dark}`; unchanged.

## Part 5 — RARA palette (shipped example)

Applied to `config.yaml` as the 6 base colors per mode (final greens tuned in the
builder against the preview):

| role | Light | Dark |
| --- | --- | --- |
| background | Cream `#F4F1E9` | Midnight `#0A1A3F` |
| panel | Bone `#E7E8E2` | deep navy `#11254F` |
| text | Ink `#1A1A1A` | Bone `#E7E8E2` |
| accent | Cobalt `#0032CB` | Sky Blue `#5A9CF2` |
| good | harmonized green `#2E7D32` | green `#43A047` |
| bad | Race Red `#D90000` | Race Red `#D90000` |

## Testing / verification

- **Pytest** (`pytest`): `POST /api/config` accepts and persists valid `colors`;
  rejects a bad hex with 422; omitting `colors` leaves existing values untouched.
- **Node tests** (`node --test`): a `colormath.test.js` using the built-in
  `node:test` + `node:assert` runner (no npm dependencies) covering:
  - `parseHex` handles `#rgb`/`#rrggbb` and rejects malformed input;
  - `onColor` returns the higher-contrast choice and meets WCAG contrast ≥ 4.5
    against its background, including a light accent (e.g. Flash `#F2B705`) where
    today's hardcoded `#fff` would fail;
  - derived `line`/`dim`/`tile-bg` reproduce the Solarized values within rounding;
  - `derivePalette` returns all 12 keys and honors explicit overrides.
- A minimal `package.json` (`"test": "node --test src/openfieldday/static"`, no
  dependencies) wires up the runner. Node is a **dev/test-only** tool — it is not a
  runtime dependency on the Pi (the app stays static-file/Node-free in production).
- **Visual:** headless screenshots of the builder (both tabs) and the dashboard
  under the RARA light + dark themes, confirming readable text on every element.

### New / changed files

- `src/openfieldday/static/colormath.js` — new, pure color math (UMD footer).
- `src/openfieldday/static/colormath.test.js` — new, `node --test`.
- `package.json` — new, minimal, dev-only test script.
- `src/openfieldday/static/builder.html` / `builder.js` — new, the builder page.
- `src/openfieldday/static/theme.js` — `injectThemeColors` derives via `colormath`.
- `src/openfieldday/static/styles.css` — `--on-*` vars; builder styles.
- `src/openfieldday/static/settings.html` — link to the builder.
- `src/openfieldday/app.py` — `colors` validation on `POST /api/config`.
- `config.yaml` — RARA base palette (light + dark).

## Out of scope

- Automated color extraction from an image file (rejected: image libs on the Pi,
  unpredictable role mapping).
- Per-element color overrides beyond the 6 base + advanced raw escape hatch.
- Changing the theme **mode** machinery (auto/system/light/dark) — unchanged.
