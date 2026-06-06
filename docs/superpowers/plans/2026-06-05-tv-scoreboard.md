# OpenFieldDay TV Scoreboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a read-only Raspberry Pi web dashboard that shows live ARRL Field Day stats (total/score, rate, band×mode, per-operator) by consuming N3FJP's TCP API.

**Architecture:** A single Python (FastAPI) service. An async `Source` connects to N3FJP's TCP API, pulls the full log via `<CMD><LIST><INCLUDEALL></CMD>`, and re-pulls whenever N3FJP pushes an `ENTEREVENT` or every 10s. Parsed QSOs land in an in-memory store; a pure scoring engine turns store + config into a `Stats` object that is pushed to browsers over Server-Sent Events. A small settings page sets power class and bonuses (which can't come from the log).

**Tech Stack:** Python 3.11+, FastAPI, Uvicorn, asyncio TCP client, PyYAML, plain HTML/JS + vendored Chart.js, pytest + pytest-asyncio.

---

## File Structure

```
pyproject.toml                         # project metadata, deps, pytest config
src/openfieldday/
  __init__.py
  __main__.py                          # `openfieldday` entry point (uvicorn runner)
  models.py                            # QSO, Stats, BandModeCount, OperatorCount
  modes.py                             # mode -> mode-group + QSO points
  scoring.py                           # pure compute_stats(qsos, config, connected, now)
  config.py                            # Config dataclass, BONUS_CATALOG, load/save YAML
  store.py                             # QSOStore: in-memory list + change listeners
  events.py                            # Broadcaster: SSE pub/sub
  sources/
    __init__.py
    base.py                            # Source abstract base class
    n3fjp_parser.py                    # pure parsing of N3FJP <CMD> payloads
    n3fjp.py                           # N3FJPSource: async TCP client + reconnect
  app.py                              # create_app(): wiring + routes
  static/
    index.html                         # dashboard
    settings.html                      # power class + bonuses form
    app.js                             # SSE client + rendering + Chart.js
    settings.js                        # settings form logic
    styles.css                         # big-screen styling
    vendor/chart.min.js                # vendored Chart.js (offline; field site has no internet)
tests/
  __init__.py
  conftest.py
  test_modes.py
  test_scoring.py
  test_config.py
  test_store.py
  test_events.py
  test_n3fjp_parser.py
  test_n3fjp_source.py
  test_app.py
  fixtures/
    list_includeall.txt                # captured N3FJP LIST response (placeholder until real capture)
    enterevent.txt                     # captured ENTEREVENT push
```

**Responsibilities:** `models` = data shapes only. `modes`/`scoring`/`config`/`n3fjp_parser` = pure, no I/O, heavily unit-tested. `store`/`events` = in-memory state + fan-out. `n3fjp` = the only networking code. `app` = wiring + HTTP. Frontend = presentation only.

---

## Task 0: Project scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `src/openfieldday/__init__.py` (empty)
- Create: `tests/__init__.py` (empty)
- Create: `tests/test_smoke.py`

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "openfieldday"
version = "0.1.0"
description = "Read-only ARRL Field Day TV scoreboard fed by the N3FJP TCP API"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.110",
    "uvicorn[standard]>=0.29",
    "pyyaml>=6",
]

[project.optional-dependencies]
dev = ["pytest>=8", "pytest-asyncio>=0.23", "httpx>=0.27"]

[project.scripts]
openfieldday = "openfieldday.__main__:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
pythonpath = ["src"]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: Create empty `src/openfieldday/__init__.py` and `tests/__init__.py`**

Both files are empty.

- [ ] **Step 3: Write a smoke test** in `tests/test_smoke.py`

```python
def test_python_imports_package():
    import openfieldday  # noqa: F401
```

- [ ] **Step 4: Create venv and install**

Run:
```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
```
Expected: installs FastAPI, Uvicorn, PyYAML, pytest, etc. with no errors.

- [ ] **Step 5: Run the smoke test**

Run: `.venv/bin/pytest tests/test_smoke.py -v`
Expected: PASS.

- [ ] **Step 6: Add `.gitignore` and commit**

Create `.gitignore`:
```
.venv/
__pycache__/
*.pyc
config.yaml
```

```bash
git add pyproject.toml .gitignore src/openfieldday/__init__.py tests/__init__.py tests/test_smoke.py
git commit -m "chore: scaffold openfieldday package and test harness"
```

---

## Task 1: Data models

**Files:**
- Create: `src/openfieldday/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write the failing test** in `tests/test_models.py`

```python
from datetime import datetime, timezone
from openfieldday.models import QSO, Stats, BandModeCount, OperatorCount


def test_qso_has_required_and_optional_fields():
    q = QSO(call="W1AW", band="20", mode="SSB")
    assert q.call == "W1AW"
    assert q.band == "20"
    assert q.mode == "SSB"
    assert q.operator is None
    assert q.timestamp is None


def test_qso_accepts_operator_and_timestamp():
    ts = datetime(2026, 6, 27, 18, 0, tzinfo=timezone.utc)
    q = QSO(call="K1ABC", band="40", mode="CW", operator="AB1CD", timestamp=ts)
    assert q.operator == "AB1CD"
    assert q.timestamp == ts


def test_stats_is_constructible():
    s = Stats(
        total_qsos=1, qso_points=2, power_multiplier=2, bonus_points=100,
        score=104, rate_10min=6.0, rate_60min=1.0,
        band_mode=[BandModeCount(band="20", mode_group="Phone", count=1)],
        by_operator=[OperatorCount(operator="AB1CD", count=1)],
        connected=True,
    )
    assert s.score == 104
    assert s.band_mode[0].count == 1
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/pytest tests/test_models.py -v`
Expected: FAIL (`ModuleNotFoundError: openfieldday.models`).

- [ ] **Step 3: Implement** `src/openfieldday/models.py`

```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class QSO:
    call: str
    band: str
    mode: str
    operator: str | None = None
    timestamp: datetime | None = None


@dataclass(frozen=True)
class BandModeCount:
    band: str
    mode_group: str
    count: int


@dataclass(frozen=True)
class OperatorCount:
    operator: str
    count: int


@dataclass(frozen=True)
class Stats:
    total_qsos: int
    qso_points: int
    power_multiplier: int
    bonus_points: int
    score: int
    rate_10min: float
    rate_60min: float
    band_mode: list[BandModeCount] = field(default_factory=list)
    by_operator: list[OperatorCount] = field(default_factory=list)
    connected: bool = False
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/pytest tests/test_models.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/openfieldday/models.py tests/test_models.py
git commit -m "feat: add QSO and Stats data models"
```

---

## Task 2: Mode grouping and QSO points

**Files:**
- Create: `src/openfieldday/modes.py`
- Test: `tests/test_modes.py`

- [ ] **Step 1: Write the failing test** in `tests/test_modes.py`

```python
import pytest
from openfieldday.modes import mode_group, qso_points


