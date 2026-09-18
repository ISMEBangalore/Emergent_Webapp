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

PCU CONVERSION — ``volume_vph``/``lane_capacity_vph`` are, by default,
plain vehicle counts, which is the US Highway Capacity Manual assumption
for homogeneous, lane-disciplined traffic. Indian practice (IRC:106-1990
and the "Indo-HCM") instead converts every vehicle type to a Passenger
Car Unit (PCU) equivalent before computing capacity, because Indian
traffic is heterogeneous and doesn't hold lane discipline. This module
now supports that conversion (``pcu_volume``, ``DEFAULT_VEHICLE_MIX``,
the optional ``vehicle_mix`` argument to ``evaluate_segment``) — pass a
vehicle-type mix and the volume/capacity ratio (and everything downstream
of it) is computed in PCU terms instead of raw vehicle counts. What this
does NOT fix: ``DEFAULT_LANE_CAPACITY_VPH = 1800`` is still a round
number carried over from the homogeneous-traffic literature, not looked
up from IRC:106's own capacity tables (which vary by carriageway width
and divided/undivided status) — treat the CONVERSION as real, the
DEFAULT CAPACITY VALUE as still approximate pending that lookup. Treat
every number this module produces as "roughly how much better/worse",
not as a certified capacity analysis.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

DEFAULT_ALPHA = 0.15
DEFAULT_BETA = 4.0
DEFAULT_LANE_CAPACITY_VPH = 1800.0  # PCU/hour/lane if a vehicle_mix is supplied, else plain vehicles/hour/lane

# Passenger Car Unit equivalence factors, IRC:106-style — how many
# "car's worth" of road space one vehicle of this type effectively uses
# under Indian mixed-traffic conditions. Illustrative/typical values
# widely cited in Indian transportation-engineering teaching material,
# not re-derived from a specific survey for this project.
PCU_FACTORS: dict[str, float] = {
    "two_wheeler": 0.5,
    "auto_rickshaw": 0.8,
    "car": 1.0,
    "bus_truck": 3.0,
}

# An illustrative "typical" Indian mixed-urban-traffic composition, used
# as the default when a caller wants a PCU-adjusted result but hasn't
# supplied a corridor-specific mix. NOT a Bengaluru-specific survey —
# replace with real classified-volume-count data before relying on this.
DEFAULT_VEHICLE_MIX: dict[str, float] = {
    "two_wheeler": 0.45,
    "auto_rickshaw": 0.15,
    "car": 0.30,
    "bus_truck": 0.10,
}


def pcu_volume(total_vph: float, mix: dict[str, float] | None = None) -> float:
    """Convert a raw vehicle-count volume to its PCU-equivalent volume,
    given a vehicle-type composition (fractions of ``total_vph``, must
    sum to ~1.0). Defaults to ``DEFAULT_VEHICLE_MIX`` if not supplied.
    """
    mix = DEFAULT_VEHICLE_MIX if mix is None else mix
    total_fraction = sum(mix.values())
    if not math.isclose(total_fraction, 1.0, abs_tol=0.01):
        raise ValueError(f"vehicle mix fractions must sum to ~1.0, got {total_fraction}")
    unknown = set(mix) - set(PCU_FACTORS)
    if unknown:
        raise ValueError(f"unknown vehicle type(s) in mix: {sorted(unknown)}")
    return total_vph * sum(fraction * PCU_FACTORS[kind] for kind, fraction in mix.items())


# Level of Service (LOS) thresholds on volume/capacity ratio — the
# standard A (free flow) to F (breakdown) grading transportation
# engineering uses to describe a facility's operating condition. Typical
# Highway Capacity Manual-style break points; exact thresholds vary by
# facility type/edition in real practice, so treat these as illustrative,
# consistent ones for teaching rather than a universal legal standard.
LOS_THRESHOLDS: list[tuple[float, str]] = [
    (0.35, "A"),
    (0.55, "B"),
    (0.75, "C"),
    (0.90, "D"),
    (1.00, "E"),
]


def level_of_service(vc_ratio: float) -> str:
    for threshold, grade in LOS_THRESHOLDS:
        if vc_ratio < threshold:
            return grade
    return "F"


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
    volume_effective: float  # the volume actually used for v/c — PCU-adjusted if a vehicle_mix was given, else raw
    los: str  # Level of Service grade, "A".."F" — see level_of_service()


def evaluate_segment(
    length_m: float,
    free_flow_kmh: float,
    lanes: int,
    volume_vph: float,
    lane_capacity_vph: float = DEFAULT_LANE_CAPACITY_VPH,
    alpha: float = DEFAULT_ALPHA,
    beta: float = DEFAULT_BETA,
    vehicle_mix: dict[str, float] | None = None,
) -> SegmentResult:
    """Evaluate one road segment. If ``vehicle_mix`` is given (a mapping
    of PCU_FACTORS keys to fractions summing to ~1.0), ``volume_vph`` is
    treated as a raw total vehicle count and converted to PCU before the
    volume/capacity ratio (and therefore travel time and LOS) is
    computed — pass ``vehicle_mix=DEFAULT_VEHICLE_MIX`` for an
    illustrative Indian-mixed-traffic correction, or omit it to keep the
    previous homogeneous-vehicle-count behavior.
    """
    effective_volume = pcu_volume(volume_vph, vehicle_mix) if vehicle_mix is not None else volume_vph
    fft = free_flow_time_s(length_m, free_flow_kmh)
    vc = volume_capacity_ratio(effective_volume, lanes, lane_capacity_vph)
    tt = fft * (1 + alpha * (vc**beta))
    return SegmentResult(
        travel_time_s=tt,
        free_flow_time_s=fft,
        volume_capacity_ratio=vc,
        delay_s=tt - fft,
        volume_effective=effective_volume,
        los=level_of_service(vc),
    )
