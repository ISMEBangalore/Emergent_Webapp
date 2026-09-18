import datetime as dt

from traffic_lab.calendar_rules import Festival, RiskLevel, congestion_risk_for_date, upcoming_high_risk_days
from traffic_lab.landmarks import Landmark


def make_landmark(kind: str) -> Landmark:
    return Landmark(name=f"Test {kind}", kind=kind, lat=12.97, lon=77.59)


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