@pytest.mark.parametrize("mode,group", [
    ("CW", "CW"),
    ("SSB", "Phone"), ("USB", "Phone"), ("LSB", "Phone"),
    ("FM", "Phone"), ("AM", "Phone"),
    ("RTTY", "Digital"), ("FT8", "Digital"), ("FT4", "Digital"),
    ("PSK31", "Digital"), ("ft8", "Digital"),
])
def test_mode_group_known(mode, group):
    assert mode_group(mode) == group


def test_unknown_mode_defaults_to_phone():
    assert mode_group("BANANA") == "Phone"


@pytest.mark.parametrize("mode,points", [
    ("SSB", 1), ("FM", 1), ("CW", 2), ("FT8", 2), ("RTTY", 2),
])
def test_qso_points(mode, points):
    assert qso_points(mode) == points
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/pytest tests/test_modes.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement** `src/openfieldday/modes.py`

```python
from __future__ import annotations

import logging

log = logging.getLogger(__name__)

CW_MODES = {"CW"}
PHONE_MODES = {"SSB", "USB", "LSB", "FM", "AM", "PHONE", "DV", "FT8PHONE"}
DIGITAL_MODES = {
    "RTTY", "FT8", "FT4", "PSK", "PSK31", "PSK63", "JT65", "JT9",
    "MFSK", "JS8", "OLIVIA", "DIGITAL", "DATA", "DIGITALVOICE", "MSK144",
}


def mode_group(mode: str) -> str:
    """Map a raw ADIF/N3FJP mode to one of CW / Phone / Digital.

    Per the design, unrecognized modes default to Phone (and are logged).
    """
    m = (mode or "").strip().upper()
    if m in CW_MODES:
        return "CW"
    if m in DIGITAL_MODES:
        return "Digital"
    if m in PHONE_MODES:
        return "Phone"
    log.warning("Unrecognized mode %r; defaulting to Phone", mode)
    return "Phone"


def qso_points(mode: str) -> int:
    """1 point for Phone, 2 points for CW and Digital."""
    return 1 if mode_group(mode) == "Phone" else 2
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/pytest tests/test_modes.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/openfieldday/modes.py tests/test_modes.py
git commit -m "feat: add mode grouping and QSO point rules"
```

---

## Task 3: Config (power class + bonuses) with YAML persistence

**Files:**
- Create: `src/openfieldday/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test** in `tests/test_config.py`

```python
from openfieldday.config import Config, BONUS_CATALOG


def test_defaults():
    c = Config()
    assert c.n3fjp_host == "127.0.0.1"
    assert c.n3fjp_port == 1100
    assert c.power_multiplier == 2
    assert c.bonuses == {}
    assert c.bonus_points == 0


def test_bonus_points_sums_selected():
    c = Config(bonuses={"Emergency power": 100, "Public location": 100})
    assert c.bonus_points == 200


def test_bonus_catalog_is_nonempty_mapping():
    assert isinstance(BONUS_CATALOG, dict)
    assert "Emergency power" in BONUS_CATALOG
    assert all(isinstance(v, int) for v in BONUS_CATALOG.values())


def test_save_and_load_roundtrip(tmp_path):
    path = tmp_path / "config.yaml"
    original = Config(
        n3fjp_host="192.168.1.50", n3fjp_port=1100,
        power_multiplier=5, bonuses={"Emergency power": 100},
    )
    original.save(path)
    loaded = Config.load(path)
    assert loaded == original
    assert loaded.bonus_points == 100


def test_load_missing_file_returns_defaults(tmp_path):
    loaded = Config.load(tmp_path / "does_not_exist.yaml")
    assert loaded == Config()
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/pytest tests/test_config.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement** `src/openfieldday/config.py`

```python
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path

import yaml

# Point values to VERIFY against the current ARRL Field Day rules at implementation
# time. Stored as data so they are easy to update; the settings page renders a
# checkbox per entry.
BONUS_CATALOG: dict[str, int] = {
    "Emergency power": 100,
    "Public location": 100,
    "Public information table": 100,
    "Message to ARRL SM/SEC": 100,
    "Copy W1AW Field Day message": 100,
    "Media publicity": 100,
    "Satellite QSO": 100,
    "GOTA bonus (educational)": 100,
    "Web submission": 50,
    "Youth participation": 20,
    "Social media": 100,
    "Educational activity": 100,
}

# Allowed Field Day power multipliers. VERIFY tiers/values against current rules.
POWER_MULTIPLIERS = {1, 2, 5}


@dataclass
class Config:
    n3fjp_host: str = "127.0.0.1"
    n3fjp_port: int = 1100
    power_multiplier: int = 2
    bonuses: dict[str, int] = field(default_factory=dict)

    @property
    def bonus_points(self) -> int:
        return sum(self.bonuses.values())

    def save(self, path: str | Path) -> None:
        data = {
            "n3fjp_host": self.n3fjp_host,
            "n3fjp_port": self.n3fjp_port,
            "power_multiplier": self.power_multiplier,
            "bonuses": self.bonuses,
        }
        Path(path).write_text(yaml.safe_dump(data, sort_keys=True))

    @classmethod
    def load(cls, path: str | Path) -> "Config":
        p = Path(path)
        if not p.exists():
            return cls()
        data = yaml.safe_load(p.read_text()) or {}
        return cls(
            n3fjp_host=data.get("n3fjp_host", "127.0.0.1"),
            n3fjp_port=int(data.get("n3fjp_port", 1100)),
            power_multiplier=int(data.get("power_multiplier", 2)),
            bonuses=dict(data.get("bonuses", {})),
        )

    def to_public_dict(self) -> dict:
        """Shape consumed by the settings page."""
        d = asdict(self)
        d["bonus_points"] = self.bonus_points
        return d
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/pytest tests/test_config.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/openfieldday/config.py tests/test_config.py
git commit -m "feat: add Config with bonus catalog and YAML persistence"
```

---

## Task 4: Scoring / stats engine

**Files:**
- Create: `src/openfieldday/scoring.py`
- Test: `tests/test_scoring.py`

- [ ] **Step 1: Write the failing test** in `tests/test_scoring.py`

