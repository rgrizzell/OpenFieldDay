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
