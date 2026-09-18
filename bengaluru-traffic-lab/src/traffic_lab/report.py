"""CLI entrypoint tying the modules together.

Examples::

    python -m traffic_lab.report critical-roads --graph data/sample_network.csv --top 10
    python -m traffic_lab.report festival-risk --landmarks data/landmarks.sample.csv \\
        --festivals data/festivals.sample.yaml --start 2026-09-18 --days 30
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys

import yaml

from . import criticality, graph_io, landmarks as landmarks_mod
from .calendar_rules import Festival, RiskLevel, upcoming_high_risk_days


def _load_festivals(path: str) -> list[Festival]:
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or []
    festivals = []
    for entry in raw:
        festivals.append(
            Festival(
                name=entry["name"],
                start_date=entry["start_date"],
                end_date=entry.get("end_date", entry["start_date"]),
                severity=RiskLevel(entry.get("severity", "high")),
                affected_kinds=tuple(entry.get("affected_kinds", [])),
                affected_names=tuple(entry.get("affected_names", [])),
                note=entry.get("note", ""),
            )
        )
    return festivals


def cmd_critical_roads(args: argparse.Namespace) -> None:
    graph = graph_io.load_edgelist_csv(args.graph)
    ranked = criticality.rank_critical_roads(graph, top_n=args.top)
    rows = []
    for score in ranked:
        impact = criticality.removal_impact(graph, score.u, score.v) if args.impact else None
        rows.append(
            {
                "road": score.name,
                "from": score.u,
                "to": score.v,
                "betweenness": round(score.betweenness, 5),
                **({"removal_impact": impact} if impact is not None else {}),
            }
        )
    _emit(rows, args.format)


def cmd_festival_risk(args: argparse.Namespace) -> None:
    marks = landmarks_mod.load_landmarks(args.landmarks)
    festivals = _load_festivals(args.festivals) if args.festivals else []
    start = dt.date.fromisoformat(args.start)
    hits = upcoming_high_risk_days(marks, festivals, start, days=args.days, min_level=RiskLevel(args.min_level))
    rows = [
        {
            "date": date.isoformat(),
            "landmark": landmark.name,
            "kind": landmark.kind,
            "level": assessment.level.value,
            "reasons": assessment.reasons,
        }
        for date, landmark, assessment in sorted(hits, key=lambda h: h[0])
    ]
    _emit(rows, args.format)


def _emit(rows: list[dict], fmt: str) -> None:
    if fmt == "json":
        json.dump(rows, sys.stdout, indent=2, default=str)
        sys.stdout.write("\n")
        return
    if not rows:
        print("(no results)")
        return
    headers = list(rows[0].keys())
    widths = {h: max(len(h), max(len(str(r.get(h, ""))) for r in rows)) for h in headers}
    print("  ".join(h.ljust(widths[h]) for h in headers))
    for r in rows:
        print("  ".join(str(r.get(h, "")).ljust(widths[h]) for h in headers))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="traffic_lab.report")
    sub = parser.add_subparsers(dest="command", required=True)

    p1 = sub.add_parser("critical-roads", help="Rank roads by network-wide importance (variable #3)")
    p1.add_argument("--graph", required=True, help="Edge-list CSV (u,v,name,length_m,oneway)")
    p1.add_argument("--top", type=int, default=20)
    p1.add_argument("--impact", action="store_true", help="Also simulate removal impact for each top road")
    p1.add_argument("--format", choices=["table", "json"], default="table")
    p1.set_defaults(func=cmd_critical_roads)

    p2 = sub.add_parser("festival-risk", help="List upcoming weekly/festival congestion days (variable #4)")
    p2.add_argument("--landmarks", required=True)
    p2.add_argument("--festivals", default=None)
    p2.add_argument("--start", default=dt.date.today().isoformat())
    p2.add_argument("--days", type=int, default=30)
    p2.add_argument("--min-level", dest="min_level", choices=[l.value for l in RiskLevel][1:], default="elevated")
    p2.add_argument("--format", choices=["table", "json"], default="table")
    p2.set_defaults(func=cmd_festival_risk)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
