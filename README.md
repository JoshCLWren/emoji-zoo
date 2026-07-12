# 🦁 Emoji Zoo

A terminal-based ecosystem simulation where Conway's Game of Life meets a living, breathing emoji world. Plants grow and spread, herbivores graze and flee predators, carnivores hunt. Population cycles emerge from simple rules.

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![Tests](https://img.shields.io/badge/tests-152%20pytest-brightgreen)
![License](https://img.shields.io/badge/license-MIT-green)

## Features

### Ecosystem Simulation

- **8 herbivore species** (rabbit, sheep, deer, cow, goat, bunny, pig, horse) and **8 carnivore species** (lion, wolf, fox, bear, tiger, eagle, snake, crocodile), each with unique traits
- **Per-species traits**: speed, vision, lifespan, reproduction thresholds, pack bonus, color
- **Seasons**: Spring/Summer/Autumn/Winter cycle, affecting plant growth and energy burn. Winter kills plants.
- **Disease**: random infections spread through dense populations, draining energy and killing or recovering after a duration
- **Decomposition**: dead animals enrich the soil, boosting plant growth on nutrient-rich cells
- **Thirst**: animals must drink from adjacent water or suffer energy penalties
- **Pack/herd behavior**: same-species neighbors lower reproduction thresholds
- **Intra-carnivore predation**: bears, tigers, eagles, snakes, and crocodiles hunt smaller carnivore species
- **Cannibalism**: starving carnivores (below 20% energy) eat their own kind
- **Natural aging**: every species has a max lifespan; plants die of old age too

### Gameplay

- **5 presets**: balanced, desert, paradise, predator, chaos
- **Species picker**: toggle which animals are in your zoo at startup
- **God mode**: place and delete entities with a cursor
- **Parameter tuning**: adjust 9 simulation parameters live without restarting
- **Save/load**: persist your ecosystem to JSON and restore it later
- **Step mode**: advance one tick at a time while paused
- **Event log**: scrollable history of births, kills, starvations, deaths, and disease

### Terminal UI

- Population sparklines for plants, herbivores, and carnivores
- Per-species population breakdown
- Stats panel (births, kills, starvations, age deaths, disease deaths, peaks, avg lifespan)
- Entity inspection in god mode (energy, age, thirst, disease, coordinates)
- Color-coded rendering by species
- Disease visual indicator
- Season indicator with progress bar
- Terminal resize handling

## Quick Start

```bash
pip3 install -r requirements.txt
python3 emoji_zoo.py
```

Requires a real terminal (not a pipe). Minimum ~42 columns, ~28 lines.

## CLI Arguments

```bash
python3 emoji_zoo.py --seed 42 --preset desert --speed 2 --no-picker
python3 emoji_zoo.py --width 60 --height 30
python3 emoji_zoo.py --load          # load saved ecosystem
python3 emoji_zoo.py --debug         # enable logging
```

| Flag | Description |
|------|-------------|
| `--seed` | Random seed for reproducible runs |
| `--width` | Grid width (default: auto from terminal) |
| `--height` | Grid height (default: auto from terminal) |
| `--speed` | Initial speed multiplier (default 1) |
| `--no-picker` | Skip species picker, use all species |
| `--preset` | Ecosystem preset: balanced, desert, paradise, predator, chaos |
| `--save-file` | Save/load file path (default: emoji_zoo_save.json) |
| `--load` | Load saved ecosystem on startup |
| `--debug` | Enable debug logging |

## Presets

| Preset | Description |
|--------|-------------|
| `balanced` | Stable ecosystem with all mechanics at default levels |
| `desert` | Sparse plants, more water, shorter plant lifespan |
| `paradise` | Abundant plants, minimal predators, no disease |
| `predator` | High carnivore population with enhanced stats |
| `chaos` | Fast everything, short seasons, high disease |

## Controls

| Key | Action |
|-----|--------|
| `SPACE` | Pause / resume |
| `s` | Step one tick (while paused) |
| `+` / `-` | Speed up / slow down |
| `r` | Reset the ecosystem |
| `1` / `2` / `3` | Drop plants / herbivores / carnivores |
| `g` | God mode (arrows move, 1/2/3 place, x delete, ESC exit) |
| `p` | Parameter tuning menu |
| `h` / `?` | Help screen |
| `[` / `]` | Scroll event log back / forward |
| `S` | Save ecosystem to file |
| `L` | Load ecosystem from file |
| `q` | Quit |

## Species Traits

Every species has unique stats that affect how it behaves:

### Herbivores

| Species | Vision | Lifespan | Breed Threshold | Pack Bonus |
|---------|--------|----------|-----------------|------------|
| Bunny | 3 | 60 | 16 | 0.20 |
| Rabbit | 4 | 80 | 20 | 0.15 |
| Goat | 5 | 170 | 30 | 0.05 |
| Sheep | 5 | 150 | 32 | 0.08 |
| Pig | 5 | 160 | 30 | 0.05 |
| Horse | 6 | 190 | 34 | 0.00 |
| Deer | 7 | 160 | 32 | 0.05 |
| Cow | 4 | 200 | 38 | 0.00 |

### Carnivores

| Species | Vision | Lifespan | Can Hunt Carns |
|---------|--------|----------|----------------|
| Snake | 4 | 140 | Yes |
| Crocodile | 4 | 240 | Yes |
| Bear | 5 | 250 | Yes |
| Tiger | 6 | 220 | Yes |
| Lion | 6 | 200 | No |
| Fox | 6 | 120 | No |
| Wolf | 7 | 180 | No |
| Eagle | 9 | 160 | Yes |

## How It Works

Each tick, every entity is processed in random order:

1. **Plants** grow through stages, spread to neighbors, and die from old age or winter
2. **Herbivores** flee nearby carnivores, eat adjacent plants, seek food, drink water, reproduce when well-fed, and die from starvation, old age, or disease
3. **Carnivores** hunt herbivores, chase prey, eat smaller carnivore species, cannibalize when starving, and reproduce when well-fed

Energy is the core currency. Animals burn energy each tick (modified by season). Eating restores it. Reproduction costs it. Death returns it to the soil as nutrients.

Population cycles emerge naturally: plants flourish, herbivores boom, carnivores rise, herbivores crash, carnivores starve, plants recover, repeat.

## Tech Stack

- Python 3 (stdlib only except `faker`)
- Single file: `emoji_zoo.py`
- 152 pytest tests
- CI: GitHub Actions on Python 3.11, 3.12, 3.13

## License

MIT
