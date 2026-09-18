import pytest

from traffic_lab.bpr import bpr_travel_time_s, evaluate_segment, free_flow_time_s, volume_capacity_ratio


def test_free_flow_time_basic():
    # 36 km/h = 10 m/s, so 1000m should take 100s at free flow.
    assert free_flow_time_s(1000, 36) == pytest.approx(100.0)


def test_free_flow_time_rejects_nonpositive_speed():
    with pytest.raises(ValueError):
        free_flow_time_s(1000, 0)


def test_volume_capacity_ratio():
    assert volume_capacity_ratio(1800, 1, lane_capacity_vph=1800) == pytest.approx(1.0)
    assert volume_capacity_ratio(3600, 2, lane_capacity_vph=1800) == pytest.approx(1.0)


def test_bpr_travel_time_at_zero_volume_equals_free_flow():
    tt = bpr_travel_time_s(1000, 36, lanes=2, volume_vph=0)
    assert tt == pytest.approx(free_flow_time_s(1000, 36))


def test_bpr_travel_time_at_capacity_matches_standard_15pct_delay():
    # At v/c == 1, BPR gives travel_time = free_flow_time * 1.15 with defaults.
    tt = bpr_travel_time_s(1000, 36, lanes=1, volume_vph=1800, lane_capacity_vph=1800)
    assert tt == pytest.approx(free_flow_time_s(1000, 36) * 1.15)


def test_bpr_travel_time_increases_with_volume():
    low = bpr_travel_time_s(1000, 36, lanes=2, volume_vph=1000)
    high = bpr_travel_time_s(1000, 36, lanes=2, volume_vph=3000)
    assert high > low


def test_bpr_travel_time_decreases_with_more_lanes_same_volume():
    narrow = bpr_travel_time_s(1000, 36, lanes=2, volume_vph=3000)
    wide = bpr_travel_time_s(1000, 36, lanes=4, volume_vph=3000)
    assert wide < narrow


def test_bpr_travel_time_decreases_with_higher_free_flow_speed():
    slow = bpr_travel_time_s(1000, 30, lanes=2, volume_vph=2000)
    fast = bpr_travel_time_s(1000, 45, lanes=2, volume_vph=2000)
    assert fast < slow


def test_evaluate_segment_delay_is_travel_time_minus_free_flow():
    result = evaluate_segment(1000, 36, lanes=2, volume_vph=2500)
    assert result.delay_s == pytest.approx(result.travel_time_s - result.free_flow_time_s)
    assert result.delay_s > 0
