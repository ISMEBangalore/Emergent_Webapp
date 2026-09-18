# Research: what already exists, and what this tool adds

This tool started from four "thinking out loud" ideas about Bengaluru traffic. Before
writing code, it's worth being honest about what's already deployed, what's studied
academically, and what's actually a gap.

## 1. What already exists

**Bengaluru Adaptive Traffic Control System (B-ATCS / CoSiCoSt).** Bengaluru Traffic
Police, with C-DAC and Arcadis IBI Group, has deployed an AI-driven adaptive signal
control system (CoSiCoSt, built for India's non-lane-based heterogeneous traffic) at
169 junctions as of April 2025, with a target of 500+ by 2027. It adjusts signal
timing in real time from live traffic data and includes GPS-based emergency-vehicle
priority. This directly addresses *signal timing*, but is closed, city-operated
infrastructure — it is not a public API, and it does not appear to do network-wide
resilience ranking (variable #3), U-turn geometry optimization (variable #1), or a
religious-calendar-aware congestion model (variable #4).
[Indian Infrastructure case study](https://indianinfrastructure.com/2026/04/06/smart-mobility-a-case-study-of-the-bengaluru-adaptive-traffic-control-system/) ·
[Team-BHP coverage](https://www.team-bhp.com/news/bangalore-gets-ai-powered-adaptive-traffic-control-system) ·
[Bengaluru Traffic Police page](https://btp.karnataka.gov.in/214/adaptive-traffic-control-system-(atcs)/en)

**Large religious-gathering crowd/traffic management.** Sabarimala is piloting
AI-driven crowd control (camera/infrared/drone heat maps to predict crowd build-up,
virtual queues, daily booking caps). Kumbh Mela's 2027 Nashik plan uses hard zoning
plus an outer-parking-and-shuttle model to keep private vehicles out of the core
area. These are large-event playbooks (zone the area, divert vehicles outward, shuttle
the last mile) rather than a routine, weekly, city-wide model — they operate at the
scale of a single mega-event, not "every masjid every Friday."
[Sabarimala AI crowd management](https://keralakaumudi.com/en/kerala/general/sabarimala-pilgrimage-ai-technology-crowd-management-1768728) ·
[Simhastha Kumbh Mela 2027 traffic plan](https://nashikkumbhmela.org/simhastha-kumbh-mela-2027-traffic-plan-entry-routes-parking-and-shuttle-bus-system-announced/) ·
[Sabarimala Crisis Management Plan (Kerala SDMA)](https://sdma.kerala.gov.in/wp-content/uploads/2019/08/CMP-Sabarimala.pdf)

**Utility work-zone coordination.** US practice (FHWA) formalizes "Work Zone Project
Coordination" — joint trenching, shared permits, a standing Utility Coordinating
Committee — specifically to stop multiple agencies from cutting the same road in the
same year. This is a coordination/process pattern, not a piece of software tied to
live congestion data; nothing found ties dig-permit scheduling to a predicted
low-traffic window the way variable #2 asks for.
[FHWA Work Zone Project Coordination](https://ops.fhwa.dot.gov/wz/construction/crp/index.htm) ·
[FHWA Pavement Utility Cuts](https://www.fhwa.dot.gov/utilities/utilitycuts/man02.cfm)

**Bengaluru open transit data.** BMTC has no official public API, but community
efforts (`datameet`/OpenBangalore, and unofficial GTFS dumps on GitHub/Kaggle) publish
BMTC routes, stops and schedules as GTFS. Bus schedule-vs-actual deviation is a usable
(if noisy) proxy for road-level congestion where no other feed exists.
[Vonter/bmtc-gtfs](https://github.com/Vonter/bmtc-gtfs) · [datameet transport data](https://datameet.org/category/data/transport/)

## 2. What's academically well-studied (and directly reusable)

**Road-network criticality via betweenness centrality (variable #3).** Ranking edges
by betweenness centrality — how often a segment sits on shortest paths between other
points — is the standard first-pass method for finding topological bottlenecks in
transportation networks; refinements weight it by actual traffic flow (path-flow
weighted betweenness, Traffic Flow Betweenness Index) to avoid over-crediting
low-flow shortcuts. `criticality.py` in this tool implements the base version plus a
removal-impact simulation to sanity-check the top candidates.
[Link criticality via path-flow weighted betweenness (2025)](https://www.sciencedirect.com/science/article/abs/pii/S0378437125005631) ·
[Critical links via traffic flow betweenness index](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7147776/) ·
[GPS-trajectory-based critical road identification](https://www.sciencedirect.com/science/article/abs/pii/S0378437119313470)

**U-turn / median-opening placement (variable #1).** This is an active, well-parameterized
traffic-engineering research area: the optimal distance of a U-turn median opening from
the main intersection depends on traffic volume and composition, tested at increments
like 120/150/180/210/250/300 m from the intersection, and Median U-Turn (MUT) designs
outperform conventional signalized intersections up to roughly 4,000 vehicles/hour total
entering volume. This is genuinely a simulation/optimization problem, not a simple
heuristic — see "gap" note below.
[Optimizing U-Turn median opening location (ASCE)](https://ascelibrary.org/doi/abs/10.1061/JTEPBS.0000267) ·
[Optimal location of U-Turn median openings (TRB)](https://doi.org/10.3141/1847-05) ·
[Scenario-based MUT evaluation across demand levels](https://pmc.ncbi.nlm.nih.gov/articles/PMC13465966/)

**Traffic simulation / digital twins.** SUMO (Simulation of Urban MObility, DLR) is a
mature open-source microscopic traffic simulator used for exactly this kind of
what-if testing — geometry changes, signal retiming, new routing — including recent
"digital twin" projects (e.g. Digital Twin Munich) that compare scenario indicators
before committing changes in the real network.
[SUMO documentation](https://sumo.dlr.de/docs/Data/Scenarios.html) · [Sumonity (SUMO + Unity)](https://muenchen.digital/projekte/digitaler-zwilling/28_game_engine-en.html)

## 3. The actual gap (why this tool is worth building)

Nothing found combines all four variables from the original brief into one
routinely-run tool:

- B-ATCS optimizes signal timing but is a closed municipal system, not a public
  planning tool for road-geometry or maintenance-scheduling decisions.
- Betweenness-centrality criticality analysis is well established in the literature
  but isn't, as far as this research found, applied as a standing tool against
  Bengaluru's own network to prioritize maintenance.
- Religious-crowd traffic management exists at mega-event scale (Kumbh, Sabarimala)
  but not as a routine "every Friday/Tuesday/Saturday, at every masjid/temple in the
  city" scheduling input.
- Utility work-zone coordination is a process/policy pattern; tying it to a
  predicted low-traffic *time window* rather than just "avoid other dig permits" is
  the missing piece variable #2 is asking for.

That's the scope this MVP targets: a **static analysis toolkit** — no live feed
required — that (a) ranks roads by network importance from an OSM extract, (b) scores
any date for any tagged religious landmark against a weekly-recurrence rule plus a
festival calendar, and (c) combines the two into a maintenance-window recommendation.
U-turn geometry optimization (variable #1) is deliberately **not** in this MVP: the
literature above shows it needs a real traffic-volume simulation (SUMO or similar),
which needs calibrated demand data this tool doesn't yet have — see Roadmap below.

## 4. Other variables worth adding as the tool grows

Turned up during research or by extension of the same logic, roughly in order of how
cheaply they slot into the existing data model:

- **IT park shift timings** — Whitefield, Electronic City, ORR tech corridors have
  concentrated 9/10/11 AM and matching evening shift changes that dominate local
  peak timing far more than a generic "rush hour" — a real `TimeOfDayProfile` should
  be per-zone, not citywide.
- **School/exam calendars** — board exam dates and school start/end times create
  sharp, predictable local peaks (drop-off/pickup) similar in shape to the religious
  weekly-peak model already built.
- **Wholesale market days** — KR Market and similar wholesale/mandi areas have their
  own weekly heavy-vehicle patterns (early-morning loading), same rule-engine shape
  as `WEEKLY_PEAK_DAYS`.
- **Monsoon waterlogging blackspots** — BBMP publishes known flooding-prone stretches
  each monsoon; these should raise a road's effective criticality tier during the
  monsoon months, since a flooded arterial has no fallback capacity.
- **Metro (Namma Metro) construction phases** — an active construction corridor is
  effectively a long-duration, high-severity "festival" in this model's terms and
  can reuse the `Festival` mechanism instead of needing a new one.
- **Freight/heavy-vehicle curfew hours** — Bengaluru already restricts heavy vehicle
  entry to certain hours; this interacts directly with `workzone_scheduler`'s
  allowed-hours logic and should be modeled as a citywide time constraint.
- **Stadium/large-venue event calendars** (M. Chinnaswamy Stadium, Kanteerava
  Stadium) and **VIP movement advisories** — same one-off, date-scoped shape as
  `Festival`, just a different source list to maintain.
- **Accident-hotspot data** — where available (Bengaluru Traffic Police publishes
  black-spot lists periodically), this is an independent signal from betweenness
  centrality and should be a second, additive criticality factor, not a replacement.

## 5. Roadmap (explicitly out of scope for this MVP)

1. **Real time-of-day congestion data** to replace `GenericCommuteProfile` — start
   with BMTC GTFS scheduled-vs-actual bus speed as a free proxy; a paid traffic-index
   API is the accurate-but-costed alternative.
2. **SUMO-based U-turn/geometry simulation (variable #1)** — once a demand model
   exists (even approximate, from the above), test candidate median-opening
   relocations the way the cited ASCE/TRB studies do, instead of guessing.
3. **A real OSM extract + real landmark/festival data**, verified against official
   sources, to replace the `*.sample.*` placeholder files before anything here is
   used operationally.
4. **A map UI** (e.g. `folium`, already listed as an optional dependency) to make the
   critical-roads ranking and festival-risk calendar visually inspectable rather than
   table-only.
