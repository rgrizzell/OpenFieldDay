from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone

from .models import QSO, Stats, BandModeCount, OperatorCount, QSOLogEntry
from .modes import mode_group, qso_points
from .config import Config

# Rate-history sparkline: 5-minute buckets across a 60-minute trailing window.
RATE_BUCKET_MINUTES = 5
RATE_WINDOW_MINUTES = 60
RATE_BUCKET_COUNT = RATE_WINDOW_MINUTES // RATE_BUCKET_MINUTES  # 12

# Operators panel shows the busiest few in the trailing hour; log shows the latest.
TOP_OPERATOR_COUNT = 3
RECENT_QSO_COUNT = 25


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

    window_start = now - timedelta(minutes=RATE_WINDOW_MINUTES)
    in_last_60 = 0
    # Bucket index 0 is the oldest 5-minute slice, the last index is the newest.
    rate_buckets = [0] * RATE_BUCKET_COUNT
    op_counter: Counter[str] = Counter()  # operators active in the trailing hour
    for q in qsos:
        if not q.timestamp or q.timestamp <= window_start or q.timestamp > now:
            continue
        in_last_60 += 1
        op_counter[q.operator or "Unknown"] += 1
        minutes_ago = (now - q.timestamp).total_seconds() / 60.0
        idx = RATE_BUCKET_COUNT - 1 - int(minutes_ago // RATE_BUCKET_MINUTES)
        idx = max(0, min(RATE_BUCKET_COUNT - 1, idx))
        rate_buckets[idx] += 1

    top_operators = [
        OperatorCount(operator=op, count=count)
        for op, count in sorted(op_counter.items(), key=lambda kv: (-kv[1], kv[0]))[:TOP_OPERATOR_COUNT]
    ]

    recent = sorted(
        qsos,
        key=lambda q: q.timestamp or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )[:RECENT_QSO_COUNT]
    recent_qsos = [
        QSOLogEntry(call=q.call, qso_class=q.qso_class, section=q.section, operator=q.operator)
        for q in recent
    ]

    start, end = config.contest_window()
    if not start or not end:
        contest_state = "unset"
    elif now < start:
        contest_state = "pending"
    elif now <= end:
        contest_state = "active"
    else:
        contest_state = "ended"

    return Stats(
        total_qsos=len(qsos),
        qso_points=total_points,
        power_multiplier=config.power_multiplier,
        bonus_points=bonus,
        score=score,
        qsos_per_hour=float(in_last_60),
        rate_buckets=rate_buckets,
        worked_sections=sorted({q.section for q in qsos if q.section}),
        band_mode=band_mode,
        top_operators=top_operators,
        recent_qsos=recent_qsos,
        connected=connected,
        contest_state=contest_state,
    )
