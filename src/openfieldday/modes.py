from __future__ import annotations

import logging

log = logging.getLogger(__name__)

CW_MODES = {"CW"}
PHONE_MODES = {"SSB", "USB", "LSB", "FM", "AM", "PHONE", "DV", "FT8PHONE"}
DIGITAL_MODES = {
    "RTTY", "FT8", "FT4", "PSK", "PSK31", "PSK63", "JT65", "JT9",
    "MFSK", "JS8", "OLIVIA", "DIGITAL", "DIG", "DATA", "DIGITALVOICE", "MSK144",
}


def mode_group(mode: str) -> str:
    """Map a raw ADIF/N3FJP mode to one of CW / Phone / Digital.

    Per the design, unrecognized modes default to Phone (and are logged).
    """
    m = (mode or "").strip().upper()
    if m in CW_MODES:
        return "CW"
    if m in DIGITAL_MODES:
        return "Digital"
    if m in PHONE_MODES:
        return "Phone"
    log.warning("Unrecognized mode %r; defaulting to Phone", mode)
    return "Phone"


def qso_points(mode: str) -> int:
    """1 point for Phone, 2 points for CW and Digital."""
    return 1 if mode_group(mode) == "Phone" else 2
