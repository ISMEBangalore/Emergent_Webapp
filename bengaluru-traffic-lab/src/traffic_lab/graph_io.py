"""Load a road network into a networkx graph.

Three sources are supported, in order of preference:

1. A pre-fetched OSM extract saved as GraphML (``load_graphml``) — the
   recommended path, since it works offline and is reproducible.
2. A plain edge-list CSV (``load_edgelist_csv``) — for a hand-built or
   already-cleaned network with no OSM dependency at all.
3. A live fetch from OpenStreetMap via ``osmnx`` (``fetch_osm_graph``) —
   convenient for a first pass over a named place, but requires network
   access and an installed ``osmnx`` package, and results can shift as OSM
   data is edited. Cache the result with ``save_graphml`` and commit that
   file rather than re-fetching on every run.
"""
from __future__ import annotations

import csv
from pathlib import Path

import networkx as nx


def load_graphml(path: str | Path) -> nx.MultiDiGraph:
    return nx.read_graphml(path)


def save_graphml(graph: nx.Graph, path: str | Path) -> None:
    nx.write_graphml(graph, path)


def load_edgelist_csv(path: str | Path) -> nx.MultiDiGraph:
    """Build a graph from a CSV with columns: u,v,name,length_m,oneway.

    ``u``/``v`` are node ids (e.g. intersection names or OSM node ids).
    ``length_m`` is the segment length in metres, used as edge weight.
    ``oneway`` is "true"/"false"; when false an edge is added in both
    directions.
    """
    graph = nx.MultiDiGraph()
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            u, v = row["u"], row["v"]
            length = float(row.get("length_m", 1.0) or 1.0)
            name = row.get("name", f"{u}-{v}")
            graph.add_edge(u, v, name=name, length=length)
            if str(row.get("oneway", "false")).strip().lower() != "true":
                graph.add_edge(v, u, name=name, length=length)
    return graph


def fetch_osm_graph(place_name: str, network_type: str = "drive") -> nx.MultiDiGraph:
    """Fetch a drivable road network for a place from OpenStreetMap.

    Requires the optional ``osmnx`` dependency and outbound network access.
    Raises ImportError with a clear message if osmnx isn't installed.
    """
    try:
        import osmnx as ox
    except ImportError as exc:
        raise ImportError(
            "fetch_osm_graph requires the 'osmnx' package: pip install osmnx"
        ) from exc
    return ox.graph_from_place(place_name, network_type=network_type)
