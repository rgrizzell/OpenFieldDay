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
