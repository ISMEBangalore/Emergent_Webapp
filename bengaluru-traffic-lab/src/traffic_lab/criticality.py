"""Rank road segments by how much a jam there would hurt the wider network.

This is variable #3 from the brief: "identify critical roads which, if
blocked, would create huge jams on main roads, so maintenance of those
roads can be prioritised."

The approach is standard in transportation-network-resilience literature
(see docs/RESEARCH.md for citations): rank edges by betweenness centrality
(how often they sit on shortest paths between other points), then confirm
the top candidates by actually simulating their removal and measuring how
much worse the network gets. Betweenness is a fast screen; removal-impact
is the expensive-but-trustworthy check, so only run it on the top-N
shortlist rather than on every edge.
"""
from __future__ import annotations

from dataclasses import dataclass

import networkx as nx


@dataclass(frozen=True)
class RoadScore:
    u: str
    v: str
    name: str
    betweenness: float


def compute_edge_betweenness(graph: nx.Graph, weight: str = "length") -> dict:
    """Edge betweenness centrality, keyed by (u, v) — direction-collapsed.

    Parallel edges between the same pair (common in MultiDiGraphs from OSM)
    are summed so a road doesn't get split across duplicate scores.
    """
    raw = nx.edge_betweenness_centrality(nx.DiGraph(graph), weight=weight)
    collapsed: dict[tuple, float] = {}
    for (u, v), score in raw.items():
        key = tuple(sorted((u, v)))
        collapsed[key] = collapsed.get(key, 0.0) + score
    return collapsed


def _edge_name(graph: nx.Graph, u: str, v: str) -> str:
    data = graph.get_edge_data(u, v) or graph.get_edge_data(v, u) or {}
    if isinstance(data, dict) and "name" in data:
        return data["name"]
    if isinstance(data, dict):
        first = next(iter(data.values()), {})
        if isinstance(first, dict):
            return first.get("name", f"{u}-{v}")
    return f"{u}-{v}"


def rank_critical_roads(graph: nx.Graph, top_n: int = 20, weight: str = "length") -> list[RoadScore]:
    scores = compute_edge_betweenness(graph, weight=weight)
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:top_n]
    return [RoadScore(u=u, v=v, name=_edge_name(graph, u, v), betweenness=score) for (u, v), score in ranked]


def removal_impact(graph: nx.Graph, u: str, v: str, weight: str = "length") -> dict:
    """Simulate closing the road segment between u and v.

    Returns the change in average shortest-path length across the largest
    remaining component, plus whether the removal disconnects the network.
    A large jump (or a disconnect) confirms the segment is a true
    single-point-of-failure worth prioritising for maintenance, drainage
    work, or a service-road/alternate-route plan — not just an artifact of
    the betweenness ranking.
    """
    before = nx.DiGraph(graph)
    baseline = _avg_shortest_path(before, weight)

    after = before.copy()
    removed_edges = [(a, b) for a, b in [(u, v), (v, u)] if after.has_edge(a, b)]
    for a, b in removed_edges:
        after.remove_edge(a, b)

    disconnected = not nx.is_strongly_connected(after) and nx.is_strongly_connected(before)
    after_score = _avg_shortest_path(after, weight)

    # When removal disconnects the network, "after" is only measured within
    # whatever fragment remains largest — that number is not comparable to
    # the pre-removal, whole-network baseline, so don't compute a delta from
    # it (a smaller isolated fragment can have a *shorter* average path,
    # which would misleadingly read as an improvement).
    delta = None if (baseline is None or after_score is None or disconnected) else after_score - baseline
    return {
        "baseline_avg_path": baseline,
        "after_removal_avg_path": after_score,
        "delta": delta,
        "disconnects_network": disconnected,
    }


def _avg_shortest_path(graph: nx.DiGraph, weight: str) -> float | None:
    if graph.number_of_nodes() < 2:
        return None
    if nx.is_strongly_connected(graph):
        return nx.average_shortest_path_length(graph, weight=weight)
    # Network already fragmented (or became fragmented by a removal): score
    # the largest strongly connected component so the metric stays defined,
    # since "disconnected" is already flagged separately by the caller.
    largest = max(nx.strongly_connected_components(graph), key=len)
    if len(largest) < 2:
        return None
    sub = graph.subgraph(largest)
    return nx.average_shortest_path_length(sub, weight=weight)
