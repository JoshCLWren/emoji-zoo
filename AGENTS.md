# Emoji Zoo

## What This Is

A terminal-based Conway's Game of Life variant simulating an emoji ecosystem.
Plants grow and spread, herbivores graze and flee predators, carnivores hunt.
Energy drives reproduction and death. Population cycles emerge from simple rules.

Each species has unique traits (speed, vision, lifespan, reproduction thresholds).
Seasons cycle through Spring/Summer/Autumn/Winter, affecting plant growth and
energy burn. Disease can sweep through dense populations. Dead animals decompose
into nutrients that boost plant growth. Animals get thirsty and must drink from
water. Some carnivores can hunt smaller carnivore species.

## Tech Stack

- Python 3 (stdlib only except `faker`)
- Single file: `emoji_zoo.py`
- Dependencies: `faker` (see `requirements.txt`)
- Tests: `pytest` (see `pytest.ini`, `tests/test_emoji_zoo.py`)

## Running

```bash
pip3 install -r requirements.txt
python3 emoji_zoo.py
```

### CLI Arguments

```bash
python3 emoji_zoo.py --seed 42 --preset desert --speed 2 --no-picker
python3 emoji_zoo.py --width 60 --height 30
python3 emoji_zoo.py --load  # load saved ecosystem
python3 emoji_zoo.py --debug  # enable logging
```

Flags: `--seed`, `--width`, `--height`, `--speed`, `--no-picker`, `--preset`,
`--save-file`, `--load`, `--debug`.

### Presets

- `balanced` (default): stable ecosystem
- `desert`: sparse plants, more water, shorter plant lifespan
- `paradise`: abundant plants, minimal predators, no disease
- `predator`: high carnivore population, enhanced carnivore stats
- `chaos`: fast everything, short seasons, high disease

Requires a real terminal (not a pipe). Minimum ~42 columns, ~28 lines.

## Controls

- `SPACE` - pause/resume
- `s` - step one tick (while paused)
- `+`/`-` - speed up/slow down
- `r` - reset the ecosystem
- `1`/`2`/`3` - drop plants/herbivores/carnivores at random spots
- `g` - god mode (arrows move, 1/2/3 place, x delete, ESC exit)
- `p` - parameter tuning menu (up/down select, +/- adjust)
- `h`/`?` - help screen
- `[`/`]` - scroll event log back/forward
- `S` - save ecosystem to file
- `L` - load ecosystem from file
- `q` - quit

## Architecture

Everything lives in `emoji_zoo.py` (~1900 lines). Key sections (marked with `# --`):

- **Species traits** (lines 57-155): `SpeciesTraits` dataclass with per-species
  stats (speed, vision, energy, repro, lifespan, pack_bonus, can_hunt_carns,
  color). `HERBIVORE_TRAITS`/`CARNIVORE_TRAITS` dicts. 8 herbivore and 8
  carnivore species, each with unique values.
- **Config** (lines 158-240): `Config` dataclass with all tunable parameters.
  `PRESETS` dict for named configurations. `make_config()` factory.
- **Emoji palettes** (lines 243-280): Plant stages, herbivore/carnivore emoji
  lists, water/disease emojis, species-to-emoji mappings, season definitions.
- **Model** (lines 290-380): `Kind` enum (PLANT/HERBIVORE/CARNIVORE/WATER),
  `Entity` dataclass (with species, traits, thirst, diseased fields), `Grid`
  class with cell access, neighbors, nutrients layer, and BFS-optimized
  `find_nearest`.
- **Helpers** (lines 383-525): `sign`, `find_nearest` (BFS ring search),
  `find_nearest_species`, `try_move`, `try_move_through_plants`, `sparkline`,
  `random_name` (Faker), entity factories, `drop_creatures`, `species_of`.
- **Statistics** (lines 528-575): `Stats` dataclass tracking cumulative births,
  kills, starvations, age deaths, disease deaths, peak populations, average
  lifespan.
- **Game state** (lines 578-600): `GameState` dataclass bundling grid, config,
  stats, selected species, tick, season, history, ticker, flashes.
- **Simulation step** (lines 605-970): `step()` orchestrates per-tick
  processing. `_tick_plant`/`_tick_herb`/`_tick_carn` handle per-species
  behavior with species traits. New mechanics: seasons, disease spread,
  decomposition (nutrients), thirst/water drinking, pack bonus reproduction,
  intra-carnivore predation, plant aging/dieoff, migration.
- **Setup** (lines 973-1020): `_place_water` creates water clusters, `populate`
  fills the grid with initial populations based on config ratios.
- **Species picker** (lines 1023-1100): Interactive toggle menu at startup.
  Shows per-species trait summaries. Returns selected herb/carn emoji lists.
- **Save/Load** (lines 1103-1200): `save_state`/`load_state` serialize the
  full game state (grid, entities, config, stats, history) to JSON.
- **Event formatting** (lines 1203-1240): Maps event dicts (kill, birth,
  starve, age_death, disease_death, carn_kill) to display messages. Flash
  emojis/colors for grid overlays.
