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
