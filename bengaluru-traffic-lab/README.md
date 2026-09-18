# Bengaluru Traffic Lab

A small, self-contained analysis toolkit for asking "would changing this traffic-zone
variable actually help?" — starting from four ideas (U-turn placement, road-work
timing, critical-road identification, religious-calendar-aware congestion) and built
as a **static analysis tool**: it works from a road-network export and configuration
files, with no live traffic feed required (Bengaluru doesn't have a public one — see
`docs/RESEARCH.md`).

This lives in its own directory, independent of the LeadPulse CRM app elsewhere in
this repository (different problem domain, different dependencies) — treat it as a
standalone project that happens to be checked in alongside it, and expect it to move
to its own repository if it grows past the exploration stage.

## Read this first

`docs/RESEARCH.md` covers what already exists (Bengaluru's B-ATCS adaptive signal
system, Sabarimala/Kumbh Mela crowd management, academic road-criticality and
U-turn-placement research, SUMO traffic simulation), what gap this tool actually
fills, and a roadmap of what's deliberately left out of this first pass — most
importantly, U-turn geometry optimization (variable #1), which needs a calibrated
traffic simulation this MVP doesn't build.

## What's here

| Module | Variable it addresses | What it does |
|---|---|---|
| `criticality.py` | #3 — critical roads | Ranks road segments by betweenness centrality, then simulates removing the top candidates to confirm real impact (does it disconnect the network / how much longer do detours get). |
| `calendar_rules.py` + `landmarks.py` | #4 — religious-site congestion | Tags landmarks with a kind (masjid, hanuman_temple, shani_temple, church, ...) and a recurring weekly peak day, plus a festival calendar for one-off spikes (immersion processions, Eid, etc.). |
| `workzone_scheduler.py` | #2 — road-digging/utility work timing | Combines a road's criticality tier with the calendar risk of anything nearby to recommend allowed work hours or a hard blackout for a given date. |
| `graph_io.py` | (shared) | Loads a road network from GraphML, a plain edge-list CSV, or a live OSM fetch via `osmnx`. |
| `report.py` | (shared) | CLI: `critical-roads` and `festival-risk` subcommands. |

Variable #1 (U-turn placement) isn't implemented yet — see the Roadmap section of
`docs/RESEARCH.md` for why (it needs a calibrated volume/simulation model, e.g. SUMO,
not a heuristic) and what the next step looks like.

## Setup

```bash
cd bengaluru-traffic-lab
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt pytest
```

## Sample output, visualized

`docs/sample-output.html` is a static, open-in-any-browser rendering of what the CLI
below actually produces: the critical-roads ranking as a diagram, the 30-day
festival-risk calendar as a heatmap, and the sample landmarks plotted on a real
lat/lon-projected map (with orientation reference points) that you can step through
day by day. It's generated from the same sample data in this directory — open it
directly, no server needed.

`docs/google-map.html` is the same 5 landmarks and 30-day risk calendar on an
**actual Google Map** (real tiles, real streets, an optional live-traffic-layer
toggle) instead of a projected graticule. It needs your own Google Maps API key
(the file's top comment walks through getting one — Maps JavaScript API enabled,
billing on, key restricted to your use) pasted into `GOOGLE_MAPS_API_KEY` near the
top; without a key it just shows a setup banner instead of a map. This is
deliberately a plain standalone file, not published anywhere — Google's Maps
JavaScript API can't load inside a claude.ai Artifact's sandbox, only in a normal
browser tab you open yourself. Google Maps here is presentation only: the
criticality *analysis* still runs on OSM data (see `graph_io.py`), since Google's
Maps Platform terms restrict caching/storing their data to build your own derived
geographic dataset, which is exactly what that analysis does.

## Try it with the bundled sample data

The `data/*.sample.*` files are illustrative only (a synthetic 8-node road network,
a handful of real Bengaluru landmark names with approximate/unverified coordinates,
and a festival calendar with clearly-marked placeholder dates) — good for seeing the
tool work end to end, not for operational use.

```bash
# Rank roads by network importance, and confirm the top ones with a removal simulation
python -m traffic_lab.report critical-roads --graph data/sample_network.csv --top 5 --impact

# List every weekly-peak-day and festival-day congestion risk over the next 2 weeks
python -m traffic_lab.report festival-risk \
  --landmarks data/landmarks.sample.csv \
  --festivals data/festivals.sample.yaml \
  --start 2026-09-18 --days 14
```

Both commands take `--format json` for machine-readable output.

## Using it on a real road network

1. Get an OSM extract for the area you care about, either via `osmnx` (needs network
   access):
   ```python
   from traffic_lab import graph_io
   g = graph_io.fetch_osm_graph("Indiranagar, Bengaluru, India")
   graph_io.save_graphml(g, "data/indiranagar.graphml")
   ```
   or by exporting a hand-picked edge list into the same `u,v,name,length_m,oneway`
   CSV shape as `data/sample_network.csv` if you'd rather not depend on OSM at all.
2. Replace `data/landmarks.sample.csv` and `data/festivals.sample.yaml` with real,
   verified data — see the disclaimer comments at the top of each sample file for
   what to check before trusting them.
3. Run the same `report.py` commands against your real files.

## Tests

```bash
pip install pytest
pytest
```

Tests run against small synthetic graphs and fixed dates — no OSM/network access or
real data files required.
