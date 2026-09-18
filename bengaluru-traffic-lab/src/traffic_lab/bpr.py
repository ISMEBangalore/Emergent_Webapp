"""Bureau of Public Roads (BPR) volume-delay function.

The standard textbook link-performance model used in transportation
planning to estimate how travel time on a road segment degrades as
traffic volume approaches (or exceeds) its capacity:

    travel_time = free_flow_time * (1 + alpha * (volume / capacity) ** beta)

with alpha=0.15, beta=4.0 being the original Bureau of Public Roads (1964)
calibration, still the default in most planning software and widely cited
(e.g. the US FHWA's own traffic assignment guidance). This module uses it
as an explainable, citable heuristic for "what happens to travel time if
we change lanes/speed/volume on this segment" — it is NOT a calibrated
model for Bengaluru specifically (no local speed/volume counts feed it;
see docs/RESEARCH.md), and it does NOT model network-wide traffic
assignment/equilibrium (real drivers re-choosing routes network-wide in
response to a change) — only the direct effect on a given segment/path
plus whatever explicit reroute the caller models. Treat outputs as
directional (better/worse, roughly by how much), not as a traffic count.
"""
from __future__ import annotations

from dataclasses import dataclass

DEFAULT_ALPHA = 0.15
DEFAULT_BETA = 4.0
DEFAULT_LANE_CAPACITY_VPH = 1800.0  # vehicles/hour/lane, standard urban arterial assumption (HCM-style)


def free_flow_time_s(length_m: float, free_flow_kmh: float) -> float:
    if free_flow_kmh <= 0:
        raise ValueError("free_flow_kmh must be positive")
    free_flow_mps = free_flow_kmh * 1000.0 / 3600.0
    return length_m / free_flow_mps


def volume_capacity_ratio(volume_vph: float, lanes: int, lane_capacity_vph: float = DEFAULT_LANE_CAPACITY_VPH) -> float:
    capacity_vph = lanes * lane_capacity_vph
    if capacity_vph <= 0:
        raise ValueError("lanes must be positive")
    return volume_vph / capacity_vph


def bpr_travel_time_s(
    length_m: float,
    free_flow_kmh: float,
    lanes: int,
    volume_vph: float,
    lane_capacity_vph: float = DEFAULT_LANE_CAPACITY_VPH,
    alpha: float = DEFAULT_ALPHA,
    beta: float = DEFAULT_BETA,
) -> float:
    fft = free_flow_time_s(length_m, free_flow_kmh)
    vc = volume_capacity_ratio(volume_vph, lanes, lane_capacity_vph)
    return fft * (1 + alpha * (vc**beta))


@dataclass(frozen=True)
class SegmentResult:
    travel_time_s: float
    free_flow_time_s: float
    volume_capacity_ratio: float
    delay_s: float  # travel_time - free_flow_time, i.e. congestion-attributable time


def evaluate_segment(
    length_m: float,
    free_flow_kmh: float,
    lanes: int,
    volume_vph: float,
    lane_capacity_vph: float = DEFAULT_LANE_CAPACITY_VPH,
    alpha: float = DEFAULT_ALPHA,
    beta: float = DEFAULT_BETA,
) -> SegmentResult:
    fft = free_flow_time_s(length_m, free_flow_kmh)
    vc = volume_capacity_ratio(volume_vph, lanes, lane_capacity_vph)
    tt = fft * (1 + alpha * (vc**beta))
    return SegmentResult(travel_time_s=tt, free_flow_time_s=fft, volume_capacity_ratio=vc, delay_s=tt - fft)
