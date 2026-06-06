from __future__ import annotations

from dataclasses import dataclass, field, asdict
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

    @property
    def bonus_points(self) -> int:
        return sum(self.bonuses.values())

    def save(self, path: str | Path) -> None:
        data = {
            "n3fjp_host": self.n3fjp_host,
            "n3fjp_port": self.n3fjp_port,
            "power_multiplier": self.power_multiplier,
            "bonuses": self.bonuses,
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
        )

    def to_public_dict(self) -> dict:
        """Shape consumed by the settings page."""
        d = asdict(self)
        d["bonus_points"] = self.bonus_points
        return d
