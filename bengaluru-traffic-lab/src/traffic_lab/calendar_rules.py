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

Four more everyday (not just religious) congestion generators are tagged
the same way, as recurring-day "kinds" rather than one-off festival
dates, since they recur every school/work day rather than once a week:

- ``school`` — student drop-off/pickup queuing, term-time weekdays (and
  Saturday at many Bengaluru schools; verify per school's own calendar).
- ``it_park`` — staggered but concentrated shift-change traffic at IT
  campuses/tech corridors, Monday-Friday (varies with WFH/hybrid policy
  at a given company — verify before relying on this).
- ``truck_corridor`` — a point on a route where BBMP/Bengaluru Traffic
  Police heavy-goods-vehicle entry timing restrictions concentrate truck
  movement into a night/early-morning window; every day of the week.
  Verify the current restriction hours with Bengaluru Traffic Police
  before using this operationally — timing windows have changed
  historically and are not hardcoded here beyond the illustrative hourly
  shape in ``docs/google-map.html``.
- ``parking_zone`` — a commercial/market area whose on-street parking
  saturates during business hours, every day of the week.
"""
from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass, field
from enum import Enum

_ALL_DAYS = {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"}

WEEKLY_PEAK_DAYS: dict[str, set[str]] = {
    "masjid": {"Friday"},
    "hanuman_temple": {"Tuesday", "Saturday"},
    "shani_temple": {"Saturday"},
    "church": {"Sunday"},
    "gurdwara": {"Sunday"},
    "temple_generic": {"Friday"},  # common default for Devi/Amman temples; verify per-site
    "school": {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"},
    "it_park": {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday"},
    "truck_corridor": set(_ALL_DAYS),
    "parking_zone": set(_ALL_DAYS),
}

# Kind pairs whose congestion windows are known to conflict when the two
# landmarks sit close together on the same corridor — e.g. a school's
# morning drop-off competing with a heavy-vehicle entry corridor for the
# same road space. This is a proximity + shared-operating-day heuristic,
# not a measured traffic-volume interaction; it exists to surface WHERE a
# real turning-movement/volume study would be most worth commissioning
# (see ``apply_proximity_escalation`` below), not to replace one.
CONFLICT_KIND_PAIRS: dict[frozenset[str], str] = {
    frozenset({"school", "truck_corridor"}): (
        "Heavy-vehicle corridor within {distance_m:.0f}m of a school zone — "
        "morning drop-off and truck movement can overlap on the same road."
    ),
    frozenset({"school", "it_park"}): (
        "School pickup within {distance_m:.0f}m of an IT campus/tech corridor — "
        "afternoon pickup and shift-change traffic compete for the same arterial capacity."
    ),
    frozenset({"it_park", "parking_zone"}): (
        "IT commute corridor within {distance_m:.0f}m of a saturated parking/market zone — "
        "shift-change traffic and curb-parking search share the same road space."
    ),
    frozenset({"parking_zone", "truck_corridor"}): (
        "Loading/unloading corridor within {distance_m:.0f}m of a saturated parking zone — "
        "truck movement narrows already-scarce curb space."
    ),
}
CONFLICT_RADIUS_M = 1200.0


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


_RANK_TO_LEVEL = [RiskLevel.NONE, RiskLevel.ELEVATED, RiskLevel.HIGH, RiskLevel.EXTREME]


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in meters — adequate at city scale."""
    r = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def apply_proximity_escalation(
    landmark,
    assessment: RiskAssessment,
    date: dt.date,
    all_landmarks: list,
    radius_m: float = CONFLICT_RADIUS_M,
) -> RiskAssessment:
    """Bump ``assessment`` one severity tier when a geographically close
    landmark of a known-conflicting kind is also active (its own weekly
    peak day) on the same date.

    This is the "scientific analysis" version of the same idea festivals
    already use for escalation — proximity (haversine distance) and a
    shared active day stand in for the turning-movement/volume interaction
    a real study would measure — not a substitute for one. Two independent
    single-cause "elevated" days becoming a "high" conflict day is the
    signal this function exists to surface, not a claim about an actual
    measured volume increase.
    """
    weekday_name = date.strftime("%A")
    reasons = list(assessment.reasons)
    level = assessment.level

    for other in all_landmarks:
        if other is landmark or other.kind == landmark.kind:
            continue
        pair_key = frozenset({landmark.kind, other.kind})
        template = CONFLICT_KIND_PAIRS.get(pair_key)
        if template is None:
            continue
        if weekday_name not in WEEKLY_PEAK_DAYS.get(other.kind, set()):
            continue
        distance_m = haversine_m(landmark.lat, landmark.lon, other.lat, other.lon)
        if distance_m > radius_m:
            continue
        escalated_rank = min(level.rank + 1, RiskLevel.EXTREME.rank)
        level = _RANK_TO_LEVEL[escalated_rank]
        reasons.append(
            "Conflict: " + template.format(distance_m=distance_m) + f" ({other.name})"
        )

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
