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
