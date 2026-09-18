import datetime as dt

from traffic_lab.calendar_rules import (
    Festival,
    RiskLevel,
    apply_proximity_escalation,
    congestion_risk_for_date,
    haversine_m,
    upcoming_high_risk_days,
)
from traffic_lab.landmarks import Landmark


def make_landmark(kind: str, lat: float = 12.97, lon: float = 77.59, name: str | None = None) -> Landmark:
    return Landmark(name=name or f"Test {kind}", kind=kind, lat=lat, lon=lon)


def test_masjid_flagged_on_friday_not_thursday():
    landmark = make_landmark("masjid")
    friday = dt.date(2026, 9, 18)  # confirmed Friday
    thursday = friday - dt.timedelta(days=1)

    assert friday.strftime("%A") == "Friday"
    assert congestion_risk_for_date(landmark, friday).level == RiskLevel.ELEVATED
    assert congestion_risk_for_date(landmark, thursday).level == RiskLevel.NONE


def test_hanuman_temple_flagged_tuesday_and_saturday():
    landmark = make_landmark("hanuman_temple")
    tuesday = dt.date(2026, 9, 22)
    saturday = dt.date(2026, 9, 26)
    sunday = dt.date(2026, 9, 27)

    assert tuesday.strftime("%A") == "Tuesday"
    assert saturday.strftime("%A") == "Saturday"
    assert sunday.strftime("%A") == "Sunday"

    assert congestion_risk_for_date(landmark, tuesday).level == RiskLevel.ELEVATED
    assert congestion_risk_for_date(landmark, saturday).level == RiskLevel.ELEVATED
    assert congestion_risk_for_date(landmark, sunday).level == RiskLevel.NONE


def test_festival_overrides_weekly_baseline_with_higher_severity():
    landmark = make_landmark("temple_generic")
    festival_day = dt.date(2026, 9, 20)  # a Sunday, not a weekly peak day for temple_generic
    festival = Festival(
        name="Car Festival",
        start_date=festival_day,
        end_date=festival_day,
        severity=RiskLevel.EXTREME,
        affected_kinds=("temple_generic",),
    )

    assessment = congestion_risk_for_date(landmark, festival_day, [festival])
    assert assessment.level == RiskLevel.EXTREME
    assert any("Car Festival" in r for r in assessment.reasons)


def test_festival_does_not_apply_to_unrelated_kind():
    landmark = make_landmark("church")
    festival_day = dt.date(2026, 9, 21)  # a Monday: not the church's weekly peak day
    assert festival_day.strftime("%A") == "Monday"
    festival = Festival(
        name="Masjid-only event",
        start_date=festival_day,
        end_date=festival_day,
        severity=RiskLevel.EXTREME,
        affected_kinds=("masjid",),
    )
    assessment = congestion_risk_for_date(landmark, festival_day, [festival])
    assert assessment.level == RiskLevel.NONE


def test_upcoming_high_risk_days_filters_by_min_level():
    landmarks = [make_landmark("masjid"), make_landmark("hanuman_temple")]
    start = dt.date(2026, 9, 18)  # Friday
    hits = upcoming_high_risk_days(landmarks, [], start, days=7, min_level=RiskLevel.ELEVATED)
    # Over 7 days we expect: masjid on the one Friday, hanuman on Tue+Sat
    assert len(hits) == 3
    assert all(h[2].level == RiskLevel.ELEVATED for h in hits)


def test_school_flagged_weekdays_and_saturday_not_sunday():
    landmark = make_landmark("school")
    saturday = dt.date(2026, 9, 19)
    sunday = dt.date(2026, 9, 20)
    assert congestion_risk_for_date(landmark, saturday).level == RiskLevel.ELEVATED
    assert congestion_risk_for_date(landmark, sunday).level == RiskLevel.NONE


def test_it_park_flagged_weekdays_not_weekend():
    landmark = make_landmark("it_park")
    friday = dt.date(2026, 9, 18)
    saturday = dt.date(2026, 9, 19)
    assert congestion_risk_for_date(landmark, friday).level == RiskLevel.ELEVATED
    assert congestion_risk_for_date(landmark, saturday).level == RiskLevel.NONE


def test_truck_corridor_and_parking_zone_flagged_every_day():
    truck = make_landmark("truck_corridor")
    parking = make_landmark("parking_zone")
    for offset in range(7):
        date = dt.date(2026, 9, 18) + dt.timedelta(days=offset)
        assert congestion_risk_for_date(truck, date).level == RiskLevel.ELEVATED
        assert congestion_risk_for_date(parking, date).level == RiskLevel.ELEVATED


def test_haversine_m_known_distance():
    # Roughly 1 degree of longitude at the equator is ~111.3km.
    distance = haversine_m(0.0, 0.0, 0.0, 1.0)
    assert 110_000 < distance < 112_000


def test_proximity_escalation_bumps_severity_when_close_and_both_active():
    school = make_landmark("school", lat=12.9000, lon=77.6000, name="Test school")
    truck = make_landmark("truck_corridor", lat=12.9005, lon=77.6005, name="Test truck corridor")  # ~70m away
    monday = dt.date(2026, 9, 21)
    assert monday.strftime("%A") == "Monday"

    base = congestion_risk_for_date(school, monday)
    assert base.level == RiskLevel.ELEVATED  # school's own weekday peak, no conflict yet

    escalated = apply_proximity_escalation(school, base, monday, [school, truck])
    assert escalated.level == RiskLevel.HIGH
    assert any("Conflict" in r and "Test truck corridor" in r for r in escalated.reasons)


def test_proximity_escalation_ignores_distant_or_unrelated_kinds():
    school = make_landmark("school", lat=12.9000, lon=77.6000, name="Test school")
    far_truck = make_landmark("truck_corridor", lat=13.1000, lon=77.8000, name="Far truck corridor")
    nearby_temple = make_landmark("temple_generic", lat=12.9003, lon=77.6003, name="Nearby temple")
    monday = dt.date(2026, 9, 21)

    base = congestion_risk_for_date(school, monday)
    escalated = apply_proximity_escalation(school, base, monday, [school, far_truck, nearby_temple])
    assert escalated.level == base.level
    assert escalated.reasons == base.reasons
