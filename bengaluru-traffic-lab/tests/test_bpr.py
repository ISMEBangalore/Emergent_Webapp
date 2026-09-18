import pytest

from traffic_lab.bpr import (
    DEFAULT_VEHICLE_MIX,
    PCU_FACTORS,
    bpr_travel_time_s,
    evaluate_segment,
    free_flow_time_s,
    level_of_service,
    pcu_volume,
    volume_capacity_ratio,
)


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


def test_evaluate_segment_without_vehicle_mix_uses_raw_volume():
    result = evaluate_segment(1000, 36, lanes=2, volume_vph=2500)
    assert result.volume_effective == pytest.approx(2500)


def test_pcu_volume_all_cars_is_unchanged():
    assert pcu_volume(1000, {"car": 1.0}) == pytest.approx(1000)


def test_pcu_volume_mixed_traffic_is_lower_than_raw_count_for_two_wheeler_heavy_mix():
    # A two-wheeler-heavy mix should reduce the PCU-equivalent volume
    # below the raw vehicle count, since two-wheelers count as < 1 PCU.
    mix = {"two_wheeler": 0.8, "auto_rickshaw": 0.1, "car": 0.1, "bus_truck": 0.0}
    pcu = pcu_volume(1000, mix)
    assert pcu < 1000
    assert pcu == pytest.approx(1000 * (0.8 * 0.5 + 0.1 * 0.8 + 0.1 * 1.0))


def test_pcu_volume_bus_heavy_mix_can_exceed_raw_count():
    mix = {"two_wheeler": 0.0, "auto_rickshaw": 0.0, "car": 0.2, "bus_truck": 0.8}
    pcu = pcu_volume(1000, mix)
    assert pcu > 1000  # buses/trucks count as 3 PCU each, so a bus-heavy stream uses more effective capacity


def test_pcu_volume_rejects_fractions_not_summing_to_one():
    with pytest.raises(ValueError):
        pcu_volume(1000, {"car": 0.5, "two_wheeler": 0.2})


def test_pcu_volume_rejects_unknown_vehicle_type():
    with pytest.raises(ValueError):
        pcu_volume(1000, {"car": 0.5, "spaceship": 0.5})


def test_default_vehicle_mix_fractions_sum_to_one():
    assert sum(DEFAULT_VEHICLE_MIX.values()) == pytest.approx(1.0)


def test_default_vehicle_mix_only_uses_known_pcu_factors():
    assert set(DEFAULT_VEHICLE_MIX) <= set(PCU_FACTORS)


def test_evaluate_segment_with_two_wheeler_heavy_mix_reduces_vc_ratio_vs_raw_count():
    mix = {"two_wheeler": 0.8, "auto_rickshaw": 0.1, "car": 0.1, "bus_truck": 0.0}
    raw = evaluate_segment(1000, 36, lanes=2, volume_vph=3000)
    pcu_adjusted = evaluate_segment(1000, 36, lanes=2, volume_vph=3000, vehicle_mix=mix)
    assert pcu_adjusted.volume_capacity_ratio < raw.volume_capacity_ratio
    assert pcu_adjusted.travel_time_s < raw.travel_time_s


def test_level_of_service_grades_match_expected_boundaries():
    assert level_of_service(0.10) == "A"
    assert level_of_service(0.40) == "B"
    assert level_of_service(0.60) == "C"
    assert level_of_service(0.80) == "D"
    assert level_of_service(0.95) == "E"
    assert level_of_service(1.20) == "F"


def test_level_of_service_is_monotonically_non_improving_with_higher_vc():
    ratios = [0.1, 0.3, 0.5, 0.7, 0.9, 1.1, 1.5]
    grades = [level_of_service(r) for r in ratios]
    order = "ABCDEF"
    grade_ranks = [order.index(g) for g in grades]
    assert grade_ranks == sorted(grade_ranks)


def test_evaluate_segment_exposes_los():
    result = evaluate_segment(1000, 36, lanes=1, volume_vph=1800, lane_capacity_vph=1800)
    assert result.los == level_of_service(result.volume_capacity_ratio)
