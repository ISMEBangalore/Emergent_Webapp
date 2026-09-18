import datetime as dt

from traffic_lab.landmarks import Landmark
from traffic_lab.workzone_scheduler import criticality_tier, recommend_work_window


def test_criticality_tier_thresholds():
    assert criticality_tier(0.2) == "arterial"
    assert criticality_tier(0.02) == "collector"
    assert criticality_tier(0.001) == "local"


def test_quiet_local_road_no_landmark_gets_wide_daytime_window():
    rec = recommend_work_window(
        betweenness_score=0.001,
        date_=dt.date(2026, 9, 21),  # a Monday, no weekly peak days nearby
        nearby_landmarks=[],
    )
    assert rec.blackout is False
    assert rec.tier == "local"
    assert 10 in rec.allowed_hours  # generous daytime window granted


def test_arterial_road_near_masjid_on_friday_is_blacked_out():
    masjid = Landmark(name="Test Masjid", kind="masjid", lat=12.97, lon=77.59)
    rec = recommend_work_window(
        betweenness_score=0.2,  # arterial tier
        date_=dt.date(2026, 9, 18),  # Friday
        nearby_landmarks=[masjid],
    )
    assert rec.blackout is True
    assert rec.allowed_hours == []


def test_arterial_road_on_a_quiet_weekday_restricts_to_off_peak_hours():
    rec = recommend_work_window(
        betweenness_score=0.2,
        date_=dt.date(2026, 9, 21),  # Monday, no landmark risk
        nearby_landmarks=[],
    )
    assert rec.blackout is False
    assert 9 not in rec.allowed_hours  # inside default morning peak
    assert 2 in rec.allowed_hours  # off-peak night hour allowed
