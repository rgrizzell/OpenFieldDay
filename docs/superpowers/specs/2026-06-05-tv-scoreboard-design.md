# OpenFieldDay TV Scoreboard — Design

**Date:** 2026-06-05
**Status:** Approved (brainstorming) — ready for implementation planning

## Summary

OpenFieldDay v1 is a **read-only big-screen scoreboard** for ARRL Field Day. It runs as
a single Python service on a Raspberry Pi connected to a TV, ingests the live log from
**N3FJP** over N3FJP's TCP API, computes Field Day stats and score, and renders a
glanceable dashboard. The same dashboard is viewable by anyone on the LAN (phones,
laptops) via a browser.

It does **not** log, edit, or export QSOs — N3FJP remains the system of record. This is
purely a display layer on top of N3FJP.

## Goals

- Show, updating live during the event:
  - Total QSOs and current score.
  - Rate (QSOs per hour).
  - Band × mode breakdown.
  - Per-operator / per-station leaderboard.
- Be readable across a room (TV is the primary target) and also openable on any LAN
  device's browser.
- Run reliably on a Raspberry Pi for the duration of Field Day.

## Non-goals (v1, YAGNI)

- Logging or editing QSOs (read-only).
- Cabrillo/ADIF export or contest submission.
- Contests other than ARRL Field Day.
- Persistent database / historical archive (state is in-memory, rebuilt from N3FJP on
  restart).
- Authentication / access control (assumes a trusted Field Day LAN).

## Context and key decisions

- **Operating positions run N3FJP**, which keeps contacts in its own database and only
  writes ADIF on a manual export. Therefore file/folder watching cannot provide live
  updates and was rejected as the v1 data source.
- **N3FJP's TCP API is the live data source.** N3FJP runs a TCP server (default port
  1100). It **automatically pushes an `ENTEREVENT` message whenever a contact is
  logged** (includes QSO count, call, band, mode, date/time), and supports
  `<CMD><LIST><INCLUDEALL></CMD>` to pull the full log with all fields on demand.
  Reference: <http://www.n3fjp.com/help/api.html>.
- **N3FJP already merges and de-dupes** across positions: in a networked Field Day
  setup, all positions sync into one master database. The dashboard connects to that one
  master API endpoint and consumes the already-merged, already-deduped log. We do **not**
  merge per-station files or cross-station dedup ourselves in v1.
- **Pluggable ingestion** so the "logger-agnostic" value isn't lost: a small internal
  `Source` interface decouples the scoring/display core from N3FJP. v1 ships only the
  N3FJP-API adapter; an ADIF-file-watch adapter (for fldigi, WSJT-X, etc.) can be added
  later without touching the core.
- **Stack: Python.** FastAPI web server, Server-Sent Events (SSE) for live push,
  Chart.js on the frontend. Lightweight on a Pi, strong ADIF/ham ecosystem, simple
  deploy.

## Architecture

```
N3FJP master (TCP API :1100)
        │  ENTEREVENT pushes + periodic LIST snapshot
        ▼
┌──────────────────────┐
│ Ingestion adapter    │  Source interface; N3FJPSource impl for v1
│                      │  → emits normalized QSO records
└─────────┬────────────┘
          ▼
┌──────────────────────┐
│ QSO store (in-memory)│  canonical list, rebuilt from LIST snapshots
└─────────┬────────────┘
          ▼
┌──────────────────────┐
│ Scoring/stats engine │  pure functions: score, rate, band×mode, per-op
└─────────┬────────────┘
          ▼
┌──────────────────────┐     ┌─────────────────────┐
│ Web server (FastAPI) │◀────│ Config (YAML file +  │
│  - GET /api/stats    │     │ web settings page)   │
│  - GET /events (SSE) │     │ power class, bonuses │
│  - serves dashboard  │     └─────────────────────┘
└─────────┬────────────┘
          ▼
  Browsers: TV kiosk @ localhost + LAN viewers @ Pi-IP
  4 panels (total/score · rate · band×mode · operator leaderboard), Chart.js
```

### Components (each with one job)

1. **`Source` interface + `N3FJPSource`**
   Owns all N3FJP-protocol details. On connect, backfills the full log via
   `<CMD><LIST><INCLUDEALL></CMD>`; then listens for `ENTEREVENT` pushes and re-polls
   `LIST` every ~10s to reconcile (the periodic snapshot is the source of truth;
   `ENTEREVENT` triggers an immediate refresh for liveliness). Emits **normalized QSO
   records**; nothing downstream knows N3FJP exists. Protocol detail: commands/responses
   are `<CMD>…</CMD>` framed, uppercase, terminated by CR+LF.

