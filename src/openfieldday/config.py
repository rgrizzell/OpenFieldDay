from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml

# Point values to VERIFY against the current ARRL Field Day rules at implementation
# time. Stored as data so they are easy to update; the settings page renders a
# checkbox per entry.
BONUS_CATALOG: dict[str, int] = {
    "Emergency power": 100,
    "Public location": 100,
    "Public information table": 100,
    "Message to ARRL SM/SEC": 100,
    "Copy W1AW Field Day message": 100,
    "Media publicity": 100,
    "Satellite QSO": 100,
    "GOTA bonus (educational)": 100,
    "Web submission": 50,
    "Youth participation": 20,
    "Social media": 100,
    "Educational activity": 100,
}

# Allowed Field Day power multipliers. VERIFY tiers/values against current rules.
POWER_MULTIPLIERS = {1, 2, 5}


@dataclass
class Config:
    n3fjp_host: str = "127.0.0.1"
    n3fjp_port: int = 1100
    power_multiplier: int = 2
    bonuses: dict[str, int] = field(default_factory=dict)
    # Theme color overrides on top of the built-in light/dark palettes (the
    # defaults live in the dashboard CSS). Either a nested mapping
    #   {"light": {...}, "dark": {...}}
    # or a flat {key: value} dict, which is treated as dark-theme overrides for
    # backward compatibility. Keys match the CSS custom properties (bg, accent...).
    colors: dict = field(default_factory=dict)
    logo_path: str | None = None  # optional logo image; tile shown only if readable
    # "auto" theme mode uses light during [auto_light_start, auto_light_end) local
    # (hours, 24h) and dark otherwise.
    auto_light_start: int = 5
    auto_light_end: int = 21
    # Contest window as ISO 8601 datetimes (include a timezone, e.g. ...Z; a naive
    # value is treated as UTC). Drives the header contest-status indicator.
    contest_start: str | None = None
    contest_end: str | None = None

    @property
    def bonus_points(self) -> int:
        return sum(self.bonuses.values())

    @staticmethod
    def _parse_dt(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

    def contest_window(self) -> tuple[datetime | None, datetime | None]:
        """Parsed (start, end); either may be None if unset or unparseable."""
        return self._parse_dt(self.contest_start), self._parse_dt(self.contest_end)

    def theme_color_overrides(self) -> dict:
        """Per-theme color overrides as {"light": {...}, "dark": {...}}.

        A flat color dict (legacy/simple form) is applied to the dark theme.
        """
        c = self.colors or {}
        if "light" in c or "dark" in c:
            return {"light": dict(c.get("light") or {}), "dark": dict(c.get("dark") or {})}
        return {"light": {}, "dark": dict(c)}

    @property
    def has_logo(self) -> bool:
        return bool(self.logo_path) and Path(self.logo_path).is_file()

    def save(self, path: str | Path) -> None:
        data = {
            "n3fjp_host": self.n3fjp_host,
            "n3fjp_port": self.n3fjp_port,
            "power_multiplier": self.power_multiplier,
            "bonuses": self.bonuses,
            "colors": self.colors,
            "logo_path": self.logo_path,
            "auto_light_start": self.auto_light_start,
            "auto_light_end": self.auto_light_end,
            "contest_start": self.contest_start,
            "contest_end": self.contest_end,
        }
        Path(path).write_text(yaml.safe_dump(data, sort_keys=True))

    @classmethod
    def load(cls, path: str | Path) -> "Config":
        p = Path(path)
        if not p.exists():
            return cls()
        data = yaml.safe_load(p.read_text()) or {}

        def as_str(v):  # YAML may parse an ISO datetime natively; store as a string
            if v is None:
                return None
            return v.isoformat() if hasattr(v, "isoformat") else str(v)

        return cls(
            n3fjp_host=data.get("n3fjp_host", "127.0.0.1"),
            n3fjp_port=int(data.get("n3fjp_port", 1100)),
            power_multiplier=int(data.get("power_multiplier", 2)),
            bonuses=dict(data.get("bonuses", {})),
            colors=dict(data.get("colors") or {}),
            logo_path=data.get("logo_path") or None,
            auto_light_start=int(data.get("auto_light_start", 5)),
            auto_light_end=int(data.get("auto_light_end", 21)),
            contest_start=as_str(data.get("contest_start")),
            contest_end=as_str(data.get("contest_end")),
        )

    def to_public_dict(self) -> dict:
        """Shape consumed by the dashboard and settings page.

        Exposes merged theme colors and whether a logo is available, but not the
        raw logo filesystem path (the dashboard fetches the image from /logo).
        """
        return {
            "n3fjp_host": self.n3fjp_host,
            "n3fjp_port": self.n3fjp_port,
            "power_multiplier": self.power_multiplier,
            "bonuses": self.bonuses,
            "bonus_points": self.bonus_points,
            "colors": self.theme_color_overrides(),
            "theme": {
                "auto_light_start": self.auto_light_start,
                "auto_light_end": self.auto_light_end,
            },
            "has_logo": self.has_logo,
        }
