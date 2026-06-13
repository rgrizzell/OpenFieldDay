from __future__ import annotations

from dataclasses import dataclass, field
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

# Dashboard theme. Keys match the CSS custom properties (--bg, --accent, ...);
# config values override these and are applied by the dashboard at load.
DEFAULT_COLORS: dict[str, str] = {
    "bg": "#0b1021",
    "panel": "#161c3a",
    "fg": "#f5f7ff",
    "accent": "#ffd166",
    "bad": "#ef476f",
    "good": "#06d6a0",
}


@dataclass
class Config:
    n3fjp_host: str = "127.0.0.1"
    n3fjp_port: int = 1100
    power_multiplier: int = 2
    bonuses: dict[str, int] = field(default_factory=dict)
    # Theme overrides (subset of DEFAULT_COLORS keys) and an optional logo image
    # path on disk; the logo tile only appears when a readable file is configured.
    colors: dict[str, str] = field(default_factory=dict)
    logo_path: str | None = None

    @property
    def bonus_points(self) -> int:
        return sum(self.bonuses.values())

    @property
    def merged_colors(self) -> dict[str, str]:
        return {**DEFAULT_COLORS, **self.colors}

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
        }
        Path(path).write_text(yaml.safe_dump(data, sort_keys=True))

    @classmethod
    def load(cls, path: str | Path) -> "Config":
        p = Path(path)
        if not p.exists():
            return cls()
        data = yaml.safe_load(p.read_text()) or {}
        return cls(
            n3fjp_host=data.get("n3fjp_host", "127.0.0.1"),
            n3fjp_port=int(data.get("n3fjp_port", 1100)),
            power_multiplier=int(data.get("power_multiplier", 2)),
            bonuses=dict(data.get("bonuses", {})),
            colors=dict(data.get("colors") or {}),
            logo_path=data.get("logo_path") or None,
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
            "colors": self.merged_colors,
            "has_logo": self.has_logo,
        }
