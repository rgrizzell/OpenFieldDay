from datetime import datetime, timedelta, timezone
from openfieldday.models import QSO
from openfieldday.config import Config
from openfieldday.scoring import compute_stats

NOW = datetime(2026, 6, 27, 20, 0, tzinfo=timezone.utc)


def q(call, band, mode, operator=None, minutes_ago=None, section=None, qso_class=None):
    ts = None if minutes_ago is None else NOW - timedelta(minutes=minutes_ago)
    return QSO(call=call, band=band, mode=mode, operator=operator, timestamp=ts,
               section=section, qso_class=qso_class)


def test_empty_log_is_all_zero():
    s = compute_stats([], Config(), connected=True, now=NOW)
    assert s.total_qsos == 0
    assert s.qso_points == 0
    assert s.score == 0
    assert s.band_mode == []
    assert s.top_operators == []
    assert s.recent_qsos == []
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


def test_top_operators_last_hour_capped_and_drops_inactive():
    qsos = [
        q("A", "20", "SSB", operator="AB1CD", minutes_ago=2),
        q("B", "20", "SSB", operator="AB1CD", minutes_ago=5),
        q("C", "20", "SSB", operator="AB1CD", minutes_ago=8),   # AB1CD = 3
        q("D", "20", "SSB", operator="EF2GH", minutes_ago=10),
        q("E", "20", "SSB", operator="EF2GH", minutes_ago=12),  # EF2GH = 2
        q("F", "20", "SSB", operator="IJ3KL", minutes_ago=15),  # IJ3KL = 1
        q("G", "20", "SSB", operator="MN4OP", minutes_ago=20),  # MN4OP = 1 (over cap)
        q("H", "20", "SSB", operator="OLD", minutes_ago=90),    # >60 min -> drops off
    ]
    s = compute_stats(qsos, Config(), connected=True, now=NOW)
    assert len(s.top_operators) == 3  # capped at top 3
    assert [o.operator for o in s.top_operators] == ["AB1CD", "EF2GH", "IJ3KL"]
    assert s.top_operators[0].count == 3
    assert all(o.operator != "OLD" for o in s.top_operators)  # inactive op dropped


def test_top_operators_unknown_bucket():
    s = compute_stats([q("A", "20", "SSB", operator=None, minutes_ago=5)],
                      Config(), connected=True, now=NOW)
    assert s.top_operators[0].operator == "Unknown"


def test_contest_state_reflects_window():
    cfg = Config(contest_start="2026-06-27T18:00:00Z", contest_end="2026-06-28T21:00:00Z")
    before = datetime(2026, 6, 27, 17, 0, tzinfo=timezone.utc)
    during = datetime(2026, 6, 27, 20, 0, tzinfo=timezone.utc)
    after = datetime(2026, 6, 29, 0, 0, tzinfo=timezone.utc)
    assert compute_stats([], cfg, connected=True, now=before).contest_state == "pending"
    assert compute_stats([], cfg, connected=True, now=during).contest_state == "active"
    assert compute_stats([], cfg, connected=True, now=after).contest_state == "ended"


def test_contest_state_unset_without_window():
    s = compute_stats([], Config(), connected=True, now=NOW)
    assert s.contest_state == "unset"


def test_recent_qsos_newest_first_with_class_and_section():
    qsos = [
        q("OLDEST", "20", "SSB", minutes_ago=50, section="CT", qso_class="1A", operator="AB1CD"),
        q("NEWEST", "40", "CW", minutes_ago=1, section="EMA", qso_class="2A", operator="EF2GH"),
    ]
    s = compute_stats(qsos, Config(), connected=True, now=NOW)
    assert [e.call for e in s.recent_qsos] == ["NEWEST", "OLDEST"]  # newest first
    assert s.recent_qsos[0].qso_class == "2A"
    assert s.recent_qsos[0].section == "EMA"
    assert s.recent_qsos[0].operator == "EF2GH"


def test_qsos_per_hour_counts_trailing_60_minutes():
    qsos = [
        q("A", "20", "SSB", minutes_ago=2),
        q("B", "20", "SSB", minutes_ago=5),
        q("C", "20", "SSB", minutes_ago=30),    # still within the last 60 min
        q("D", "20", "SSB", minutes_ago=90),    # outside the window
    ]
    s = compute_stats(qsos, Config(), connected=True, now=NOW)
    assert s.qsos_per_hour == 3.0   # A, B, C are within 60 min; D is not


def test_rate_buckets_5min_over_60min():
    qsos = [
        q("A", "20", "SSB", minutes_ago=1),     # newest bucket (index 11)
        q("B", "20", "SSB", minutes_ago=3),     # also newest bucket
        q("C", "20", "SSB", minutes_ago=12),    # 10-15 min ago -> index 9
        q("D", "20", "SSB", minutes_ago=58),    # oldest bucket (index 0)
        q("E", "20", "SSB", minutes_ago=75),    # outside window -> ignored
        q("F", "20", "SSB"),                     # no timestamp -> ignored
    ]
    s = compute_stats(qsos, Config(), connected=True, now=NOW)
    assert len(s.rate_buckets) == 12
    assert s.rate_buckets[11] == 2   # A, B
    assert s.rate_buckets[9] == 1    # C
    assert s.rate_buckets[0] == 1    # D
    assert sum(s.rate_buckets) == 4  # E and F excluded


def test_worked_sections_distinct_and_sorted():
    qsos = [
        q("A", "20", "SSB", section="CT"),
        q("B", "20", "SSB", section="EMA"),
        q("C", "20", "SSB", section="CT"),    # duplicate section
        q("D", "20", "SSB", section=None),    # no section -> excluded
    ]
    s = compute_stats(qsos, Config(), connected=True, now=NOW)
    assert s.worked_sections == ["CT", "EMA"]
