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
