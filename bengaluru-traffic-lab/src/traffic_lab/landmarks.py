"""Religious/congregational landmarks that drive predictable local surges.

This is variable #4 from the brief: temples, mosques, churches, and
gurdwaras all draw recurring crowds on specific weekdays and specific
festival dates, and the roads around them need capacity planning for those
windows, not for a citywide average.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Landmark:
    name: str
    kind: str  # e.g. "hanuman_temple", "shani_temple", "masjid", "church", "gurdwara", "temple_generic"
    lat: float
    lon: float
    radius_m: float = 500.0
    nearby_road_names: tuple[str, ...] = ()


def load_landmarks(path: str | Path) -> list[Landmark]:
    landmarks = []
    with open(path, newline="", encoding="utf-8") as f:
        lines = (line for line in f if not line.lstrip().startswith("#"))
        for row in csv.DictReader(lines):
            roads = tuple(r.strip() for r in row.get("nearby_road_names", "").split("|") if r.strip())
            landmarks.append(
                Landmark(
                    name=row["name"],
                    kind=row["kind"],
                    lat=float(row["lat"]),
                    lon=float(row["lon"]),
                    radius_m=float(row.get("radius_m", 500.0) or 500.0),
                    nearby_road_names=roads,
                )
            )
    return landmarks
