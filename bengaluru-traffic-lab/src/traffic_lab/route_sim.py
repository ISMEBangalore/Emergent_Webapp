"""Route a car across the illustrative road_network.py skeleton, and
simulate the effect of infrastructure changes (widening, resurfacing,
festival rerouting) on travel time — this is variable #1/#2 territory
from the original brief, using the BPR heuristic (bpr.py) in place of a
calibrated microsimulation (SUMO), which docs/RESEARCH.md flags as
needing real calibration data this project doesn't have.

Scope, stated plainly: this recomputes travel time on the SAME shortest
path (by current BPR time) before and after a change, plus a
network-wide total-travel-time figure (sum of edge BPR time * edge
volume, i.e. total vehicle-hours across the loaded skeleton) as a proxy
for "does this help overall or just move the jam" — it does NOT run a
real traffic assignment/equilibrium (drivers re-choosing routes
network-wide), only whatever explicit reroute the caller applies via
``RoadChange.reroute_to``. Treat results as directional and educational,
not as a validated volume forecast.
"""
from __future__ import annotations

from dataclasses import dataclass

import networkx as nx

from .bpr import evaluate_segment
from .road_network import EDGES, NODES, RoadEdge, edge_by_id

PAVEMENT_SPEED_MULTIPLIER = {
    "poor": 0.7,   # potholed / unmaintained
    "fair": 0.85,
    "good": 1.0,   # current baseline for every sample edge
    "excellent": 1.15,  # resurfaced with better materials, modest realistic gain
}


@dataclass(frozen=True)
class RoadChange:
    edge_id: str
    lanes: int | None = None  # widen/narrow; None = unchanged
    pavement: str | None = None  # key into PAVEMENT_SPEED_MULTIPLIER; None = unchanged ("good")
    reroute_fraction: float = 0.0  # 0..1 of this edge's volume diverted away (festival rerouting)


@dataclass(frozen=True)
class EdgeState:
    edge: RoadEdge
    effective_lanes: int
    effective_free_flow_kmh: float
    effective_volume_vph: float
    result: object  # bpr.SegmentResult


def _apply_changes(edges: list[RoadEdge], changes: list[RoadChange]) -> dict[str, EdgeState]:
    changes_by_edge = {c.edge_id: c for c in changes}
    # First pass: compute each edge's own lane/pavement overrides and how
    # much volume it sheds via reroute_fraction.
    volume_by_edge = {e.id: e.base_volume_vph for e in edges}
    shed_by_edge = {e.id: 0.0 for e in edges}
    for change in changes:
        if change.reroute_fraction > 0:
            edge = edge_by_id(change.edge_id)
            shed = edge.base_volume_vph * min(max(change.reroute_fraction, 0.0), 1.0)
            shed_by_edge[change.edge_id] += shed
            volume_by_edge[change.edge_id] -= shed
            if not edge.reroute_alternates:
                raise ValueError(f"edge {change.edge_id!r} has no reroute_alternates to divert onto")
            per_alt = shed / len(edge.reroute_alternates)
            for alt_id in edge.reroute_alternates:
                volume_by_edge[alt_id] = volume_by_edge.get(alt_id, edge_by_id(alt_id).base_volume_vph) + per_alt

    states: dict[str, EdgeState] = {}
    for edge in edges:
        change = changes_by_edge.get(edge.id)
        lanes = change.lanes if (change and change.lanes) else edge.lanes
        pavement_key = (change.pavement if change else None) or "good"
        multiplier = PAVEMENT_SPEED_MULTIPLIER[pavement_key]
        free_flow_kmh = edge.free_flow_kmh * multiplier
        volume_vph = volume_by_edge[edge.id]
        result = evaluate_segment(edge.length_m, free_flow_kmh, lanes, volume_vph)
        states[edge.id] = EdgeState(edge, lanes, free_flow_kmh, volume_vph, result)
    return states


def build_graph(edge_states: dict[str, EdgeState]) -> nx.Graph:
    g = nx.Graph()
    for node in NODES:
        g.add_node(node.id)
    for edge_id, state in edge_states.items():
        g.add_edge(state.edge.u, state.edge.v, edge_id=edge_id, weight=state.result.travel_time_s)
    return g


@dataclass(frozen=True)
class RouteResult:
    path_node_ids: list[str]
    path_edge_ids: list[str]
    total_time_s: float
    total_length_m: float


def shortest_route(edge_states: dict[str, EdgeState], source: str, target: str) -> RouteResult:
    graph = build_graph(edge_states)
    path = nx.dijkstra_path(graph, source, target, weight="weight")
    edge_ids = [graph.edges[path[i], path[i + 1]]["edge_id"] for i in range(len(path) - 1)]
    total_time = sum(edge_states[eid].result.travel_time_s for eid in edge_ids)
    total_length = sum(edge_states[eid].edge.length_m for eid in edge_ids)
    return RouteResult(path_node_ids=path, path_edge_ids=edge_ids, total_time_s=total_time, total_length_m=total_length)


def total_network_travel_time_veh_hours(edge_states: dict[str, EdgeState]) -> float:
    """Sum of (edge travel time x edge volume) across the whole skeleton,
    in vehicle-hours — a coarse "total system delay" proxy, NOT a real
    network equilibrium recomputation. Rises if a change helps one route
    but pushes enough volume elsewhere to make the network worse overall.
    """
    total_veh_seconds = sum(s.result.travel_time_s * s.effective_volume_vph for s in edge_states.values())
    return total_veh_seconds / 3600.0


@dataclass(frozen=True)
class SimulationComparison:
    before: RouteResult
    after: RouteResult
    before_states: dict[str, EdgeState]
    after_states: dict[str, EdgeState]
    travel_time_pct_change: float  # negative = faster
    delay_change_s: float
    network_travel_time_before_veh_hours: float
    network_travel_time_after_veh_hours: float
    network_travel_time_pct_change: float


def simulate(source: str, target: str, changes: list[RoadChange]) -> SimulationComparison:
    before_states = _apply_changes(EDGES, [])
    after_states = _apply_changes(EDGES, changes)

    before = shortest_route(before_states, source, target)
    after = shortest_route(after_states, source, target)

    pct = ((after.total_time_s - before.total_time_s) / before.total_time_s) * 100.0 if before.total_time_s else 0.0
    delay_change = after.total_time_s - before.total_time_s

    net_before = total_network_travel_time_veh_hours(before_states)
    net_after = total_network_travel_time_veh_hours(after_states)
    net_pct = ((net_after - net_before) / net_before) * 100.0 if net_before else 0.0

    return SimulationComparison(
        before=before,
        after=after,
        before_states=before_states,
        after_states=after_states,
        travel_time_pct_change=pct,
        delay_change_s=delay_change,
        network_travel_time_before_veh_hours=net_before,
        network_travel_time_after_veh_hours=net_after,
        network_travel_time_pct_change=net_pct,
    )
