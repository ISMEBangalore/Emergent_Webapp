"""Recurring-weekday and festival-date congestion rules for landmarks.

Two independent layers feed into a single risk score for a given landmark
on a given date:

1. **Weekly rules** — the same weekday, every week, tied to the landmark's
   ``kind`` (Friday Jumu'ah at a masjid, Tuesday/Saturday at a Hanuman
   temple, Saturday at a Shani temple, Sunday mass at a church, and so on).
   These are the easy, always-on part of variable #4 and cost nothing to
   apply once a landmark is tagged with a kind.
2. **Festival dates** — one-off or annual dates (Ganesh Chaturthi
   immersion, Karaga, Eid, Christmas Eve/midnight mass, temple car
   festivals/"rathotsava") that spike far above the weekly baseline and
   often bring processions that shut roads outright, not just slow them.
   Because most Hindu/Islamic festival dates follow lunar calendars, this
   module does NOT hardcode future dates — it takes a caller-supplied
   ``Festival`` list (see data/festivals.sample.yaml) that should be
   refreshed each year from an authoritative calendar.

The weekly table below is a starting point, not settled fact — local
practice varies by specific temple/mosque, and some sites observe more
than one peak day (e.g., a temple that is both a Hanuman and Shani site).
Treat ``WEEKLY_PEAK_DAYS`` as configuration to verify against the actual
landmarks in ``data/landmarks.sample.csv``, not a universal rule.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from enum import Enum

WEEKLY_PEAK_DAYS: dict[str, set[str]] = {
    "masjid": {"Friday"},
    "hanuman_temple": {"Tuesday", "Saturday"},
    "shani_temple": {"Saturday"},
    "church": {"Sunday"},
    "gurdwara": {"Sunday"},
    "temple_generic": {"Friday"},  # common default for Devi/Amman temples; verify per-site
}


class RiskLevel(str, Enum):
    NONE = "none"
    ELEVATED = "elevated"  # weekly peak day
    HIGH = "high"  # festival, moderate/high severity
    EXTREME = "extreme"  # festival, extreme severity (processions, immersion, etc.)

    @property
    def rank(self) -> int:
        return {"none": 0, "elevated": 1, "high": 2, "extreme": 3}[self.value]


@dataclass(frozen=True)
class Festival:
    name: str
    start_date: dt.date
    end_date: dt.date
    severity: RiskLevel
    affected_kinds: tuple[str, ...] = ()
    affected_names: tuple[str, ...] = ()
    note: str = ""

    def covers(self, date: dt.date) -> bool:
        return self.start_date <= date <= self.end_date

    def applies_to(self, landmark_name: str, landmark_kind: str) -> bool:
        if not self.affected_kinds and not self.affected_names:
            return True  # citywide (e.g. a general holiday surge)
        return landmark_kind in self.affected_kinds or landmark_name in self.affected_names


@dataclass(frozen=True)
class RiskAssessment:
    level: RiskLevel
    reasons: list[str] = field(default_factory=list)


def congestion_risk_for_date(landmark, date: dt.date, festivals: list[Festival] | None = None) -> RiskAssessment:
    reasons: list[str] = []
    level = RiskLevel.NONE

    weekday_name = date.strftime("%A")
    if weekday_name in WEEKLY_PEAK_DAYS.get(landmark.kind, set()):
        level = RiskLevel.ELEVATED
        reasons.append(f"Weekly peak day for {landmark.kind} ({weekday_name})")

    for festival in festivals or []:
        if festival.covers(date) and festival.applies_to(landmark.name, landmark.kind):
            if festival.severity.rank > level.rank:
                level = festival.severity
            reasons.append(f"{festival.name} ({festival.severity.value})" + (f" — {festival.note}" if festival.note else ""))

    return RiskAssessment(level=level, reasons=reasons)


def upcoming_high_risk_days(
    landmarks: list,
    festivals: list[Festival],
    start_date: dt.date,
    days: int = 30,
    min_level: RiskLevel = RiskLevel.ELEVATED,
) -> list[tuple[dt.date, object, RiskAssessment]]:
    """Scan a date window and return every (date, landmark, assessment) hit
    at or above ``min_level`` — the list a work-scheduling tool should
    avoid, and the list a traffic-police roster should staff up for.
    """
    results = []
    for offset in range(days):
        date = start_date + dt.timedelta(days=offset)
        for landmark in landmarks:
            assessment = congestion_risk_for_date(landmark, date, festivals)
            if assessment.level.rank >= min_level.rank:
                results.append((date, landmark, assessment))
    return results
