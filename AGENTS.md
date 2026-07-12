# Emoji Zoo

## What This Is

A terminal-based Conway's Game of Life variant simulating an emoji ecosystem.
Plants grow and spread, herbivores graze and flee predators, carnivores hunt.
Energy drives reproduction and death. Population cycles emerge from simple rules.

## Tech Stack

- Python 3 (stdlib only except `faker`)
- Single file: `emoji_zoo.py`
- Dependencies: `faker` (see `requirements.txt`)
- No build step, no tests framework

## Running

```bash
pip3 install -r requirements.txt
python3 emoji_zoo.py
```

Requires a real terminal (not a pipe). Minimum ~42 columns, ~28 lines.

## Controls

- `SPACE` - pause/resume
- `+`/`-` - speed up/slow down
- `r` - reset the ecosystem
- `1`/`2`/`3` - drop plants/herbivores/carnivores at random spots
- `g` - god mode (arrow keys to move cursor, 1/2/3 to place, x to delete, ESC to exit)
- `q` - quit

## Architecture

Everything lives in `emoji_zoo.py`. Key sections (marked with `# --` comments):

- **Tunable parameters** (lines 31-68): All ecosystem balance knobs. Plant spread
  chance, energy thresholds, vision ranges, reproduction costs, migration rates,
  initial population ratios, grid cap ratios.
- **Emoji palettes** (lines 70-97): Plant growth stages, herbivore/carnivore emoji
  lists with keys and species names. `SELECTED_HERBS`/`SELECTED_CARNS` are mutated
  by the species picker.
- **Model** (lines 109-160): `Kind` enum, `Entity` dataclass, `Grid` class with
  cell access, neighbors, and empty/passable neighbor helpers.
- **Helpers** (lines 163-240): `sign`, `find_nearest`, `try_move`,
  `try_move_through_plants`, `sparkline`, `random_name` (Faker), entity factories
  (`make_plant`/`make_herb`/`make_carn`), `drop_creatures`, `species_of`.
- **Simulation step** (lines 243-420): `step()` orchestrates per-tick processing.
  `_tick_plant`/`_tick_herb`/`_tick_carn` handle per-species behavior. Events
  (kills, births, starvation) are appended to an events list for the renderer.
- **Setup** (lines 423-465): `_place_water` creates water clusters, `populate`
  fills the grid with initial populations.
- **Species picker** (lines 468-545): Interactive toggle menu at startup.
  Selects which herbivore/carnivore species are in the zoo.
- **Event formatting** (lines 548-565): Maps event dicts to display messages
  with animal names and species. Flash emojis/colors for grid overlays.
- **Render** (lines 568-680): Draws the grid, food chain legend, population
  sparklines, event ticker, and controls help line.
- **Input** (lines 683-705): Non-blocking keyboard input with arrow key parsing.
- **Main** (lines 708-841): Game loop, terminal setup/teardown, key handling
  for both normal and god mode, per-tick event collection and flash rendering.

## Tuning Guide

If the ecosystem is out of balance, adjust the parameters at the top of the file:

- **Plants taking over**: Lower `PLANT_SPREAD_CHANCE`, `PLANT_SEED_COUNT`, or
  `PLANT_CAP_RATIO`. Raise `HERB_EAT_ENERGY` or `INIT_HERB_RATIO`.
- **Herbivores going extinct**: Raise `MIGRATE_HERB_CHANCE`/`MIGRATE_HERB_GROUP`,
  lower `HERB_REPRO_THRESHOLD`, or lower `INIT_CARN_RATIO`.
- **Carnivores going extinct**: Raise `CARN_VISION`, lower `CARN_REPRO_THRESHOLD`,
  raise `CARN_START_ENERGY`, or slow carnivore energy burn (`e.age % 2`).
- **Too many animals**: Raise `*_REPRO_THRESHOLD`, lower `*_MAX_NEIGHBORS`,
  lower `INIT_*_RATIO`, or lower migration rates.
- **Too fast/slow**: Change `base_delay` in `main()` (currently 0.4s per tick).

## Key Design Decisions

- Carnivores can move through plant cells (trampling them) via
  `try_move_through_plants`. Herbivores cannot.
- Carnivores burn energy every other tick (`e.age % 2 == 0`), herbivores every
  tick. This gives carnivores more hunting time between meals.
- Predator satiation (`CARN_SATIATION`): well-fed carnivores stop killing,
  preventing them from wiping out all prey at once.
- Density-dependent reproduction (`*_MAX_NEIGHBORS`): animals won't reproduce
  if surrounded by too many of their own kind, preventing population explosions.
- Migration: when populations drop below thresholds, new animals randomly
  migrate in, preventing permanent extinction.
- Plant cap: spreading and seeding are gated by `PLANT_CAP_RATIO` so plants
  never fill more than 25% of the grid.

## Dependencies

- `faker` - generates random animal names (`Faker().first_name()`)
- Everything else is Python stdlib
