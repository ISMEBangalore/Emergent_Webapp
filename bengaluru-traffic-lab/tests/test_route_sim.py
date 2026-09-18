import pytest

from traffic_lab.road_network import EDGES, NODES, edge_by_id
from traffic_lab.route_sim import RoadChange, shortest_route, simulate, total_network_travel_time_veh_hours


def _base_states():
    from traffic_lab.route_sim import _apply_changes

    return _apply_changes(EDGES, [])


def test_all_edge_endpoints_are_known_nodes():
    node_ids = {n.id for n in NODES}
    for edge in EDGES:
        assert edge.u in node_ids, f"{edge.id} references unknown node {edge.u!r}"
        assert edge.v in node_ids, f"{edge.id} references unknown node {edge.v!r}"


def test_reroute_alternates_reference_real_edges():
    edge_ids = {e.id for e in EDGES}
    for edge in EDGES:
        for alt in edge.reroute_alternates:
            assert alt in edge_ids, f"{edge.id} references unknown alternate {alt!r}"


def test_shortest_route_finds_a_path_between_distant_nodes():
    states = _base_states()
    route = shortest_route(states, "electronic_city", "hebbal")
    assert route.path_node_ids[0] == "electronic_city"
    assert route.path_node_ids[-1] == "hebbal"
    assert route.total_time_s > 0
    assert route.total_length_m > 0


def test_widening_the_route_bottleneck_reduces_its_own_travel_time():
    comparison = simulate(
        source="electronic_city",
        target="marathahalli",
        changes=[RoadChange(edge_id="e_silkboard_marathahalli", lanes=10)],
    )
    if "e_silkboard_marathahalli" in comparison.before.path_edge_ids:
        assert comparison.travel_time_pct_change < 0


def test_resurfacing_never_makes_the_route_slower():
    comparison = simulate(
        source="majestic",
        target="whitefield",
        changes=[RoadChange(edge_id="e_krpuram_hebbal", pavement="excellent")],
    )
    assert comparison.travel_time_pct_change <= 0


def test_reroute_fraction_sheds_volume_from_source_and_adds_to_alternates():
    before_states = _base_states()
    edge = edge_by_id("e_silkboard_marathahalli")
    from traffic_lab.route_sim import _apply_changes

    after_states = _apply_changes(EDGES, [RoadChange(edge_id=edge.id, reroute_fraction=0.5)])

    assert after_states[edge.id].effective_volume_vph == pytest.approx(edge.base_volume_vph * 0.5)
    for alt_id in edge.reroute_alternates:
        alt_edge = edge_by_id(alt_id)
        expected_added = (edge.base_volume_vph * 0.5) / len(edge.reroute_alternates)
        assert after_states[alt_id].effective_volume_vph == pytest.approx(alt_edge.base_volume_vph + expected_added)


def test_reroute_without_alternates_raises():
    from traffic_lab.route_sim import _apply_changes

    # e_hebbal_yeshwanthpur has no reroute_alternates defined.
    with pytest.raises(ValueError):
        _apply_changes(EDGES, [RoadChange(edge_id="e_hebbal_yeshwanthpur", reroute_fraction=0.3)])


def test_total_network_travel_time_is_positive_and_finite():
    states = _base_states()
    total = total_network_travel_time_veh_hours(states)
    assert total > 0
    assert total < 1_000_000  # sanity bound, not a precise assertion
