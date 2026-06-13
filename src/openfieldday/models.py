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
    section: str | None = None    # ARRL/RAC section from the Field Day exchange
    qso_class: str | None = None  # Field Day class from the exchange, e.g. "2A"


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
class QSOLogEntry:
    call: str
    qso_class: str | None
    section: str | None
    operator: str | None


@dataclass(frozen=True)
class Stats:
    total_qsos: int
    qso_points: int
    power_multiplier: int
    bonus_points: int
    score: int
    qsos_per_hour: float  # actual QSOs logged in the trailing 60 minutes
    # QSO counts per 5-minute bucket over the trailing 60 minutes, oldest first
    # (12 buckets). Drives the rate-history sparkline.
    rate_buckets: list[int] = field(default_factory=list)
    # Distinct ARRL/RAC sections contacted, sorted. Drives the sections map.
    worked_sections: list[str] = field(default_factory=list)
    band_mode: list[BandModeCount] = field(default_factory=list)
    # Top operators by QSO count in the trailing 60 minutes (so inactive ops drop off).
    top_operators: list[OperatorCount] = field(default_factory=list)
    # Most recent QSOs, newest first, for the live log panel.
    recent_qsos: list[QSOLogEntry] = field(default_factory=list)
    connected: bool = False
    # Contest status vs the configured window: "active", "pending", "ended", "unset".
    contest_state: str = "unset"