```python
from datetime import datetime, timedelta, timezone
from openfieldday.models import QSO
from openfieldday.config import Config
from openfieldday.scoring import compute_stats

NOW = datetime(2026, 6, 27, 20, 0, tzinfo=timezone.utc)


def q(call, band, mode, operator=None, minutes_ago=None):
    ts = None if minutes_ago is None else NOW - timedelta(minutes=minutes_ago)
    return QSO(call=call, band=band, mode=mode, operator=operator, timestamp=ts)


def test_empty_log_is_all_zero():
    s = compute_stats([], Config(), connected=True, now=NOW)
    assert s.total_qsos == 0
    assert s.qso_points == 0
    assert s.score == 0
    assert s.band_mode == []
    assert s.by_operator == []
    assert s.connected is True


def test_points_and_score_with_multiplier_and_bonus():
    qsos = [q("W1AW", "20", "SSB"), q("K1ABC", "40", "CW")]  # 1 + 2 = 3 points
    cfg = Config(power_multiplier=2, bonuses={"Emergency power": 100})
    s = compute_stats(qsos, cfg, connected=True, now=NOW)
    assert s.qso_points == 3
    assert s.power_multiplier == 2
    assert s.bonus_points == 100
    assert s.score == 3 * 2 + 100  # 106


def test_band_mode_breakdown_groups_modes():
    qsos = [q("A", "20", "SSB"), q("B", "20", "FM"), q("C", "20", "CW")]
    s = compute_stats(qsos, Config(), connected=True, now=NOW)
    counts = {(b.band, b.mode_group): b.count for b in s.band_mode}
    assert counts[("20", "Phone")] == 2   # SSB + FM
    assert counts[("20", "CW")] == 1


def test_by_operator_counts_and_unknown_bucket():
    qsos = [q("A", "20", "SSB", operator="AB1CD"),
            q("B", "20", "SSB", operator="AB1CD"),
            q("C", "20", "SSB", operator=None)]
    s = compute_stats(qsos, Config(), connected=True, now=NOW)
    counts = {o.operator: o.count for o in s.by_operator}
    assert counts["AB1CD"] == 2
    assert counts["Unknown"] == 1
    # sorted descending by count
    assert s.by_operator[0].operator == "AB1CD"


def test_rate_windows():
    qsos = [
        q("A", "20", "SSB", minutes_ago=2),
        q("B", "20", "SSB", minutes_ago=5),     # 2 within last 10 min
        q("C", "20", "SSB", minutes_ago=30),    # within last 60 min only
        q("D", "20", "SSB", minutes_ago=90),    # outside both windows
    ]
    s = compute_stats(qsos, Config(), connected=True, now=NOW)
    assert s.rate_10min == 12.0   # 2 in 10 min * 6
    assert s.rate_60min == 3.0    # 3 in last 60 min
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/pytest tests/test_scoring.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement** `src/openfieldday/scoring.py`

```python
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone

from .models import QSO, Stats, BandModeCount, OperatorCount
from .modes import mode_group, qso_points
from .config import Config


def compute_stats(
    qsos: list[QSO],
    config: Config,
    connected: bool,
    now: datetime | None = None,
) -> Stats:
    now = now or datetime.now(timezone.utc)

    total_points = sum(qso_points(q.mode) for q in qsos)
    bonus = config.bonus_points
    score = total_points * config.power_multiplier + bonus

    band_mode_counter: Counter[tuple[str, str]] = Counter(
        (q.band, mode_group(q.mode)) for q in qsos
    )
    band_mode = [
        BandModeCount(band=band, mode_group=group, count=count)
        for (band, group), count in sorted(band_mode_counter.items())
    ]

    op_counter: Counter[str] = Counter(
        (q.operator or "Unknown") for q in qsos
    )
    by_operator = [
        OperatorCount(operator=op, count=count)
        for op, count in sorted(op_counter.items(), key=lambda kv: (-kv[1], kv[0]))
    ]

    ten_min_ago = now - timedelta(minutes=10)
    sixty_min_ago = now - timedelta(minutes=60)
    in_last_10 = sum(1 for q in qsos if q.timestamp and q.timestamp >= ten_min_ago)
    in_last_60 = sum(1 for q in qsos if q.timestamp and q.timestamp >= sixty_min_ago)

    return Stats(
        total_qsos=len(qsos),
        qso_points=total_points,
        power_multiplier=config.power_multiplier,
        bonus_points=bonus,
        score=score,
        rate_10min=float(in_last_10 * 6),
        rate_60min=float(in_last_60),
        band_mode=band_mode,
        by_operator=by_operator,
        connected=connected,
    )
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/pytest tests/test_scoring.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/openfieldday/scoring.py tests/test_scoring.py
git commit -m "feat: add pure scoring/stats engine"
```

---

## Task 5: In-memory QSO store

**Files:**
- Create: `src/openfieldday/store.py`
- Test: `tests/test_store.py`

- [ ] **Step 1: Write the failing test** in `tests/test_store.py`

```python
from openfieldday.models import QSO
from openfieldday.store import QSOStore


def test_starts_empty_and_disconnected():
    s = QSOStore()
    assert s.qsos == []
    assert s.connected is False


def test_replace_sets_qsos_and_notifies():
    s = QSOStore()
    calls = []
    s.on_change(lambda: calls.append(len(s.qsos)))
    s.replace([QSO(call="W1AW", band="20", mode="SSB")])
    assert len(s.qsos) == 1
    assert calls == [1]


def test_set_connected_only_notifies_on_change():
    s = QSOStore()
    calls = []
    s.on_change(lambda: calls.append(s.connected))
    s.set_connected(True)
    s.set_connected(True)   # no change, no extra notify
    s.set_connected(False)
    assert calls == [True, False]


def test_qsos_returns_copy():
    s = QSOStore()
    s.replace([QSO(call="A", band="20", mode="CW")])
    got = s.qsos
    got.clear()
    assert len(s.qsos) == 1  # internal list unaffected
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/pytest tests/test_store.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement** `src/openfieldday/store.py`

```python
from __future__ import annotations

from typing import Callable

from .models import QSO


class QSOStore:
    """Holds the current canonical QSO list and connection state in memory.

    The N3FJP LIST response is authoritative, so updates arrive via replace().
    Listeners are notified synchronously on any change.
    """

    def __init__(self) -> None:
        self._qsos: list[QSO] = []
        self._connected: bool = False
        self._listeners: list[Callable[[], None]] = []

    def on_change(self, fn: Callable[[], None]) -> None:
        self._listeners.append(fn)

    def _notify(self) -> None:
        for fn in self._listeners:
            fn()

    @property
    def qsos(self) -> list[QSO]:
        return list(self._qsos)

    @property
    def connected(self) -> bool:
        return self._connected

    def replace(self, qsos: list[QSO]) -> None:
        self._qsos = list(qsos)
        self._notify()

    def set_connected(self, value: bool) -> None:
        if self._connected != value:
            self._connected = value
            self._notify()
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/pytest tests/test_store.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/openfieldday/store.py tests/test_store.py
git commit -m "feat: add in-memory QSO store with change listeners"
```

