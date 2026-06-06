from __future__ import annotations

import re
from datetime import datetime, timezone

from ..models import QSO

# One log record inside a LIST response. VERIFY this tag against a real capture.
RECORD_TAG = "LISTRECORD"

_RECORD_RE = re.compile(rf"<{RECORD_TAG}>(.*?)</{RECORD_TAG}>", re.DOTALL | re.IGNORECASE)


def _tag(record: str, name: str) -> str | None:
    m = re.search(rf"<{name}>(.*?)</{name}>", record, re.DOTALL | re.IGNORECASE)
    if not m:
        return None
    value = m.group(1).strip()
    return value or None


def _parse_timestamp(date: str | None, time_on: str | None) -> datetime | None:
    if not date or not time_on:
        return None
    digits = time_on.strip().replace(":", "")
    if len(digits) < 4:
        return None
    fmt_candidates = ("%Y/%m/%d", "%Y-%m-%d", "%m/%d/%Y")
    for fmt in fmt_candidates:
        try:
            d = datetime.strptime(date.strip(), fmt)
        except ValueError:
            continue
        return d.replace(
            hour=int(digits[0:2]), minute=int(digits[2:4]), tzinfo=timezone.utc
        )
    return None


def parse_list(payload: str) -> list[QSO]:
    """Parse an N3FJP LIST response into QSO records."""
    qsos: list[QSO] = []
    for record in _RECORD_RE.findall(payload):
        call = _tag(record, "CALL")
        if not call:
            continue
        qsos.append(
            QSO(
                call=call,
                band=_tag(record, "BAND") or "",
                mode=_tag(record, "MODE") or "",
                operator=_tag(record, "OPERATOR"),
                timestamp=_parse_timestamp(
                    _tag(record, "DATE"), _tag(record, "TIMEON")
                ),
            )
        )
    return qsos


def message_type(payload: str) -> str | None:
    """Return the command/response id, e.g. 'ENTEREVENT'."""
    m = re.search(r"<CMD><([A-Z0-9_]+)>", payload, re.IGNORECASE)
    return m.group(1).upper() if m else None


def is_enterevent(payload: str) -> bool:
    return message_type(payload) == "ENTEREVENT"
