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