---

## Task 6: SSE broadcaster

**Files:**
- Create: `src/openfieldday/events.py`
- Test: `tests/test_events.py`

- [ ] **Step 1: Write the failing test** in `tests/test_events.py`

```python
import asyncio
import pytest
from openfieldday.events import Broadcaster


async def test_subscriber_receives_published_message():
    b = Broadcaster()
    gen = b.subscribe()
    b.publish("hello")
    msg = await asyncio.wait_for(gen.__anext__(), timeout=1)
    assert msg == "hello"


async def test_new_subscriber_gets_latest_immediately():
    b = Broadcaster()
    b.publish("state-1")
    gen = b.subscribe()
    first = await asyncio.wait_for(gen.__anext__(), timeout=1)
    assert first == "state-1"


async def test_multiple_subscribers_all_receive():
    b = Broadcaster()
    g1, g2 = b.subscribe(), b.subscribe()
    b.publish("x")
    a = await asyncio.wait_for(g1.__anext__(), timeout=1)
    c = await asyncio.wait_for(g2.__anext__(), timeout=1)
    assert a == c == "x"
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/pytest tests/test_events.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement** `src/openfieldday/events.py`

```python
from __future__ import annotations

import asyncio
from typing import AsyncIterator


class Broadcaster:
    """Fan-out of the latest stats JSON string to all connected SSE clients.

    publish() is synchronous (safe to call from store listeners). Each
    subscriber gets the latest snapshot immediately on connect, then live
    updates.
    """

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[str]] = set()
        self._latest: str | None = None

    def publish(self, data: str) -> None:
        self._latest = data
        for q in list(self._subscribers):
            q.put_nowait(data)

    async def subscribe(self) -> AsyncIterator[str]:
        q: asyncio.Queue[str] = asyncio.Queue()
        self._subscribers.add(q)
        try:
            if self._latest is not None:
                yield self._latest
            while True:
                yield await q.get()
        finally:
            self._subscribers.discard(q)
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/pytest tests/test_events.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/openfieldday/events.py tests/test_events.py
git commit -m "feat: add SSE broadcaster with latest-snapshot replay"
```

---

## Task 7: N3FJP payload parser (pure)

**Files:**
- Create: `src/openfieldday/sources/__init__.py` (empty)
- Create: `src/openfieldday/sources/n3fjp_parser.py`
- Create: `tests/fixtures/list_includeall.txt`
- Test: `tests/test_n3fjp_parser.py`

> **VERIFY BEFORE RELYING ON THIS:** The exact LIST record framing is documented loosely. Capture a real `<CMD><LIST><INCLUDEALL></CMD>` response from the group's N3FJP and replace the fixture below; adjust `RECORD_TAG`/field names if the capture differs. This task isolates that risk to one module.

- [ ] **Step 1: Create the fixture** `tests/fixtures/list_includeall.txt`

(Placeholder approximating the documented `<CMD>…</CMD>` format. Replace with a real capture.)

```
<CMD><LISTRECORD><CALL>W1AW</CALL><BAND>20</BAND><MODE>SSB</MODE><OPERATOR>AB1CD</OPERATOR><DATE>2026/06/27</DATE><TIMEON>1802</TIMEON></LISTRECORD><LISTRECORD><CALL>K1ABC</CALL><BAND>40</BAND><MODE>CW</MODE><OPERATOR>EF2GH</OPERATOR><DATE>2026/06/27</DATE><TIMEON>1805</TIMEON></LISTRECORD></CMD>
```

- [ ] **Step 2: Write the failing test** in `tests/test_n3fjp_parser.py`

```python
from datetime import datetime, timezone
from pathlib import Path
from openfieldday.sources.n3fjp_parser import (
    parse_list, message_type, is_enterevent,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_list_extracts_qsos():
    payload = (FIXTURES / "list_includeall.txt").read_text()
    qsos = parse_list(payload)
    assert len(qsos) == 2
    first = qsos[0]
    assert first.call == "W1AW"
    assert first.band == "20"
    assert first.mode == "SSB"
    assert first.operator == "AB1CD"
    assert first.timestamp == datetime(2026, 6, 27, 18, 2, tzinfo=timezone.utc)


def test_parse_list_tolerates_missing_optional_fields():
    payload = "<CMD><LISTRECORD><CALL>N0CALL</CALL><BAND>15</BAND><MODE>FT8</MODE></LISTRECORD></CMD>"
    qsos = parse_list(payload)
    assert len(qsos) == 1
    assert qsos[0].operator is None
    assert qsos[0].timestamp is None


def test_parse_list_empty_returns_empty():
    assert parse_list("<CMD></CMD>") == []


def test_message_type_and_is_enterevent():
    assert is_enterevent("<CMD><ENTEREVENT><CALL>W1AW</CALL></CMD>") is True
    assert is_enterevent("<CMD><LISTRECORD></LISTRECORD></CMD>") is False
    assert message_type("<CMD><ENTEREVENT>...") == "ENTEREVENT"
```

- [ ] **Step 3: Run to verify it fails**

Run: `.venv/bin/pytest tests/test_n3fjp_parser.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 4: Implement** `src/openfieldday/sources/n3fjp_parser.py`

```python
from __future__ import annotations

import re
from datetime import datetime, timezone

from ..models import QSO

# One log record inside a LIST response. VERIFY this tag against a real capture.
RECORD_TAG = "LISTRECORD"

_RECORD_RE = re.compile(rf"<{RECORD_TAG}>(.*?)</{RECORD_TAG}>", re.DOTALL | re.IGNORECASE)


def _tag(record: str, name: str) -> str | None:
    m = re.search(rf"<{name}>(.*?)</{name}>", record, re.DOTALL | re.IGNORECASE)
    if not m:
        return None
    value = m.group(1).strip()
    return value or None


def _parse_timestamp(date: str | None, time_on: str | None) -> datetime | None:
    if not date or not time_on:
        return None
    digits = time_on.strip().replace(":", "")
    if len(digits) < 4:
        return None
    fmt_candidates = ("%Y/%m/%d", "%Y-%m-%d", "%m/%d/%Y")
    for fmt in fmt_candidates:
        try:
            d = datetime.strptime(date.strip(), fmt)
        except ValueError:
            continue
        return d.replace(
            hour=int(digits[0:2]), minute=int(digits[2:4]), tzinfo=timezone.utc
        )
    return None


def parse_list(payload: str) -> list[QSO]:
    """Parse an N3FJP LIST response into QSO records."""
    qsos: list[QSO] = []
    for record in _RECORD_RE.findall(payload):
        call = _tag(record, "CALL")
        if not call:
            continue
        qsos.append(
            QSO(
                call=call,
                band=_tag(record, "BAND") or "",
                mode=_tag(record, "MODE") or "",
                operator=_tag(record, "OPERATOR"),
                timestamp=_parse_timestamp(
                    _tag(record, "DATE"), _tag(record, "TIMEON")
                ),
            )
        )
    return qsos


def message_type(payload: str) -> str | None:
    """Return the command/response id, e.g. 'ENTEREVENT'."""
    m = re.search(r"<CMD><([A-Z0-9_]+)>", payload, re.IGNORECASE)
    return m.group(1).upper() if m else None


def is_enterevent(payload: str) -> bool:
    return message_type(payload) == "ENTEREVENT"
```

- [ ] **Step 5: Run to verify it passes**

Run: `.venv/bin/pytest tests/test_n3fjp_parser.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/openfieldday/sources/__init__.py src/openfieldday/sources/n3fjp_parser.py tests/test_n3fjp_parser.py tests/fixtures/list_includeall.txt
git commit -m "feat: add N3FJP LIST/ENTEREVENT payload parser"
```

---

## Task 8: Source base class

**Files:**
- Create: `src/openfieldday/sources/base.py`
- Test: `tests/test_source_base.py`

- [ ] **Step 1: Write the failing test** in `tests/test_source_base.py`

```python
import pytest
from openfieldday.sources.base import Source


def test_source_is_abstract():
    with pytest.raises(TypeError):
        Source()  # cannot instantiate abstract base
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/pytest tests/test_source_base.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement** `src/openfieldday/sources/base.py`

```python
from __future__ import annotations

from abc import ABC, abstractmethod


class Source(ABC):
    """A live QSO source. Implementations push updates into a QSOStore.

    The only contract: run() is an async coroutine that keeps the store
    current until cancelled.
    """

    @abstractmethod
    async def run(self) -> None:
        ...
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/pytest tests/test_source_base.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/openfieldday/sources/base.py tests/test_source_base.py
git commit -m "feat: add Source abstract base class"
```

---

## Task 9: N3FJP source (async TCP client)

**Files:**
- Create: `src/openfieldday/sources/n3fjp.py`
- Test: `tests/test_n3fjp_source.py`

This is the only networking code. Behaviour: connect → send `LIST` → parse response → `store.replace`. Then read messages line-by-line; on an `ENTEREVENT` push, send `LIST` again. A background timer sends `LIST` every `poll_interval` seconds. On any failure, set disconnected and reconnect with backoff. Writes to the socket are serialized with a lock. Messages are framed on `\r\n`.

- [ ] **Step 1: Write the failing test** in `tests/test_n3fjp_source.py`

```python
import asyncio
import pytest
from openfieldday.store import QSOStore
from openfieldday.sources.n3fjp import N3FJPSource

LIST_RESPONSE = (
    "<CMD><LISTRECORD><CALL>W1AW</CALL><BAND>20</BAND><MODE>SSB</MODE>"
    "<OPERATOR>AB1CD</OPERATOR><DATE>2026/06/27</DATE><TIMEON>1802</TIMEON>"
    "</LISTRECORD></CMD>\r\n"
)


async def _fake_n3fjp(reader, writer, *, push_enterevent=False, hits=None):
    """Minimal N3FJP API server: answers any command with LIST_RESPONSE."""
    if push_enterevent:
        writer.write(b"<CMD><ENTEREVENT><CALL>W1AW</CALL></CMD>\r\n")
        await writer.drain()
    while True:
        line = await reader.readline()
        if not line:
            break
        if hits is not None:
            hits.append(line)
        writer.write(LIST_RESPONSE.encode())
        await writer.drain()


async def test_connect_backfills_store():
    server = await asyncio.start_server(_fake_n3fjp, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    store = QSOStore()
    src = N3FJPSource("127.0.0.1", port, store, poll_interval=999)
    task = asyncio.create_task(src.run())
    try:
        async with server:
            await _wait_until(lambda: len(store.qsos) == 1, timeout=2)
        assert store.connected is True
        assert store.qsos[0].call == "W1AW"
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_enterevent_triggers_refresh():
    hits = []

    async def handler(r, w):
        await _fake_n3fjp(r, w, push_enterevent=True, hits=hits)

    server = await asyncio.start_server(handler, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    store = QSOStore()
    src = N3FJPSource("127.0.0.1", port, store, poll_interval=999)
    task = asyncio.create_task(src.run())
    try:
        async with server:
            # The initial backfill sends one LIST; the ENTEREVENT push must cause a
            # SECOND LIST command. Asserting >= 2 is what proves the refresh fired
            # (>= 1 would pass on the backfill alone and prove nothing).
            await _wait_until(lambda: len(hits) >= 2, timeout=2)
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_sets_disconnected_when_server_absent():
    store = QSOStore()
    # Port 1 is unused; connection refused.
    src = N3FJPSource("127.0.0.1", 1, store, poll_interval=999, backoff_base=0.05)
    task = asyncio.create_task(src.run())
    try:
        await asyncio.sleep(0.3)
        assert store.connected is False
        assert store.qsos == []
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def _wait_until(predicate, timeout):
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        if predicate():
            return
        await asyncio.sleep(0.02)
    raise AssertionError("condition not met before timeout")
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/pytest tests/test_n3fjp_source.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement** `src/openfieldday/sources/n3fjp.py`

```python
from __future__ import annotations

import asyncio
import logging

from .base import Source
from .n3fjp_parser import parse_list, is_enterevent, message_type
from ..store import QSOStore

log = logging.getLogger(__name__)

LIST_COMMAND = b"<CMD><LIST><INCLUDEALL></CMD>\r\n"


class N3FJPSource(Source):
    def __init__(
        self,
        host: str,
        port: int,
        store: QSOStore,
        poll_interval: float = 10.0,
        backoff_base: float = 1.0,
        backoff_max: float = 30.0,
    ) -> None:
        self._host = host
        self._port = port
        self._store = store
        self._poll_interval = poll_interval
        self._backoff_base = backoff_base
        self._backoff_max = backoff_max
        self._writer: asyncio.StreamWriter | None = None
        self._write_lock = asyncio.Lock()

    async def run(self) -> None:
        backoff = self._backoff_base
        while True:
            try:
                await self._connect_and_serve()
                backoff = self._backoff_base
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - resilience is the point
                log.warning("N3FJP connection error: %s", exc)
            finally:
                self._store.set_connected(False)
                self._writer = None
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, self._backoff_max)

    async def _connect_and_serve(self) -> None:
        reader, writer = await asyncio.open_connection(self._host, self._port)
        self._writer = writer
        self._store.set_connected(True)
        await self._send(LIST_COMMAND)  # initial backfill

        poller = asyncio.create_task(self._poll_loop())
        try:
            await self._read_loop(reader)
        finally:
            poller.cancel()
            await asyncio.gather(poller, return_exceptions=True)
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:  # noqa: BLE001
                pass

    async def _read_loop(self, reader: asyncio.StreamReader) -> None:
        while True:
            line = await reader.readline()
            if not line:  # EOF
                raise ConnectionError("N3FJP closed the connection")
            payload = line.decode(errors="replace").strip()
            if not payload:
                continue
            if is_enterevent(payload):
                await self._send(LIST_COMMAND)  # refresh now
            elif message_type(payload) is None or "LISTRECORD" in payload.upper() or payload.upper().endswith("</CMD>"):
                qsos = parse_list(payload)
                if qsos or payload.upper() == "<CMD></CMD>":
                    self._store.replace(qsos)

    async def _poll_loop(self) -> None:
        while True:
            await asyncio.sleep(self._poll_interval)
            await self._send(LIST_COMMAND)

    async def _send(self, data: bytes) -> None:
        if self._writer is None:
            return
        async with self._write_lock:
            self._writer.write(data)
            await self._writer.drain()
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/pytest tests/test_n3fjp_source.py -v`
Expected: PASS.

> If `test_enterevent_triggers_refresh` is flaky, it is timing-sensitive on slow hardware — raise the `_wait_until` timeout, not the production logic.

- [ ] **Step 5: Commit**

```bash
git add src/openfieldday/sources/n3fjp.py tests/test_n3fjp_source.py
git commit -m "feat: add N3FJP async TCP source with reconnect and polling"
```

---

## Task 10: FastAPI app — wiring and routes

**Files:**
- Create: `src/openfieldday/app.py`
- Test: `tests/test_app.py`

Wiring: `create_app(config_path)` builds a `QSOStore`, `Broadcaster`, loads `Config`, and registers a `recompute()` listener on the store that runs `compute_stats` and `broadcaster.publish(json)`. A FastAPI lifespan starts the `N3FJPSource.run()` task. Routes: `GET /api/stats`, `GET /api/config`, `POST /api/config`, `GET /events` (SSE), static files at `/`.

- [ ] **Step 1: Write the failing test** in `tests/test_app.py`

```python
import json
from fastapi.testclient import TestClient
from openfieldday.app import create_app
from openfieldday.models import QSO


def make_client(tmp_path):
    app = create_app(config_path=tmp_path / "config.yaml", start_source=False)
    return app, TestClient(app)


def test_stats_endpoint_initial(tmp_path):
    app, client = make_client(tmp_path)
    r = client.get("/api/stats")
    assert r.status_code == 200
    body = r.json()
    assert body["total_qsos"] == 0
    assert body["connected"] is False
    assert "band_mode" in body and "by_operator" in body


def test_stats_reflects_store_and_config(tmp_path):
    app, client = make_client(tmp_path)
    app.state.store.replace([QSO(call="W1AW", band="20", mode="CW")])
    r = client.get("/api/stats").json()
    assert r["total_qsos"] == 1
    assert r["qso_points"] == 2
    assert r["score"] == 2 * 2  # default multiplier 2, no bonus


def test_get_and_post_config(tmp_path):
    app, client = make_client(tmp_path)
    r = client.post("/api/config", json={
        "power_multiplier": 5,
        "bonuses": {"Emergency power": 100},
    })
    assert r.status_code == 200
    cfg = client.get("/api/config").json()
    assert cfg["power_multiplier"] == 5
    assert cfg["bonus_points"] == 100
    # config change is persisted
    assert (tmp_path / "config.yaml").exists()


def test_post_config_rejects_bad_multiplier(tmp_path):
    app, client = make_client(tmp_path)
    r = client.post("/api/config", json={"power_multiplier": 3, "bonuses": {}})
    assert r.status_code == 422


def test_events_streams_initial_snapshot(tmp_path):
    app, _ = make_client(tmp_path)
    # Use TestClient as a context manager so the FastAPI lifespan runs and
    # publishes the initial snapshot (otherwise the broadcaster has no latest
    # value and the SSE stream blocks forever — a hang, not a failure).
    with TestClient(app) as client:
        with client.stream("GET", "/events") as r:
            assert r.status_code == 200
            assert r.headers["content-type"].startswith("text/event-stream")
            for line in r.iter_lines():
                if line.startswith("data:"):
                    payload = json.loads(line[len("data:"):].strip())
                    assert "total_qsos" in payload
                    break
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/pytest tests/test_app.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement** `src/openfieldday/app.py`

```python
from __future__ import annotations

import json
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator

from .config import Config, POWER_MULTIPLIERS
from .events import Broadcaster
from .scoring import compute_stats
from .store import QSOStore
from .sources.n3fjp import N3FJPSource

STATIC_DIR = Path(__file__).parent / "static"


class ConfigUpdate(BaseModel):
    power_multiplier: int
    bonuses: dict[str, int]

    @field_validator("power_multiplier")
    @classmethod
    def _check_multiplier(cls, v: int) -> int:
        if v not in POWER_MULTIPLIERS:
            raise ValueError(f"power_multiplier must be one of {sorted(POWER_MULTIPLIERS)}")
        return v


def create_app(config_path: str | Path = "config.yaml", start_source: bool = True) -> FastAPI:
    config_path = Path(config_path)
    store = QSOStore()
    broadcaster = Broadcaster()
    state = {"config": Config.load(config_path)}

    def recompute() -> None:
        stats = compute_stats(store.qsos, state["config"], store.connected)
        broadcaster.publish(json.dumps(_stats_to_dict(stats)))

    store.on_change(recompute)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        recompute()  # publish initial snapshot
        task = None
        if start_source:
            cfg = state["config"]
            source = N3FJPSource(cfg.n3fjp_host, cfg.n3fjp_port, store)
            import asyncio
            task = asyncio.create_task(source.run())
        yield
        if task is not None:
            task.cancel()
            import asyncio
            await asyncio.gather(task, return_exceptions=True)

    app = FastAPI(lifespan=lifespan)
    app.state.store = store
    app.state.broadcaster = broadcaster

    @app.get("/api/stats")
    def get_stats() -> dict:
        return _stats_to_dict(compute_stats(store.qsos, state["config"], store.connected))

    @app.get("/api/config")
    def get_config() -> dict:
        return state["config"].to_public_dict()

    @app.post("/api/config")
    def post_config(update: ConfigUpdate) -> dict:
        cfg = state["config"]
        cfg.power_multiplier = update.power_multiplier
        cfg.bonuses = update.bonuses
        cfg.save(config_path)
        recompute()
        return cfg.to_public_dict()

    @app.get("/events")
    async def events() -> StreamingResponse:
        async def stream():
            async for data in broadcaster.subscribe():
                yield f"data:{data}\n\n"
        return StreamingResponse(stream(), media_type="text/event-stream")

    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    return app


def _stats_to_dict(stats) -> dict:
    return asdict(stats)
```

- [ ] **Step 4: Create a placeholder static dir so the mount succeeds**

Create `src/openfieldday/static/index.html` with a single line (replaced fully in Task 11):

```html
<!doctype html><title>OpenFieldDay</title><p>Dashboard placeholder.</p>
```

- [ ] **Step 5: Run to verify it passes**

Run: `.venv/bin/pytest tests/test_app.py -v`
Expected: PASS (all five tests).

- [ ] **Step 6: Run the full suite**

Run: `.venv/bin/pytest -v`
Expected: all tests PASS.

- [ ] **Step 7: Commit**

```bash
git add src/openfieldday/app.py src/openfieldday/static/index.html tests/test_app.py
git commit -m "feat: add FastAPI wiring, stats/config/SSE routes"
```

---

## Task 11: Frontend (dashboard + settings) and Chart.js vendoring

**Files:**
- Modify/replace: `src/openfieldday/static/index.html`
- Create: `src/openfieldday/static/styles.css`
- Create: `src/openfieldday/static/app.js`
- Create: `src/openfieldday/static/settings.html`
- Create: `src/openfieldday/static/settings.js`
- Create: `src/openfieldday/static/vendor/chart.min.js` (downloaded)

> The field site has no internet, so Chart.js must be vendored locally, not loaded from a CDN.

- [ ] **Step 1: Vendor Chart.js**

Run:
```bash
mkdir -p src/openfieldday/static/vendor
curl -L -o src/openfieldday/static/vendor/chart.min.js https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js
```
Expected: a non-empty `chart.min.js` (~200KB).

- [ ] **Step 2: Write the dashboard** `src/openfieldday/static/index.html`

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>OpenFieldDay Scoreboard</title>
  <link rel="stylesheet" href="/styles.css">
</head>
<body>
  <header>
    <h1>OpenFieldDay</h1>
    <div id="conn" class="disconnected">⚠ Disconnected — reconnecting…</div>
    <a class="settings-link" href="/settings.html">Settings</a>
  </header>
  <main>
    <section class="panel score">
      <div class="big" id="score">0</div><div class="label">Score</div>
      <div class="sub"><span id="total">0</span> QSOs · <span id="points">0</span> pts ×
        <span id="mult">1</span> + <span id="bonus">0</span> bonus</div>
    </section>
    <section class="panel rate">
      <div class="big" id="rate10">0</div><div class="label">QSOs/hr (10 min)</div>
      <div class="sub"><span id="rate60">0</span>/hr last 60 min</div>
    </section>
    <section class="panel chart">
      <div class="label">Band × Mode</div>
      <canvas id="bandModeChart"></canvas>
    </section>
    <section class="panel ops">
      <div class="label">Operators</div>
      <table id="opTable"><tbody></tbody></table>
    </section>
  </main>
  <script src="/vendor/chart.min.js"></script>
  <script src="/app.js"></script>
</body>
</html>
```

- [ ] **Step 3: Write the styles** `src/openfieldday/static/styles.css`

```css
:root { --bg:#0b1021; --panel:#161c3a; --fg:#f5f7ff; --accent:#ffd166; --bad:#ef476f; --good:#06d6a0; }
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--fg); font-family:system-ui,sans-serif; }
header { display:flex; align-items:center; gap:1rem; padding:0.5rem 1.5rem; }
header h1 { margin:0; font-size:1.8rem; color:var(--accent); }
.settings-link { margin-left:auto; color:var(--fg); opacity:0.6; font-size:0.9rem; }
#conn { font-weight:bold; padding:0.2rem 0.6rem; border-radius:0.4rem; }
#conn.connected { background:var(--good); color:#003; }
#conn.disconnected { background:var(--bad); }
main { display:grid; grid-template-columns:1fr 1fr; gap:1rem; padding:1.5rem; height:calc(100vh - 64px); }
.panel { background:var(--panel); border-radius:1rem; padding:1.5rem; display:flex; flex-direction:column; }
.big { font-size:6rem; font-weight:800; line-height:1; color:var(--accent); }
.label { text-transform:uppercase; letter-spacing:0.1em; opacity:0.7; }
.sub { margin-top:0.5rem; opacity:0.8; }
.ops table { width:100%; border-collapse:collapse; font-size:1.6rem; }
.ops td { padding:0.3rem 0.5rem; border-bottom:1px solid rgba(255,255,255,0.1); }
.ops td:last-child { text-align:right; color:var(--accent); font-weight:bold; }
.chart canvas { flex:1; min-height:0; }
```

- [ ] **Step 4: Write the dashboard logic** `src/openfieldday/static/app.js`

```javascript
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

  // Band x mode stacked bars
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
    // EventSource auto-reconnects; nothing else needed.
  };
}

initChart();
connect();
```

- [ ] **Step 5: Write the settings page** `src/openfieldday/static/settings.html`

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>OpenFieldDay Settings</title>
  <link rel="stylesheet" href="/styles.css">
</head>
<body>
  <header><h1>Settings</h1><a class="settings-link" href="/">← Dashboard</a></header>
  <main style="display:block; max-width:600px;">
    <form id="form" class="panel">
      <fieldset>
        <legend>Power class (multiplier)</legend>
        <label><input type="radio" name="mult" value="1"> 1× (&gt;150 W)</label>
        <label><input type="radio" name="mult" value="2"> 2× (≤150 W)</label>
        <label><input type="radio" name="mult" value="5"> 5× (≤5 W QRP)</label>
      </fieldset>
      <fieldset id="bonuses"><legend>Bonuses</legend></fieldset>
      <button type="submit">Save</button>
      <span id="saved"></span>
    </form>
  </main>
  <script src="/settings.js"></script>
</body>
</html>
```

- [ ] **Step 6: Write the settings logic** `src/openfieldday/static/settings.js`

```javascript
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
```

- [ ] **Step 7: Add the bonus-catalog endpoint** in `src/openfieldday/app.py`

Add this route inside `create_app` (next to the other routes):

```python
    @app.get("/api/bonus-catalog")
    def bonus_catalog() -> dict:
        from .config import BONUS_CATALOG
        return BONUS_CATALOG
```

- [ ] **Step 8: Add a test for the catalog endpoint** in `tests/test_app.py`

```python
def test_bonus_catalog_endpoint(tmp_path):
    app, client = make_client(tmp_path)
    r = client.get("/api/bonus-catalog")
    assert r.status_code == 200
    assert "Emergency power" in r.json()
```

- [ ] **Step 9: Run the full suite**

Run: `.venv/bin/pytest -v`
Expected: all tests PASS.

- [ ] **Step 10: Manual smoke test**

Run:
```bash
.venv/bin/python -m openfieldday  # (entry point added in Task 12; or: uvicorn for now)
```
For now, before Task 12, run:
```bash
.venv/bin/uvicorn "openfieldday.app:create_app" --factory --host 0.0.0.0 --port 8000
```
Open `http://localhost:8000/` — dashboard renders zeros and shows "Disconnected" (no N3FJP). Open `/settings.html`, toggle a bonus and power class, Save, and confirm the dashboard score updates.

- [ ] **Step 11: Commit**

```bash
git add src/openfieldday/static src/openfieldday/app.py tests/test_app.py
git commit -m "feat: add dashboard and settings UI with vendored Chart.js"
```

---

## Task 12: Entry point and deployment notes

**Files:**
- Create: `src/openfieldday/__main__.py`
- Modify: `README.md`
- Create: `deploy/openfieldday.service` (systemd example)

- [ ] **Step 1: Write the entry point** `src/openfieldday/__main__.py`

```python
from __future__ import annotations

import os

import uvicorn


def main() -> None:
    host = os.environ.get("OFD_HOST", "0.0.0.0")
    port = int(os.environ.get("OFD_PORT", "8000"))
    config_path = os.environ.get("OFD_CONFIG", "config.yaml")

    from .app import create_app

    uvicorn.run(create_app(config_path=config_path), host=host, port=port)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify the entry point runs**

Run: `.venv/bin/python -m openfieldday` (Ctrl-C to stop)
Expected: Uvicorn starts on `0.0.0.0:8000`; dashboard reachable.

- [ ] **Step 3: Write the systemd unit** `deploy/openfieldday.service`

```ini
[Unit]
Description=OpenFieldDay TV Scoreboard
After=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/pi/OpenFieldDay
Environment=OFD_CONFIG=/home/pi/OpenFieldDay/config.yaml
ExecStart=/home/pi/OpenFieldDay/.venv/bin/python -m openfieldday
Restart=always
RestartSec=3
User=pi

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 4: Document usage** — append to `README.md`

```markdown
## Running

1. `python -m venv .venv && .venv/bin/pip install -e ".[dev]"`
2. Set N3FJP host/port in `config.yaml` (or copy from defaults; the settings page
   manages power class and bonuses). Example:
   ```yaml
   n3fjp_host: 192.168.1.50
   n3fjp_port: 1100
   power_multiplier: 2
   bonuses: {}
   ```
3. Enable N3FJP's TCP API (Settings → API) on the master logging PC.
4. Run `.venv/bin/python -m openfieldday` and open `http://<pi-ip>:8000/`.

### Kiosk on the Pi
Point Chromium at the dashboard full-screen:
`chromium-browser --kiosk --app=http://localhost:8000/`

### Run as a service
Copy `deploy/openfieldday.service` to `/etc/systemd/system/`, then
`sudo systemctl enable --now openfieldday`.
```

- [ ] **Step 5: Run the full suite one final time**

Run: `.venv/bin/pytest -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add src/openfieldday/__main__.py deploy/openfieldday.service README.md
git commit -m "feat: add entry point, systemd unit, and run docs"
```

---

## Post-implementation verification (against real N3FJP)

These require the group's actual N3FJP and were flagged in the spec:

- [ ] Capture a real `<CMD><LIST><INCLUDEALL></CMD>` response; replace `tests/fixtures/list_includeall.txt`. Adjust `RECORD_TAG` and field tag names in `n3fjp_parser.py` if the capture differs, and re-run `pytest`.
- [ ] Confirm the operator field name in the capture (`OPERATOR` vs other). If absent, the per-operator leaderboard will show everything under "Unknown" — decide whether to source operator elsewhere.
- [ ] Confirm current ARRL Field Day rule values: QSO points, power tiers (1×/2×/5×), and the bonus catalog in `config.py`.
- [ ] Confirm line framing: this implementation reads `\r\n`-terminated messages. If N3FJP sends a large multi-line LIST payload, adjust `_read_loop` framing to accumulate until `</CMD>`.

---

## Self-Review

**Spec coverage:**
- Read-only dashboard, N3FJP TCP API source behind a pluggable interface → Tasks 8, 9 (`Source`/`N3FJPSource`).
- Total/score, rate, band×mode, per-operator → Task 4 (`compute_stats`), Task 11 (rendering).
- Official score = points × power mult + bonuses, config-driven → Tasks 3, 4, 11 settings.
- Mode grouping (Phone/CW/Digital), points 1/2/2, unknown→Phone → Task 2.
- N3FJP merges/dedups; LIST authoritative; ENTEREVENT = refresh trigger → Task 9.
- In-memory store, no persistence, rebuild on restart → Task 5.
- SSE live push, TV + LAN viewers → Tasks 6, 10, 11.
- Config via YAML + web settings page → Tasks 3, 11.
- Error handling: disconnected banner, retry/backoff, skip bad records, zero state → Tasks 9 (backoff), 7 (tolerant parse), 11 (banner), 4 (zero state).
- Testing strategy (pure engine units, fake TCP server, API/SSE) → Tasks 4, 9, 10.
- Open items (capture LIST, verify operator/rules/framing) → Post-implementation section.

**Placeholder scan:** The `index.html` placeholder in Task 10 is intentional and fully replaced in Task 11. The fixture in Task 7 is explicitly marked for replacement with a real capture. No "TBD"/"add error handling"-style gaps remain; every code step shows complete code.

**Type consistency:** `QSO(call, band, mode, operator, timestamp)`, `Stats` fields, `compute_stats(qsos, config, connected, now)`, `Config(.power_multiplier/.bonuses/.bonus_points)`, `QSOStore(.replace/.set_connected/.qsos/.connected/.on_change)`, `Broadcaster(.publish/.subscribe)`, `parse_list/is_enterevent/message_type`, and `N3FJPSource(host, port, store, poll_interval, backoff_base)` are used consistently across tasks and tests.
