"""An illustrative arterial-road skeleton for Bengaluru.

SAMPLE DATA — same honesty framing as data/landmarks.sample.csv and
data/sample_network.csv. Live OpenStreetMap/Overpass fetching wasn't
reachable from this project's dev environment, so this is a hand-built
skeleton of ~20 major junctions/localities and ~30 arterial/collector
corridors between them, built from general knowledge of Bengaluru's road
layout (ORR, Hosur Road, Bellary Road, Tumkur Road, etc.) — NOT surveyed,
NOT full street-level OSM detail, and coordinates/lengths/lane counts are
approximate. Verify against a real network export (see graph_io.py's
osmnx-based fetcher, or a GraphML/edge-list export you supply) before
using this for anything operational.

``lanes`` is the combined total across both directions (kept simple,
consistent with the rest of this project's directionless-corridor
modeling). ``tier`` reuses workzone_scheduler.py's "arterial"/"collector"
naming. ``base_volume_vph`` is an illustrative TYPICAL peak-hour volume,
picked as a fraction of the segment's nominal capacity (lanes * a
standard per-lane capacity — see bpr.py) rather than a measured count;
arterial segments are deliberately set close to (Silk Board: over)
capacity, matching Bengaluru's well-known reputation for those corridors,
collector segments comfortably under it.

``base_volume_vph`` is a plain vehicle count, NOT a Passenger Car Unit
(PCU) figure — see bpr.py's module docstring for why that matters for
Indian traffic specifically (heterogeneous vehicle mix, no lane
discipline, IRC:106 capacity guidance uses PCU/hour, not vehicles/hour).
This skeleton doesn't model vehicle-type composition at all, so treat
every volume/capacity ratio as a rough single-mode approximation.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RoadNode:
    id: str
    name: str
    lat: float
    lon: float


@dataclass(frozen=True)
class RoadEdge:
    id: str
    name: str
    u: str
    v: str
    length_m: float
    lanes: int
    free_flow_kmh: float
    base_volume_vph: float
    tier: str  # "arterial" | "collector"
    # Alternate edge id(s) a "festival reroute" on this edge can divert
    # volume onto — only set where a genuine parallel/bypass route exists
    # in this skeleton, not fabricated for every edge.
    reroute_alternates: tuple[str, ...] = field(default_factory=tuple)


NODES: list[RoadNode] = [
    RoadNode("majestic", "Majestic / Kempegowda Bus Station", 12.9767, 77.5713),
    RoadNode("mg_road", "MG Road / Trinity Circle", 12.9757, 77.6067),
    RoadNode("hebbal", "Hebbal (NH44 junction)", 13.0358, 77.5970),
    RoadNode("yeshwanthpur", "Yeshwanthpur", 13.0280, 77.5540),
    RoadNode("peenya", "Peenya industrial area", 13.0280, 77.5200),
    RoadNode("rajajinagar", "Rajajinagar", 12.9990, 77.5510),
    RoadNode("malleshwaram", "Malleshwaram", 13.0010, 77.5730),
    RoadNode("vijayanagar", "Vijayanagar", 12.9707, 77.5350),
    RoadNode("basavanagudi", "Basavanagudi", 12.9432, 77.5721),
    RoadNode("banashankari", "Banashankari", 12.9255, 77.5468),
    RoadNode("jayanagar", "Jayanagar", 12.9250, 77.5830),
    RoadNode("btm_layout", "BTM Layout", 12.9166, 77.6101),
    RoadNode("koramangala", "Koramangala", 12.9352, 77.6245),
    RoadNode("indiranagar", "Indiranagar", 12.9719, 77.6412),
    RoadNode("domlur", "Domlur (ORR junction)", 12.9610, 77.6387),
    RoadNode("silk_board", "Silk Board Junction", 12.9172, 77.6228),
    RoadNode("hsr_layout", "HSR Layout", 12.9116, 77.6389),
    RoadNode("bellandur", "Bellandur", 12.9257, 77.6774),
    RoadNode("marathahalli", "Marathahalli", 12.9591, 77.6974),
    RoadNode("whitefield", "Whitefield / ITPL", 12.9860, 77.7360),
    RoadNode("kr_puram", "K R Puram", 12.9945, 77.6950),
    RoadNode("bommanahalli", "Bommanahalli (Hosur Road)", 12.8990, 77.6150),
    RoadNode("electronic_city", "Electronic City", 12.8452, 77.6602),
]

EDGES: list[RoadEdge] = [
    RoadEdge("e_majestic_hebbal", "Bellary Road (NH44)", "majestic", "hebbal", 9000, 6, 45, 4200, "arterial"),
    RoadEdge("e_hebbal_yeshwanthpur", "Tumkur Road link", "hebbal", "yeshwanthpur", 7000, 4, 40, 3800, "arterial"),
    RoadEdge("e_yeshwanthpur_majestic", "Tumkur Road", "yeshwanthpur", "majestic", 6000, 6, 40, 5400, "arterial"),
    RoadEdge("e_majestic_mgroad", "Central Bengaluru corridor", "majestic", "mg_road", 4000, 4, 30, 2600, "collector"),
    RoadEdge("e_mgroad_indiranagar", "Old Airport Road", "mg_road", "indiranagar", 5000, 4, 35, 3100, "collector"),
    RoadEdge("e_indiranagar_domlur", "Outer Ring Road (Indiranagar-Domlur)", "indiranagar", "domlur", 3000, 6, 40, 5800, "arterial"),
    RoadEdge("e_domlur_marathahalli", "Outer Ring Road (Domlur-Marathahalli)", "domlur", "marathahalli", 6000, 6, 40, 6300, "arterial"),
    RoadEdge("e_marathahalli_bellandur", "Outer Ring Road (Marathahalli-Bellandur)", "marathahalli", "bellandur", 5000, 6, 35, 6600, "arterial"),
    RoadEdge("e_bellandur_koramangala", "Sarjapur-Koramangala link", "bellandur", "koramangala", 6000, 4, 30, 3400, "collector"),
    RoadEdge("e_marathahalli_whitefield", "Whitefield Main Road", "marathahalli", "whitefield", 7000, 4, 35, 4600, "arterial"),
    RoadEdge("e_whitefield_krpuram", "ITPL Main Road / Old Madras Road", "whitefield", "kr_puram", 8000, 4, 35, 4400, "arterial"),
    RoadEdge("e_krpuram_hebbal", "Old Madras Road - Hennur arc", "kr_puram", "hebbal", 12000, 4, 35, 4000, "arterial"),
    RoadEdge(
        "e_silkboard_marathahalli", "Outer Ring Road (Silk Board-Marathahalli)", "silk_board", "marathahalli",
        7000, 6, 30, 7500, "arterial",
        reroute_alternates=("e_silkboard_hsr", "e_hsr_bellandur"),
    ),
    RoadEdge("e_silkboard_btm", "Hosur Road - BTM link", "silk_board", "btm_layout", 3000, 4, 30, 3200, "collector"),
    RoadEdge("e_btm_koramangala", "BTM - Koramangala link", "btm_layout", "koramangala", 4000, 4, 30, 2800, "collector"),
    RoadEdge("e_koramangala_indiranagar", "Koramangala - Indiranagar link", "koramangala", "indiranagar", 5000, 4, 30, 3000, "collector"),
    RoadEdge(
        "e_silkboard_hsr", "Hosur Road - HSR link", "silk_board", "hsr_layout", 3000, 4, 30, 2600, "collector",
        reroute_alternates=("e_silkboard_marathahalli",),
    ),
    RoadEdge("e_hsr_bellandur", "HSR - Bellandur link", "hsr_layout", "bellandur", 5000, 4, 30, 2600, "collector"),
    RoadEdge(
        "e_silkboard_electroniccity", "Hosur Road (Silk Board-Electronic City)", "silk_board", "electronic_city",
        9000, 6, 40, 7200, "arterial",
    ),
    RoadEdge("e_electroniccity_bommanahalli", "Hosur Road (Electronic City-Bommanahalli)", "electronic_city", "bommanahalli", 6000, 6, 40, 6400, "arterial"),
    RoadEdge(
        "e_bommanahalli_silkboard", "Hosur Road (Bommanahalli-Silk Board)", "bommanahalli", "silk_board", 3000, 6, 35, 7000, "arterial",
        reroute_alternates=("e_silkboard_hsr",),
    ),
    RoadEdge("e_majestic_basavanagudi", "Basavanagudi corridor", "majestic", "basavanagudi", 4000, 4, 30, 2400, "collector"),
    RoadEdge("e_basavanagudi_banashankari", "Kanakapura Road link", "basavanagudi", "banashankari", 4000, 4, 30, 2600, "collector"),
    RoadEdge("e_banashankari_jayanagar", "Banashankari - Jayanagar link", "banashankari", "jayanagar", 3000, 4, 30, 2200, "collector"),
    RoadEdge("e_jayanagar_btm", "Jayanagar - BTM link", "jayanagar", "btm_layout", 3000, 4, 30, 2400, "collector"),
    RoadEdge("e_majestic_vijayanagar", "Vijayanagar corridor", "majestic", "vijayanagar", 6000, 4, 35, 2800, "collector"),
    RoadEdge("e_vijayanagar_rajajinagar", "Vijayanagar - Rajajinagar link", "vijayanagar", "rajajinagar", 4000, 4, 30, 2200, "collector"),
    RoadEdge("e_rajajinagar_malleshwaram", "Rajajinagar - Malleshwaram link", "rajajinagar", "malleshwaram", 3000, 4, 30, 2000, "collector"),
    RoadEdge("e_malleshwaram_majestic", "Sampige Road corridor", "malleshwaram", "majestic", 4000, 4, 30, 2400, "collector"),
    RoadEdge("e_rajajinagar_peenya", "Peenya industrial corridor", "rajajinagar", "peenya", 6000, 6, 40, 3600, "arterial"),
    RoadEdge("e_peenya_yeshwanthpur", "Peenya - Yeshwanthpur link", "peenya", "yeshwanthpur", 5000, 4, 35, 2600, "collector"),
]

_NODE_BY_ID = {n.id: n for n in NODES}
_EDGE_BY_ID = {e.id: e for e in EDGES}


def node_by_id(node_id: str) -> RoadNode:
    return _NODE_BY_ID[node_id]


def edge_by_id(edge_id: str) -> RoadEdge:
    return _EDGE_BY_ID[edge_id]
