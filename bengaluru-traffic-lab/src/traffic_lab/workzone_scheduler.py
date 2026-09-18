"""Recommend maintenance/road-digging windows for a segment.

This is variable #2 from the brief: figure out when a zone is least
congested and schedule underground-wiring/road-cutting work accordingly,
while also respecting variable #4 (don't dig near a masjid on a Friday, or
near a temple on its festival day) and variable #3 (a segment that scored
as network-critical needs a stricter blackout policy than a quiet
residential lane, because closing it has knock-on effects elsewhere).

Honesty about data: there is no free, reliable, hour-by-hour congestion
feed for Bengaluru wired up here (see docs/RESEARCH.md — B-ATCS/CoSiCoSt
data isn't public, and BMTC has no official API). ``DEFAULT_TIME_PROFILE``
below is a generic placeholder (commute peaks 08:00-11:00 and 17:00-20:00)
that should be replaced with a real profile as soon as one is available —
e.g. derived from BMTC GTFS scheduled vs. actual bus speeds, from a paid
traffic-index API, or from manual counts for the specific zone. The
``TimeOfDayProfile`` protocol exists so swapping that in doesn't require
touching this module.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Iterable, Protocol

from .calendar_rules import Festival, RiskLevel, congestion_risk_for_date
from .landmarks import Landmark


class TimeOfDayProfile(Protocol):
    def is_low_traffic(self, hour: int) -> bool:
        """hour is 0-23, local time."""
        ...


@dataclass(frozen=True)
class GenericCommuteProfile:
    """Placeholder profile: flags typical two-peak commute congestion.

    Calibrate or replace this per zone once real speed/volume data exists.
    """

    morning_peak: tuple[int, int] = (8, 11)
    evening_peak: tuple[int, int] = (17, 20)

    def is_low_traffic(self, hour: int) -> bool:
        in_morning = self.morning_peak[0] <= hour < self.morning_peak[1]
        in_evening = self.evening_peak[0] <= hour < self.evening_peak[1]
        return not (in_morning or in_evening)


DEFAULT_TIME_PROFILE = GenericCommuteProfile()

CRITICALITY_TIER_THRESHOLDS = {
    # betweenness score cutoffs -> tier name; tune against the actual
    # network's score distribution rather than treating these as absolute.
    "arterial": 0.05,
    "collector": 0.01,
}


def criticality_tier(betweenness_score: float) -> str:
    if betweenness_score >= CRITICALITY_TIER_THRESHOLDS["arterial"]:
        return "arterial"
    if betweenness_score >= CRITICALITY_TIER_THRESHOLDS["collector"]:
        return "collector"
    return "local"


@dataclass(frozen=True)
class WorkWindowRecommendation:
    date: date
    tier: str
    allowed_hours: list[int]
    blackout: bool
    reasons: list[str] = field(default_factory=list)


def recommend_work_window(
    betweenness_score: float,
    date_: date,
    nearby_landmarks: Iterable[Landmark],
    festivals: list[Festival] | None = None,
    time_profile: TimeOfDayProfile = DEFAULT_TIME_PROFILE,
) -> WorkWindowRecommendation:
    tier = criticality_tier(betweenness_score)
    reasons: list[str] = [f"criticality tier: {tier}"]

    worst_risk = RiskLevel.NONE
    for landmark in nearby_landmarks:
        assessment = congestion_risk_for_date(landmark, date_, festivals)
        if assessment.reasons:
            reasons.extend(f"{landmark.name}: {r}" for r in assessment.reasons)
        if assessment.level.rank > worst_risk.rank:
            worst_risk = assessment.level

    # Blackout policy: an arterial/collector road near a landmark at
    # elevated-or-worse risk, or ANY road on an extreme-risk day (a
    # procession can close a local street it wouldn't otherwise touch).
    blackout = worst_risk == RiskLevel.EXTREME or (
        tier in ("arterial", "collector") and worst_risk.rank >= RiskLevel.ELEVATED.rank
    )

    if blackout:
        return WorkWindowRecommendation(date=date_, tier=tier, allowed_hours=[], blackout=True, reasons=reasons)

    if tier == "local" and worst_risk == RiskLevel.NONE:
        allowed_hours = list(range(6, 22))  # generous daytime window, low-stakes road
    else:
        allowed_hours = [h for h in range(0, 24) if time_profile.is_low_traffic(h)]

    return WorkWindowRecommendation(date=date_, tier=tier, allowed_hours=allowed_hours, blackout=False, reasons=reasons)
