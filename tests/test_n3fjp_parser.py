from datetime import datetime, timezone
from pathlib import Path
from openfieldday.sources.n3fjp_parser import (
    parse_list, message_type, is_enterevent,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_list_extracts_qsos():
    # Two LISTRESPONSE records concatenated on one line, as N3FJP really sends them.
    payload = (FIXTURES / "list_includeall.txt").read_text()
    qsos = parse_list(payload)
    assert len(qsos) == 2
    first = qsos[0]
    assert first.call == "W1AW"
    assert first.band == "20"
    assert first.mode == "SSB"
    assert first.operator == "AB1CD"  # comes from <FLDOPERATOR>
    assert first.section == "CT"      # comes from <SECTION>
    assert first.qso_class == "1A"    # comes from <CLASS>
    assert first.timestamp == datetime(2026, 6, 27, 18, 2, tzinfo=timezone.utc)
    assert qsos[1].section == "EMA"
    assert qsos[1].qso_class == "2A"


def test_parse_list_tolerates_missing_optional_fields():
    payload = "<CMD><LISTRESPONSE><CALL>N0CALL</CALL><BAND>15</BAND><MODE>FT8</MODE></CMD>"
    qsos = parse_list(payload)
    assert len(qsos) == 1
    assert qsos[0].operator is None
    assert qsos[0].timestamp is None


def test_parse_list_ignores_calltabevent():
    # The real-time call-entry preview must never be counted as a logged QSO.
    payload = (
        "<CMD><CALLTABEVENT><CALL>WB9JJO</CALL><BAND>20</BAND><MODE>DIG</MODE>"
        "<OPERATOR>W3GRZ</OPERATOR><QSOCOUNT>1</QSOCOUNT></CMD>"
    )
    assert parse_list(payload) == []


def test_parse_list_ignores_enterevent():
    payload = (
        "<CMD><ENTEREVENT><QSOCOUNT>2</QSOCOUNT><CALL>WB9JJO</CALL>"
        "<BAND>20</BAND><MODE>DIG</MODE></CMD>"
    )
    assert parse_list(payload) == []


def test_parse_list_empty_returns_empty():
    assert parse_list("<CMD></CMD>") == []


def test_message_type_and_is_enterevent():
    assert is_enterevent("<CMD><ENTEREVENT><CALL>W1AW</CALL></CMD>") is True
    assert is_enterevent("<CMD><LISTRESPONSE><CALL>W1AW</CALL></CMD>") is False
    assert message_type("<CMD><ENTEREVENT>...") == "ENTEREVENT"
