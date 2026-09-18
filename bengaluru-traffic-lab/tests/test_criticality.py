import networkx as nx

from traffic_lab.criticality import compute_edge_betweenness, rank_critical_roads, removal_impact


def bowtie_graph() -> nx.MultiDiGraph:
    """Two triangle clusters joined by a single bridge edge.

    The bridge (C-D) must carry every cross-cluster shortest path, so it
    should score highest on betweenness and its removal should disconnect
    the network entirely.
    """
    g = nx.MultiDiGraph()
    edges = [
        ("A", "B", 1.0), ("B", "A", 1.0),
        ("B", "C", 1.0), ("C", "B", 1.0),
        ("A", "C", 1.0), ("C", "A", 1.0),
        ("C", "D", 1.0), ("D", "C", 1.0),  # the bridge
        ("D", "E", 1.0), ("E", "D", 1.0),
        ("E", "F", 1.0), ("F", "E", 1.0),
        ("D", "F", 1.0), ("F", "D", 1.0),
    ]
    for u, v, length in edges:
        g.add_edge(u, v, name=f"{u}-{v}", length=length)
    return g


def test_bridge_edge_has_highest_betweenness():
    g = bowtie_graph()
    scores = compute_edge_betweenness(g)
    bridge_key = tuple(sorted(("C", "D")))
    top_key = max(scores, key=scores.get)
    assert top_key == bridge_key


def test_rank_critical_roads_orders_bridge_first():
    g = bowtie_graph()
    ranked = rank_critical_roads(g, top_n=3)
    top = ranked[0]
    assert {top.u, top.v} == {"C", "D"}


def test_removal_of_bridge_disconnects_network():
    g = bowtie_graph()
    result = removal_impact(g, "C", "D")
    assert result["disconnects_network"] is True


def test_removal_of_redundant_edge_does_not_disconnect():
    g = bowtie_graph()
    result = removal_impact(g, "A", "B")
    assert result["disconnects_network"] is False
