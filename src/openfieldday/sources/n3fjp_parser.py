from __future__ import annotations

import re
from datetime import datetime, timezone

from ..models import QSO

# N3FJP frames every message as <CMD>...</CMD>. A logged QSO in a LIST response is
# a command whose id is LISTRESPONSE: <CMD><LISTRESPONSE><CALL>...</CALL>...</CMD>
# — note there is NO closing </LISTRESPONSE>; the id is just the first marker tag
# and the fields are its siblings. Multiple LISTRESPONSE blocks are concatenated
# inside a single CRLF-terminated line, so we split on <CMD>...</CMD> blocks rather
# than lines. Verified against a live N3FJP Field Day capture.
LIST_RECORD_CMD = "LISTRESPONSE"

_CMD_BLOCK_RE = re.compile(r"<CMD>(.*?)</CMD>", re.DOTALL | re.IGNORECASE)
_CMD_ID_RE = re.compile(r"\s*<([A-Z0-9_]+)>", re.IGNORECASE)


def _cmd_id(block: str) -> str | None:
    m = _CMD_ID_RE.match(block)
    return m.group(1).upper() if m else None


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
    """Parse N3FJP LISTRESPONSE records out of a payload into QSO objects.

    Ignores non-LISTRESPONSE commands (e.g. CALLTABEVENT, ENTEREVENT) so a
    real-time call-entry preview is never mistaken for a logged contact.
    """
    qsos: list[QSO] = []
    for block in _CMD_BLOCK_RE.findall(payload):
        if _cmd_id(block) != LIST_RECORD_CMD:
            continue
        call = _tag(block, "CALL")
        if not call:
            continue
        qsos.append(
            QSO(
                call=call,
                band=_tag(block, "BAND") or "",
                mode=_tag(block, "MODE") or "",
                operator=_tag(block, "FLDOPERATOR"),
                timestamp=_parse_timestamp(
                    _tag(block, "DATE"), _tag(block, "TIMEON")
                ),
                section=_tag(block, "SECTION"),
                qso_class=_tag(block, "CLASS"),
            )
        )
    return qsos


def message_type(payload: str) -> str | None:
    """Return the command/response id, e.g. 'ENTEREVENT'."""
    m = re.search(r"<CMD><([A-Z0-9_]+)>", payload, re.IGNORECASE)
    return m.group(1).upper() if m else None


def is_enterevent(payload: str) -> bool:
    return message_type(payload) == "ENTEREVENT"
