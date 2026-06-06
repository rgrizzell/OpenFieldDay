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