2. **QSO store (in-memory)**
   Holds the current canonical QSO list (a Field Day log is at most a few thousand
   records). Replaced wholesale from each `LIST` snapshot. No persistence; rebuilt from
   N3FJP on restart.

3. **Scoring/stats engine**
   *Pure* functions: given QSOs + config, return a stats object (totals, score, rate,
   band×mode breakdown, per-operator counts). No I/O — trivially unit-testable.

4. **Web server (FastAPI)**
   Serves the dashboard and settings pages. Exposes `GET /api/stats` (JSON snapshot) and
   `GET /events` (SSE stream that pushes a fresh stats object whenever data or config
   changes). SSE chosen over WebSocket because updates are one-way (server→browser) and
   SSE auto-reconnects.

5. **Config**
   A YAML file holding power class, the set of applicable bonuses, and N3FJP host/port.
   Editable via a small web settings page. A config change recomputes stats and pushes an
   update.

6. **Frontend**
   One dashboard page styled for across-the-room viewing with four panels
   (total/score, rate, band×mode, operator leaderboard), using Chart.js for the band/mode
   and rate visuals, with an auto-reconnecting SSE client. Plus a settings page for power
   class and bonuses. Detailed visual design is deferred to implementation.

### Data flow

N3FJP → adapter → QSO store → scoring engine → SSE push → browsers render. Config edits
flow into the engine and trigger the same push. On restart, state rebuilds from N3FJP's
`LIST` (no database).

### Deployment

Runs as a service on the Pi. Chromium runs full-screen (kiosk) pointed at `localhost`.
LAN viewers open the Pi's IP in any browser.

## Field Day scoring rules (baked into the engine)

- **Mode grouping is the unit, not raw `MODE`.** Each QSO's mode maps to one of three
  groups:
  - **Phone** — SSB / USB / LSB / FM / AM
  - **CW** — CW
  - **Digital** — RTTY / FT8 / PSK / other data modes
  Unrecognized modes default to **Phone** and are flagged in logs.
- **QSO points:** Phone = 1, CW = 2, Digital = 2.
- **Dupes:** N3FJP's master log is already deduped (one QSO per call per band per
  mode-group); treated as authoritative — no re-dedup in v1. If a file source is added
  later, that adapter will dedup on `call + band + mode-group`, crediting the **earliest**
  QSO (this also governs leaderboard credit).
- **Score:** `total = (Σ QSO points) × power_multiplier + Σ bonus_points`.
- **Power multiplier** (from config, station-wide class):
  - 5× — ≤5 W QRP on a non-commercial power source
  - 2× — ≤150 W
  - 1× — >150 W
- **Bonus points** (from config): a checklist on the settings page (e.g. emergency power,
  public location, media publicity, GOTA, satellite QSO, etc.), each with its point value,
  summed into the total.
- **Rate:** QSOs/hour over a trailing window (e.g. last 10 min projected hourly, plus last
  60 min), computed from `TIME_ON` / `QSO_DATE`.

**Rule verification:** exact point values, power tiers, and the bonus catalog will be
verified against the **current ARRL Field Day rules** at implementation time rather than
hardcoded from memory, since rules change year to year. Encode them as data/config, not
scattered constants.

## Error handling

- **N3FJP unreachable / connection drops:** dashboard shows a clear
  "⚠ Disconnected — reconnecting" banner, keeps last-known stats on screen, and the
  adapter retries with backoff. No blank screen mid-event.
- **Malformed or missing fields:** normalize or skip the bad record; never let one record
  kill the feed.
- **Empty log / pre-contest:** all panels render zeros cleanly.

## Testing

- **Scoring engine:** pure unit tests over crafted QSO sets — mode grouping, multiplier
  tiers, bonus sums, mixed logs.
- **Ingestion adapter:** parse **captured real `ENTEREVENT` and `LIST INCLUDEALL`
  payloads** as fixtures; exercise connect → backfill → live against a fake N3FJP TCP
  server.
- **Web layer:** JSON-shape tests on `/api/stats`; a basic SSE smoke test.

## Open items to resolve during implementation

- **Capture a real `LIST INCLUDEALL` dump** from the group's N3FJP. It seeds the parser
  fixtures and confirms which fields are present.
- **Operator field availability:** the per-operator leaderboard depends on N3FJP exposing
  an operator field via the API. `ENTEREVENT` may not include it, so the leaderboard is
  driven by the periodic `LIST INCLUDEALL` snapshot. Confirm `OPERATOR` (or equivalent)
  appears in the dump; if absent, revisit how per-operator credit is sourced.
- **Confirm current ARRL Field Day rule values** (QSO points, power tiers, bonus catalog).