- **Render** (lines 1243-1450): Draws header (tick, speed, status, season),
  food chain legend, grid (with species colors, disease indicators, god mode
  cursor), population sparklines, per-species breakdown, stats panel, event
  ticker (with scrollback), entity inspection (god mode), controls help,
  help overlay, parameter tuning overlay.
- **Input** (lines 1453-1475): Non-blocking keyboard input with arrow key
  parsing.
- **Main** (lines 1480-1898): argparse CLI setup, game loop, terminal
  setup/teardown, key handling for normal/god/params/help modes, SIGWINCH
  resize handling, error recovery in step, save/load key handling.

### Tests

`tests/test_emoji_zoo.py` contains 144 pytest tests covering:

- Grid operations (access, neighbors, nutrients, random_empty)
- Helpers (sign, find_nearest, find_nearest_species, try_move, sparkline)
- Config and presets (all 5 presets, overrides)
- Species traits (variety, colors, can_hunt_carns, pack_bonus)
- Entity factories (plants, herbs, carns with traits)
- Statistics (death tracking, peaks, avg lifespan)
- Simulation step (aging, eating, starvation, disease, decomposition, thirst,
  seasons, migration, reproduction, pack bonus, intra-carn predation,
  plant dieoff, plant cap, energy conservation)
- Populate/setup
- Save/load roundtrip (grid, nutrients, entity state, stats, config)
- Event formatting (all 6 event types)
- Parameter tuning (adjust, clamp, invalid index)
- Season system (4 seasons, modifiers, cycling, winter dieoff)
- Integration (100-tick run, seeded reproducibility, reset)

## Tuning Guide

Use `--preset` for quick configuration, or press `p` in-game for the parameter
tuning menu. For source-level tuning, modify the `Config` dataclass:

- **Plants taking over**: Lower `plant_spread_chance`, `plant_seed_count`, or
  `plant_cap_ratio`. Lower season plant modifiers.
- **Herbivores going extinct**: Raise `migrate_herb_chance`/`migrate_herb_group`,
  lower herbivore species' `repro_threshold` in traits, or lower
  `init_carn_ratio`.
- **Carnivores going extinct**: Raise carnivore species' `vision` in traits,
  lower their `repro_threshold`, or raise `start_energy`.
- **Too many animals**: Raise `repro_threshold` in species traits, lower
  `max_neighbors`, lower `init_*_ratio`, or lower migration rates.
- **Disease too aggressive**: Lower `disease_chance`, `disease_spread_chance`,
  or `disease_death_chance`. Set to 0 to disable.
- **Seasons too fast/slow**: Change `season_length` (ticks per season).
- **Simulation speed**: Change `base_delay` in Config (default 0.4s per tick),
  or use `+`/`-` in-game.

## Key Design Decisions

- **Species traits**: Each species has unique speed, vision, energy thresholds,
  lifespan, and pack bonus. Rabbits breed fast but die young; eagles see far
  but have low energy; bears are slow but long-lived and can hunt other
  carnivores.
- **Seasons**: Spring boosts plant growth and reduces energy burn. Winter does
  the opposite and can kill plants. Season length is configurable.
- **Disease**: Random infection chance per tick. Diseased animals drain extra
  energy, spread to adjacent same-kind neighbors, and either die or recover
  after `disease_duration` ticks.
- **Decomposition**: Dead animals add nutrients to their cell. Plants on
  nutrient-rich cells grow faster. Nutrients decay each tick.
- **Thirst**: Animals gain thirst each tick. Above `thirst_threshold`, they
  lose extra energy. Drinking from adjacent water resets thirst.
- **Pack/herd behavior**: Animals near same-species neighbors get a
  reproduction threshold reduction proportional to `pack_bonus`.
- **Intra-carnivore predation**: Species with `can_hunt_carns=True` (bear,
  tiger, eagle, snake, crocodile) hunt carnivores with lower `max_energy`.
- **Plant aging**: Plants die after `plant_max_age` ticks or from winter
  dieoff, adding nutrients to the soil.
- **Carnivore movement**: Carnivores can move through plant cells (trampling
  them) via `try_move_through_plants`. Herbivores cannot.
- **Predator satiation**: Carnivores only hunt when energy < 60% of max,
  preventing them from wiping out all prey at once.
- **BFS find_nearest**: Ring-based outward search with early exit, more
  efficient than scanning the full vision square.
- **GameState**: All mutable state is bundled in a `GameState` dataclass
  instead of module-level globals, enabling save/load and testability.
- **Error recovery**: `step()` is wrapped in try/except in the main loop;
  errors are logged and displayed in the ticker without crashing.
- **SIGWINCH**: Terminal resize triggers a screen clear and re-render.
- **Reproducibility**: `--seed` seeds both `random` and `Faker` for
  reproducible runs.

## Dependencies

- `faker` - generates random animal names (`Faker().first_name()`)
- `pytest` - test runner (dev only)
- Everything else is Python stdlib
