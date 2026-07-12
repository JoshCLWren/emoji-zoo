#!/usr/bin/env python3
"""emoji_zoo -- Conway's Game of Life meets a living, breathing emoji ecosystem.

Plants grow and spread. Herbivores graze and flee predators.
Carnivores hunt. Energy drives reproduction and death.
Population cycles emerge from simple rules.

Each species has unique traits: speed, vision, lifespan, reproduction
thresholds. Seasons affect plant growth and energy burn. Disease can
sweep through dense populations. Dead animals decompose into nutrients
that feed plants. Animals get thirsty and must drink from water.

Controls:
  SPACE  pause / resume
  s      step one tick (while paused)
  + / -  speed up / slow down
  r      reset the ecosystem
  1      drop 5 plants at random spots
  2      drop 5 herbivores at random spots
  3      drop 3 carnivores at random spots
  g      god mode (arrows move, 1/2/3 place, x delete, i inspect, ESC exit)
  p      parameter tuning menu
  h / ?  help screen
  [ / ]  scroll event log back / forward
  S      save ecosystem to file
  L      load ecosystem from file
  q      quit
"""

import argparse
import json
import logging
import os
import random
import select
import signal
import shutil
import sys
import termios
import time
import tty
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional

from faker import Faker

logger = logging.getLogger("emoji_zoo")

# -- Species traits -------------------------------------------------------


@dataclass
class SpeciesTraits:
    speed: int = 1
    vision: int = 5
    flee_vision: int = 2
    start_energy: int = 14
    max_energy: int = 35
    eat_energy: int = 10
    repro_threshold: int = 30
    repro_cost: int = 14
    max_age: int = 200
    max_neighbors: int = 2
    pack_bonus: float = 0.0
    can_hunt_carns: bool = False
    color: str = ""


HERBIVORE_TRAITS: dict[str, SpeciesTraits] = {
    "rabbit": SpeciesTraits(
        speed=1, vision=4, flee_vision=3, start_energy=10, max_energy=25,
        eat_energy=8, repro_threshold=20, repro_cost=8, max_age=80,
        pack_bonus=0.15, color="\033[92m",
    ),
    "sheep": SpeciesTraits(
        speed=1, vision=5, flee_vision=2, start_energy=16, max_energy=40,
        eat_energy=11, repro_threshold=32, repro_cost=15, max_age=150,
        pack_bonus=0.08, color="\033[97m",
    ),
    "deer": SpeciesTraits(
        speed=1, vision=7, flee_vision=4, start_energy=18, max_energy=40,
        eat_energy=11, repro_threshold=32, repro_cost=15, max_age=160,
        pack_bonus=0.05, color="\033[33m",
    ),
    "cow": SpeciesTraits(
        speed=2, vision=4, flee_vision=2, start_energy=24, max_energy=50,
        eat_energy=14, repro_threshold=38, repro_cost=18, max_age=200,
        pack_bonus=0.0, color="\033[37m",
    ),
    "goat": SpeciesTraits(
        speed=1, vision=5, flee_vision=3, start_energy=16, max_energy=38,
        eat_energy=11, repro_threshold=30, repro_cost=14, max_age=170,
        pack_bonus=0.05, color="\033[93m",
    ),
    "bunny": SpeciesTraits(
        speed=1, vision=3, flee_vision=4, start_energy=8, max_energy=20,
        eat_energy=6, repro_threshold=16, repro_cost=6, max_age=60,
        pack_bonus=0.2, color="\033[32m",
    ),
    "pig": SpeciesTraits(
        speed=1, vision=5, flee_vision=2, start_energy=18, max_energy=42,
        eat_energy=12, repro_threshold=30, repro_cost=14, max_age=160,
        pack_bonus=0.05, color="\033[95m",
    ),
    "horse": SpeciesTraits(
        speed=1, vision=6, flee_vision=3, start_energy=22, max_energy=45,
        eat_energy=13, repro_threshold=34, repro_cost=16, max_age=190,
        pack_bonus=0.0, color="\033[90m",
    ),
}

CARNIVORE_TRAITS: dict[str, SpeciesTraits] = {
    "lion": SpeciesTraits(
        speed=1, vision=6, start_energy=26, max_energy=50,
        eat_energy=12, repro_threshold=36, repro_cost=18, max_age=200,
        pack_bonus=0.12, can_hunt_carns=False, color="\033[93m",
    ),
    "wolf": SpeciesTraits(
        speed=1, vision=7, start_energy=22, max_energy=42,
        eat_energy=11, repro_threshold=32, repro_cost=16, max_age=180,
        pack_bonus=0.15, can_hunt_carns=False, color="\033[90m",
    ),
    "fox": SpeciesTraits(
        speed=1, vision=6, start_energy=16, max_energy=30,
        eat_energy=9, repro_threshold=24, repro_cost=10, max_age=120,
        pack_bonus=0.0, can_hunt_carns=False, color="\033[91m",
    ),
    "bear": SpeciesTraits(
        speed=2, vision=5, start_energy=30, max_energy=55,
        eat_energy=14, repro_threshold=40, repro_cost=20, max_age=250,
        pack_bonus=0.0, can_hunt_carns=True, color="\033[33m",
    ),
    "tiger": SpeciesTraits(
        speed=1, vision=6, start_energy=28, max_energy=50,
        eat_energy=13, repro_threshold=38, repro_cost=18, max_age=220,
        pack_bonus=0.0, can_hunt_carns=True, color="\033[38;5;166m",
    ),
    "eagle": SpeciesTraits(
        speed=1, vision=9, start_energy=18, max_energy=35,
        eat_energy=10, repro_threshold=28, repro_cost=14, max_age=160,
        pack_bonus=0.0, can_hunt_carns=True, color="\033[97m",
    ),
    "snake": SpeciesTraits(
        speed=2, vision=4, start_energy=14, max_energy=28,
        eat_energy=8, repro_threshold=22, repro_cost=10, max_age=140,
        pack_bonus=0.0, can_hunt_carns=True, color="\033[32m",
    ),
    "crocodile": SpeciesTraits(
        speed=2, vision=4, start_energy=28, max_energy=50,
        eat_energy=13, repro_threshold=36, repro_cost=18, max_age=240,
        pack_bonus=0.0, can_hunt_carns=True, color="\033[38;5;22m",
    ),
}

TRAITS_BY_KIND: dict[str, dict[str, SpeciesTraits]] = {
    "herbivore": HERBIVORE_TRAITS,
    "carnivore": CARNIVORE_TRAITS,
}


def get_traits(kind_name: str, species: str) -> SpeciesTraits:
    return TRAITS_BY_KIND.get(kind_name, {}).get(species, SpeciesTraits())


# -- Config ---------------------------------------------------------------


@dataclass
class Config:
    plant_spread_chance: float = 0.06
    plant_max_growth: int = 3
    plant_seed_count: int = 1
    plant_cap_ratio: float = 0.25
    plant_max_age: int = 150
    plant_winter_dieoff: float = 0.08

    herb_start_energy: int = 14
    herb_eat_energy: int = 10
    herb_repro_threshold: int = 30
    herb_repro_cost: int = 14
    herb_vision: int = 5
    herb_flee_vision: int = 2
    herb_max_energy: int = 35
    herb_max_neighbors: int = 2

    carn_start_energy: int = 22
    carn_eat_energy: int = 10
    carn_repro_threshold: int = 34
    carn_repro_cost: int = 16
    carn_vision: int = 5
    carn_max_energy: int = 45
    carn_satiation: int = 28
    carn_max_neighbors: int = 2

    init_plant_ratio: float = 0.06
    init_herb_ratio: float = 0.012
    init_carn_ratio: float = 0.003
    water_ratio: float = 0.04

    drop_plant_n: int = 5
    drop_herb_n: int = 5
    drop_carn_n: int = 3

    season_length: int = 50

    disease_chance: float = 0.002
    disease_duration: int = 20
    disease_energy_drain: int = 2
    disease_spread_chance: float = 0.15
    disease_death_chance: float = 0.3

    nutrient_decay: float = 0.95
    nutrient_growth_bonus: float = 0.5
    nutrient_spawn_amount: float = 5.0

    thirst_rate: int = 1
    thirst_threshold: int = 30
    thirst_penalty: int = 2

    base_delay: float = 0.4


PRESETS: dict[str, dict] = {
    "balanced": {},
    "desert": {
        "init_plant_ratio": 0.02,
        "water_ratio": 0.08,
        "plant_spread_chance": 0.03,
        "init_herb_ratio": 0.008,
        "init_carn_ratio": 0.004,
        "plant_max_age": 100,
    },
    "paradise": {
        "init_plant_ratio": 0.12,
        "plant_spread_chance": 0.10,
        "init_herb_ratio": 0.02,
        "init_carn_ratio": 0.001,
        "disease_chance": 0.0,
    },
    "predator": {
        "init_plant_ratio": 0.04,
        "init_herb_ratio": 0.015,
        "init_carn_ratio": 0.01,
        "carn_start_energy": 30,
        "carn_vision": 7,
        "carn_satiation": 35,
    },
    "chaos": {
        "init_plant_ratio": 0.08,
        "init_herb_ratio": 0.02,
        "init_carn_ratio": 0.008,
        "plant_spread_chance": 0.12,
        "disease_chance": 0.01,
        "base_delay": 0.2,
        "season_length": 25,
    },
}


def make_config(preset: Optional[str] = None, **overrides) -> Config:
    cfg = Config()
    if preset and preset in PRESETS:
        for k, v in PRESETS[preset].items():
            setattr(cfg, k, v)
    for k, v in overrides.items():
        if hasattr(cfg, k):
            setattr(cfg, k, v)
    return cfg


# -- Emoji palettes -------------------------------------------------------

PLANT_STAGES = ["\U0001F331", "\U0001F33F", "\U0001F340", "\U0001F33E"]

ALL_HERBIVORES = [
    ("\U0001F430", "1", "rabbit"), ("\U0001F411", "2", "sheep"),
    ("\U0001F98C", "3", "deer"), ("\U0001F404", "4", "cow"),
    ("\U0001F410", "5", "goat"), ("\U0001F407", "6", "bunny"),
    ("\U0001F416", "7", "pig"), ("\U0001F40E", "8", "horse"),
]
ALL_CARNIVORES = [
    ("\U0001F981", "q", "lion"), ("\U0001F43A", "w", "wolf"),
    ("\U0001F98A", "e", "fox"), ("\U0001F43B", "r", "bear"),
    ("\U0001F42F", "t", "tiger"), ("\U0001F985", "y", "eagle"),
    ("\U0001F40D", "u", "snake"), ("\U0001F40A", "i", "crocodile"),
]

WATER_EMOJI = "\U0001F30A"
DISEASE_EMOJI = "\U0001F9A0"
EMPTY_STR = "  "
SPARK_CHARS = "\u2581\u2582\u2583\u2584\u2585\u2586\u2587\u2588"

EMOJI_TO_SPECIES: dict[str, str] = {}
for _e, _k, _s in ALL_HERBIVORES + ALL_CARNIVORES:
    EMOJI_TO_SPECIES[_e] = _s

EMOJI_TO_KEY: dict[str, str] = {}
for _e, _k, _s in ALL_HERBIVORES + ALL_CARNIVORES:
    EMOJI_TO_KEY[_e] = _k

_fake = Faker()

SEASON_NAMES = ["Spring", "Summer", "Autumn", "Winter"]
SEASON_PLANT_MOD =      [1.5, 1.0, 0.6, 0.2]
SEASON_ENERGY_MOD =     [0.8, 1.2, 1.0, 1.5]
SEASON_DIEOFF_CHANCE =  [0.0, 0.0, 0.02, 0.08]


# -- Model ----------------------------------------------------------------


class Kind(Enum):
    PLANT = 1
    HERBIVORE = 2
    CARNIVORE = 3
    WATER = 4


@dataclass
class Entity:
    kind: Kind
    emoji: str
    energy: int
    growth: int = 0
    age: int = 0
    name: Optional[str] = None
    species: str = ""
    traits: Optional[SpeciesTraits] = None
    thirst: int = 0
    diseased: int = 0

    @property
    def color(self) -> str:
        if self.traits:
            return self.traits.color
        return ""

    @property
    def is_diseased(self) -> bool:
        return self.diseased > 0


class Grid:
    def __init__(self, w: int, h: int):
        self.w = w
        self.h = h
        self.cells: list[list[Optional[Entity]]] = [[None] * w for _ in range(h)]
        self.nutrients: list[list[float]] = [[0.0] * w for _ in range(h)]

    def get(self, x: int, y: int) -> Optional[Entity]:
        if 0 <= x < self.w and 0 <= y < self.h:
            return self.cells[y][x]
        return None

    def neighbors(self, x: int, y: int) -> list[tuple[int, int]]:
        out: list[tuple[int, int]] = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if 0 <= nx < self.w and 0 <= ny < self.h:
                    out.append((nx, ny))
        return out

    def empty_neighbors(self, x: int, y: int) -> list[tuple[int, int]]:
        return [(nx, ny) for nx, ny in self.neighbors(x, y)
                if self.cells[ny][nx] is None]

    def passable_neighbors(self, x: int, y: int) -> list[tuple[int, int]]:
        out: list[tuple[int, int]] = []
        for nx, ny in self.neighbors(x, y):
            c = self.cells[ny][nx]
            if c is None or c.kind == Kind.PLANT:
                out.append((nx, ny))
        return out

    def random_empty(self, tries: int = 200) -> Optional[tuple[int, int]]:
        for _ in range(tries):
            x, y = random.randint(0, self.w - 1), random.randint(0, self.h - 1)
            if self.cells[y][x] is None:
                return (x, y)
        return None

    def add_nutrients(self, x: int, y: int, amount: float) -> None:
        if 0 <= x < self.w and 0 <= y < self.h:
            self.nutrients[y][x] += amount

    def decay_nutrients(self, rate: float) -> None:
        for y in range(self.h):
            for x in range(self.w):
                self.nutrients[y][x] *= rate


# -- Helpers --------------------------------------------------------------


def sign(n: int) -> int:
    return (n > 0) - (n < 0)


def find_nearest(grid: Grid, x: int, y: int, kind: Kind,
                 vision: int) -> Optional[tuple[int, int]]:
    for d in range(1, vision + 1):
        for dy in range(-d, d + 1):
            rem = d - abs(dy)
            if rem > 0:
                for dx in (-rem, rem):
                    nx, ny = x + dx, y + dy
                    c = grid.get(nx, ny)
                    if c and c.kind == kind:
                        return (nx, ny)
            else:
                nx, ny = x, y + dy
                c = grid.get(nx, ny)
                if c and c.kind == kind:
                    return (nx, ny)
    return None


def find_nearest_species(grid: Grid, x: int, y: int,
                         kind: Kind, species: str,
                         vision: int) -> Optional[tuple[int, int]]:
    for d in range(1, vision + 1):
        for dy in range(-d, d + 1):
            rem = d - abs(dy)
            if rem > 0:
                for dx in (-rem, rem):
                    nx, ny = x + dx, y + dy
                    c = grid.get(nx, ny)
                    if c and c.kind == kind and c.species == species:
                        return (nx, ny)
            else:
                nx, ny = x, y + dy
                c = grid.get(nx, ny)
                if c and c.kind == kind and c.species == species:
                    return (nx, ny)
    return None


def try_move(grid: Grid, x: int, y: int, e: Entity,
             nx: int, ny: int) -> bool:
    if 0 <= nx < grid.w and 0 <= ny < grid.h and grid.cells[ny][nx] is None:
        grid.cells[y][x] = None
        grid.cells[ny][nx] = e
        return True
    return False


def try_move_through_plants(grid: Grid, x: int, y: int, e: Entity,
                            nx: int, ny: int) -> bool:
    if 0 <= nx < grid.w and 0 <= ny < grid.h:
        target = grid.cells[ny][nx]
        if target is None or target.kind == Kind.PLANT:
            grid.cells[y][x] = None
            grid.cells[ny][nx] = e
            return True
    return False


def sparkline(values: list[int], max_val: int) -> str:
    if max_val <= 0:
        return SPARK_CHARS[0] * len(values)
    return "".join(
        SPARK_CHARS[min(7, max(0, int(v / max_val * 7.999)))] for v in values
    )


def random_name() -> str:
    return _fake.first_name()


def make_plant() -> Entity:
    g = random.randint(0, 3)
    return Entity(Kind.PLANT, PLANT_STAGES[g], 0, growth=g, species="plant")


def make_herb(selected: list[str]) -> Optional[Entity]:
    if not selected:
        return None
    emoji = random.choice(selected)
    species = EMOJI_TO_SPECIES.get(emoji, "herbivore")
    traits = HERBIVORE_TRAITS.get(species, SpeciesTraits())
    return Entity(
        Kind.HERBIVORE, emoji, traits.start_energy,
        name=random_name(), species=species, traits=traits,
    )


def make_herb_of_species(species: str) -> Optional[Entity]:
    traits = HERBIVORE_TRAITS.get(species)
    if traits is None:
        return None
    emoji = _SPECIES_TO_EMOJI.get(species)
    if emoji is None:
        return None
    return Entity(
        Kind.HERBIVORE, emoji, traits.start_energy,
        name=random_name(), species=species, traits=traits,
    )


def make_carn(selected: list[str]) -> Optional[Entity]:
    if not selected:
        return None
    emoji = random.choice(selected)
    species = EMOJI_TO_SPECIES.get(emoji, "carnivore")
    traits = CARNIVORE_TRAITS.get(species, SpeciesTraits())
    return Entity(
        Kind.CARNIVORE, emoji, traits.start_energy,
        name=random_name(), species=species, traits=traits,
    )


def make_carn_of_species(species: str) -> Optional[Entity]:
    traits = CARNIVORE_TRAITS.get(species)
    if traits is None:
        return None
    emoji = _SPECIES_TO_EMOJI.get(species)
    if emoji is None:
        return None
    return Entity(
        Kind.CARNIVORE, emoji, traits.start_energy,
        name=random_name(), species=species, traits=traits,
    )


def drop_creatures(grid: Grid, factory, n: int) -> None:
    for _ in range(n):
        spot = grid.random_empty()
        if spot:
            x, y = spot
            entity = factory()
            if entity:
                grid.cells[y][x] = entity


def species_of(emoji: str) -> str:
    return EMOJI_TO_SPECIES.get(emoji, "animal")


def make_event(kind: str, x: int, y: int, **kw) -> dict:
    return {"kind": kind, "x": x, "y": y, **kw}


# -- Statistics -----------------------------------------------------------


@dataclass
class Stats:
    total_births: int = 0
    total_kills: int = 0
    total_starvations: int = 0
    total_deaths_age: int = 0
    total_deaths_disease: int = 0
    peak_plants: int = 0
    peak_herbs: int = 0
    peak_carns: int = 0
    death_ages: list[int] = field(default_factory=list)

    @property
    def avg_lifespan(self) -> float:
        if not self.death_ages:
            return 0.0
        return sum(self.death_ages) / len(self.death_ages)

    @property
    def total_deaths(self) -> int:
        return (self.total_starvations + self.total_deaths_age
                + self.total_deaths_disease + self.total_kills)

    def record_death(self, age: int, cause: str) -> None:
        self.death_ages.append(age)
        if cause == "starve":
            self.total_starvations += 1
        elif cause == "age":
            self.total_deaths_age += 1
        elif cause == "disease":
            self.total_deaths_disease += 1
        elif cause == "kill":
            self.total_kills += 1

    def update_peaks(self, plants: int, herbs: int, carns: int) -> None:
        self.peak_plants = max(self.peak_plants, plants)
        self.peak_herbs = max(self.peak_herbs, herbs)
        self.peak_carns = max(self.peak_carns, carns)


# -- Game state -----------------------------------------------------------


@dataclass
class GameState:
    grid: Grid
    config: Config
    stats: Stats = field(default_factory=Stats)
    selected_herbs: list[str] = field(default_factory=list)
    selected_carns: list[str] = field(default_factory=list)
    tick: int = 0
    season: int = 0
    hist: dict[str, list[int]] = field(
        default_factory=lambda: {"plant": [], "herb": [], "carn": []})
    ticker: list[str] = field(default_factory=list)
    flashes: dict[tuple[int, int], str] = field(default_factory=dict)
    ticker_offset: int = 0
    notification: str = ""
    notification_ticks: int = 0

    @property
    def season_name(self) -> str:
        return SEASON_NAMES[self.season]

    @property
    def season_progress(self) -> int:
        return self.tick % self.config.season_length


# -- Simulation step ------------------------------------------------------


def count_pop(grid: Grid) -> dict[Kind, int]:
    counts = {Kind.PLANT: 0, Kind.HERBIVORE: 0, Kind.CARNIVORE: 0, Kind.WATER: 0}
    for y in range(grid.h):
        for x in range(grid.w):
            e = grid.cells[y][x]
            if e:
                counts[e.kind] = counts.get(e.kind, 0) + 1
    return counts


def count_by_species(grid: Grid, kind: Kind) -> dict[str, int]:
    counts: dict[str, int] = {}
    for y in range(grid.h):
        for x in range(grid.w):
            e = grid.cells[y][x]
            if e and e.kind == kind and e.species:
                counts[e.species] = counts.get(e.species, 0) + 1
    return counts


def step(state: GameState, events: list[dict]) -> None:
    grid = state.grid
    config = state.config

    state.season = (state.tick // config.season_length) % 4
    plant_mod = SEASON_PLANT_MOD[state.season]
    energy_mod = SEASON_ENERGY_MOD[state.season]
    dieoff_chance = SEASON_DIEOFF_CHANCE[state.season]

    entities: list[tuple[int, int, Entity]] = []
    for y in range(grid.h):
        for x in range(grid.w):
            e = grid.cells[y][x]
            if e and e.kind in (Kind.PLANT, Kind.HERBIVORE, Kind.CARNIVORE):
                entities.append((x, y, e))
    random.shuffle(entities)

    births: list[tuple[int, int, Entity]] = []
    plant_n = sum(1 for row in grid.cells for c in row
                  if c and c.kind == Kind.PLANT)
    plant_cap = grid.w * grid.h * config.plant_cap_ratio

    for x, y, e in entities:
        if grid.cells[y][x] is not e:
            continue
        e.age += 1
        if e.kind == Kind.PLANT:
            _tick_plant(state, x, y, e, births, plant_n, plant_cap,
                        plant_mod, dieoff_chance)
        elif e.kind == Kind.HERBIVORE:
            _tick_herb(state, x, y, e, births, events, energy_mod)
        elif e.kind == Kind.CARNIVORE:
            _tick_carn(state, x, y, e, births, events, energy_mod)

    for bx, by, be in births:
        if grid.cells[by][bx] is None:
            grid.cells[by][bx] = be

    plant_n = sum(1 for row in grid.cells for c in row
                  if c and c.kind == Kind.PLANT)
    if plant_n < plant_cap:
        adjusted_cap = plant_cap
        for _ in range(config.plant_seed_count):
            spot = grid.random_empty(50)
            if spot:
                x, y = spot
                grid.cells[y][x] = make_plant()

    grid.decay_nutrients(config.nutrient_decay)

    state.tick += 1
    c = count_pop(grid)
    state.hist["plant"].append(c[Kind.PLANT])
    state.hist["herb"].append(c[Kind.HERBIVORE])
    state.hist["carn"].append(c[Kind.CARNIVORE])
    for k in state.hist:
        if len(state.hist[k]) > 200:
            state.hist[k] = state.hist[k][-200:]
    state.stats.update_peaks(c[Kind.PLANT], c[Kind.HERBIVORE], c[Kind.CARNIVORE])


def _tick_plant(state: GameState, x: int, y: int, e: Entity,
                births: list, plant_n: int, plant_cap: float,
                plant_mod: float, dieoff_chance: float) -> None:
    grid = state.grid
    config = state.config

    if e.age > config.plant_max_age:
        grid.cells[y][x] = None
        grid.add_nutrients(x, y, 2.0)
        return

    if dieoff_chance > 0 and random.random() < dieoff_chance:
        grid.cells[y][x] = None
        grid.add_nutrients(x, y, 1.0)
        return

    if e.growth < config.plant_max_growth:
        nutrient_bonus = grid.nutrients[y][x] * config.nutrient_growth_bonus
        if random.random() < (0.3 + nutrient_bonus) * plant_mod:
            e.growth += 1
            e.emoji = PLANT_STAGES[e.growth]

    spread_chance = config.plant_spread_chance * plant_mod
    if plant_n < plant_cap and random.random() < spread_chance:
        empties = grid.empty_neighbors(x, y)
        if empties:
            nx, ny = random.choice(empties)
            births.append((nx, ny, make_plant()))


def _tick_herb(state: GameState, x: int, y: int, e: Entity,
               births: list, events: list, energy_mod: float) -> None:
    grid = state.grid
    config = state.config
    traits = e.traits or SpeciesTraits()

    if e.is_diseased:
        e.energy -= int(config.disease_energy_drain * energy_mod)
        e.diseased -= 1
        if e.diseased <= 0:
            if random.random() < config.disease_death_chance:
                grid.cells[y][x] = None
                grid.add_nutrients(x, y, config.nutrient_spawn_amount)
                state.stats.record_death(e.age, "disease")
                events.append(make_event("disease_death", x, y,
                    emoji=e.emoji, name=e.name, species=e.species))
                return
    else:
        if random.random() < config.disease_chance:
            e.diseased = config.disease_duration

    if traits.speed > 1 and e.age % traits.speed != 0:
        pass
    else:
        e.energy -= max(1, int(1 * energy_mod))

    e.thirst += config.thirst_rate
    if e.thirst > config.thirst_threshold:
        e.energy -= config.thirst_penalty

    for nx, ny in grid.neighbors(x, y):
        c = grid.cells[ny][nx]
        if c and c.kind == Kind.WATER:
            e.thirst = 0
            break

    if e.is_diseased and e.diseased > 0:
        for nx, ny in grid.neighbors(x, y):
            c = grid.cells[ny][nx]
            if c and c.kind == Kind.HERBIVORE and not c.is_diseased:
                if random.random() < config.disease_spread_chance:
                    c.diseased = config.disease_duration

    threat = find_nearest(grid, x, y, Kind.CARNIVORE, traits.flee_vision)
    if threat:
        tx, ty = threat
        nx, ny = x + sign(x - tx), y + sign(y - ty)
        if try_move(grid, x, y, e, nx, ny):
            x, y = nx, ny
    else:
        adjacent_plant = None
        for ax, ay in grid.neighbors(x, y):
            c = grid.cells[ay][ax]
            if c and c.kind == Kind.PLANT:
                adjacent_plant = (ax, ay, c)
                break
        if adjacent_plant:
            ax, ay, plant = adjacent_plant
            e.energy = min(e.energy + traits.eat_energy + plant.growth * 3,
                           traits.max_energy)
            grid.cells[ay][ax] = None
        else:
            food = find_nearest(grid, x, y, Kind.PLANT, traits.vision)
            if food:
                fx, fy = food
                nx, ny = x + sign(fx - x), y + sign(fy - y)
                if try_move(grid, x, y, e, nx, ny):
                    x, y = nx, ny
            else:
                empties = grid.empty_neighbors(x, y)
                if empties:
                    nx, ny = random.choice(empties)
                    if try_move(grid, x, y, e, nx, ny):
                        x, y = nx, ny

    if state.selected_herbs and e.energy >= traits.repro_threshold:
        same_species = sum(
            1 for nx, ny in grid.neighbors(x, y)
            if grid.cells[ny][nx] and grid.cells[ny][nx].kind == Kind.HERBIVORE
            and grid.cells[ny][nx].species == e.species
        )
        total_herbs = sum(
            1 for nx, ny in grid.neighbors(x, y)
            if grid.cells[ny][nx] and grid.cells[ny][nx].kind == Kind.HERBIVORE
        )
        if total_herbs < traits.max_neighbors:
            effective_threshold = traits.repro_threshold * (
                1.0 - traits.pack_bonus * min(same_species, 3))
            if e.energy >= effective_threshold:
                empties = grid.empty_neighbors(x, y)
                if empties:
                    nx, ny = random.choice(empties)
                    e.energy -= traits.repro_cost
                    baby = make_herb_of_species(e.species)
                    if baby:
                        births.append((nx, ny, baby))
                        state.stats.total_births += 1
                        events.append(make_event("birth", nx, ny,
                            emoji=baby.emoji, name=baby.name,
                            species=baby.species,
                            parent_name=e.name, parent_emoji=e.emoji))

    if e.age > traits.max_age:
        grid.cells[y][x] = None
        grid.add_nutrients(x, y, config.nutrient_spawn_amount)
        state.stats.record_death(e.age, "age")
        events.append(make_event("age_death", x, y,
            emoji=e.emoji, name=e.name, species=e.species))
        return

    if e.energy <= 0:
        grid.cells[y][x] = None
        grid.add_nutrients(x, y, config.nutrient_spawn_amount * 0.5)
        state.stats.record_death(e.age, "starve")
        events.append(make_event("starve", x, y,
            emoji=e.emoji, name=e.name, species=e.species))


def _tick_carn(state: GameState, x: int, y: int, e: Entity,
               births: list, events: list, energy_mod: float) -> None:
    grid = state.grid
    config = state.config
    traits = e.traits or SpeciesTraits()

    if e.is_diseased:
        e.energy -= int(config.disease_energy_drain * energy_mod)
        e.diseased -= 1
        if e.diseased <= 0:
            if random.random() < config.disease_death_chance:
                grid.cells[y][x] = None
                grid.add_nutrients(x, y, config.nutrient_spawn_amount)
                state.stats.record_death(e.age, "disease")
                events.append(make_event("disease_death", x, y,
                    emoji=e.emoji, name=e.name, species=e.species))
                return
    else:
        if random.random() < config.disease_chance:
            e.diseased = config.disease_duration

    if traits.speed > 1 and e.age % traits.speed != 0:
        pass
    else:
        e.energy -= max(1, int(1 * energy_mod))

    e.thirst += config.thirst_rate
    if e.thirst > config.thirst_threshold:
        e.energy -= config.thirst_penalty

    for nx, ny in grid.neighbors(x, y):
        c = grid.cells[ny][nx]
        if c and c.kind == Kind.WATER:
            e.thirst = 0
            break

    if e.is_diseased and e.diseased > 0:
        for nx, ny in grid.neighbors(x, y):
            c = grid.cells[ny][nx]
            if c and c.kind == Kind.CARNIVORE and not c.is_diseased:
                if random.random() < config.disease_spread_chance:
                    c.diseased = config.disease_duration

    adjacent_prey = None
    if e.energy < traits.max_energy * 0.6:
        for ax, ay in grid.neighbors(x, y):
            c = grid.cells[ay][ax]
            if c and c.kind == Kind.HERBIVORE:
                adjacent_prey = (ax, ay, c)
                break

    adjacent_carn_prey = None
    if not adjacent_prey:
        dire = e.energy < traits.max_energy * 0.2
        hungry_carn = traits.can_hunt_carns or e.energy < traits.max_energy * 0.4
        if dire or hungry_carn:
            for ax, ay in grid.neighbors(x, y):
                c = grid.cells[ay][ax]
                if not c or c.kind != Kind.CARNIVORE or c is e:
                    continue
                if not c.traits:
                    continue
                if c.species == e.species and not dire:
                    continue
                if c.traits.max_energy < traits.max_energy or dire:
                    adjacent_carn_prey = (ax, ay, c)
                    break

    if adjacent_prey:
        ax, ay, prey = adjacent_prey
        e.energy = min(e.energy + traits.eat_energy, traits.max_energy)
        grid.cells[ay][ax] = None
        grid.add_nutrients(ax, ay, config.nutrient_spawn_amount * 0.5)
        state.stats.record_death(prey.age, "kill")
        events.append(make_event("kill", ax, ay,
            predator_emoji=e.emoji, predator_name=e.name,
            predator_species=e.species,
            prey_emoji=prey.emoji, prey_name=prey.name,
            prey_species=prey.species))
    elif adjacent_carn_prey:
        ax, ay, target = adjacent_carn_prey
        e.energy = min(e.energy + traits.eat_energy, traits.max_energy)
        grid.cells[ay][ax] = None
        grid.add_nutrients(ax, ay, config.nutrient_spawn_amount * 0.5)
        state.stats.record_death(target.age, "kill")
        same_species = target.species == e.species
        ev_kind = "carn_kill" if not same_species else "carn_kill"
        events.append(make_event(ev_kind, ax, ay,
            predator_emoji=e.emoji, predator_name=e.name,
            predator_species=e.species,
            prey_emoji=target.emoji, prey_name=target.name,
            prey_species=target.species))
    else:
        prey = find_nearest(grid, x, y, Kind.HERBIVORE, traits.vision)
        if prey:
            px, py = prey
            nx, ny = x + sign(px - x), y + sign(py - y)
            if try_move_through_plants(grid, x, y, e, nx, ny):
                x, y = nx, ny
                for ax, ay in grid.neighbors(x, y):
                    c = grid.cells[ay][ax]
                    if c and c.kind == Kind.HERBIVORE:
                        e.energy = min(e.energy + traits.eat_energy,
                                       traits.max_energy)
                        grid.cells[ay][ax] = None
                        grid.add_nutrients(ax, ay, config.nutrient_spawn_amount * 0.5)
                        state.stats.record_death(c.age, "kill")
                        events.append(make_event("kill", ax, ay,
                            predator_emoji=e.emoji, predator_name=e.name,
                            predator_species=e.species,
                            prey_emoji=c.emoji, prey_name=c.name,
                            prey_species=c.species))
                        break
        else:
            dire = e.energy < traits.max_energy * 0.2
            hungry_carn = traits.can_hunt_carns or e.energy < traits.max_energy * 0.4
            carn_target = None
            if hungry_carn:
                carn_target = _find_carn_prey(
                    grid, x, y, traits, traits.vision, e, dire)
            if carn_target:
                sx, sy, target = carn_target
                nx, ny = x + sign(sx - x), y + sign(sy - y)
                if try_move_through_plants(grid, x, y, e, nx, ny):
                    x, y = nx, ny
                    for ax, ay in grid.neighbors(x, y):
                        c = grid.cells[ay][ax]
                        if not c or c.kind != Kind.CARNIVORE or c is e:
                            continue
                        if not c.traits:
                            continue
                        is_valid = (dire or
                                    (c.species != e.species and
                                     c.traits.max_energy < traits.max_energy) or
                                    (dire and c.species == e.species))
                        if is_valid:
                            e.energy = min(e.energy + traits.eat_energy,
                                           traits.max_energy)
                            grid.cells[ay][ax] = None
                            grid.add_nutrients(ax, ay, config.nutrient_spawn_amount * 0.5)
                            state.stats.record_death(c.age, "kill")
                            events.append(make_event("carn_kill", ax, ay,
                                predator_emoji=e.emoji, predator_name=e.name,
                                predator_species=e.species,
                                prey_emoji=c.emoji, prey_name=c.name,
                                prey_species=c.species))
                            break
            else:
                passables = grid.passable_neighbors(x, y)
                if passables:
                    nx, ny = random.choice(passables)
                    if try_move_through_plants(grid, x, y, e, nx, ny):
                        x, y = nx, ny

    if state.selected_carns and e.energy >= traits.repro_threshold:
        same_species = sum(
            1 for nx, ny in grid.neighbors(x, y)
            if grid.cells[ny][nx] and grid.cells[ny][nx].kind == Kind.CARNIVORE
            and grid.cells[ny][nx].species == e.species
        )
        total_carns = sum(
            1 for nx, ny in grid.neighbors(x, y)
            if grid.cells[ny][nx] and grid.cells[ny][nx].kind == Kind.CARNIVORE
        )
        if total_carns < traits.max_neighbors:
            effective_threshold = traits.repro_threshold * (
                1.0 - traits.pack_bonus * min(same_species, 3))
            if e.energy >= effective_threshold:
                empties = grid.empty_neighbors(x, y)
                if empties:
                    nx, ny = random.choice(empties)
                    e.energy -= traits.repro_cost
                    baby = make_carn_of_species(e.species)
                    if baby:
                        births.append((nx, ny, baby))
                        state.stats.total_births += 1
                        events.append(make_event("birth", nx, ny,
                            emoji=baby.emoji, name=baby.name,
                            species=baby.species,
                            parent_name=e.name, parent_emoji=e.emoji))

    if e.age > traits.max_age:
        grid.cells[y][x] = None
        grid.add_nutrients(x, y, config.nutrient_spawn_amount)
        state.stats.record_death(e.age, "age")
        events.append(make_event("age_death", x, y,
            emoji=e.emoji, name=e.name, species=e.species))
        return

    if e.energy <= 0:
        grid.cells[y][x] = None
        grid.add_nutrients(x, y, config.nutrient_spawn_amount * 0.5)
        state.stats.record_death(e.age, "starve")
        events.append(make_event("starve", x, y,
            emoji=e.emoji, name=e.name, species=e.species))


def _find_carn_prey(grid: Grid, x: int, y: int,
                    traits: SpeciesTraits, vision: int,
                    predator: Entity,
                    dire: bool) -> Optional[tuple[int, int, Entity]]:
    for d in range(1, vision + 1):
        for dy in range(-d, d + 1):
            rem = d - abs(dy)
            if rem > 0:
                for dx in (-rem, rem):
                    nx, ny = x + dx, y + dy
                    c = grid.get(nx, ny)
                    if not c or c.kind != Kind.CARNIVORE or c is predator:
                        continue
                    if not c.traits:
                        continue
                    if dire:
                        return (nx, ny, c)
                    if c.species != predator.species and c.traits.max_energy < traits.max_energy:
                        return (nx, ny, c)
            else:
                nx, ny = x, y + dy
                c = grid.get(nx, ny)
                if not c or c.kind != Kind.CARNIVORE or c is predator:
                    continue
                if not c.traits:
                    continue
                if dire:
                    return (nx, ny, c)
                if c.species != predator.species and c.traits.max_energy < traits.max_energy:
                    return (nx, ny, c)
    return None


# -- Setup ----------------------------------------------------------------


def _place_water(grid: Grid, n_water: int) -> None:
    seeds = max(1, n_water // 6)
    placed = 0
    for _ in range(seeds):
        x = random.randint(0, grid.w - 1)
        y = random.randint(0, grid.h - 1)
        if grid.cells[y][x] is None:
            grid.cells[y][x] = Entity(Kind.WATER, WATER_EMOJI, 0, species="water")
            placed += 1
        cluster_size = random.randint(2, 7)
        cx, cy = x, y
        for _ in range(cluster_size):
            dx, dy = random.choice([(-1, 0), (1, 0), (0, -1), (0, 1)])
            cx, cy = cx + dx, cy + dy
            if 0 <= cx < grid.w and 0 <= cy < grid.h and grid.cells[cy][cx] is None:
                grid.cells[cy][cx] = Entity(Kind.WATER, WATER_EMOJI, 0, species="water")
                placed += 1
        if placed >= n_water:
            break


def populate(grid: Grid, config: Config,
             selected_herbs: list[str],
             selected_carns: list[str]) -> None:
    total = grid.w * grid.h
    n_water = int(total * config.water_ratio)
    n_plants = int(total * config.init_plant_ratio)
    n_herbs = int(total * config.init_herb_ratio) if selected_herbs else 0
    n_carns = int(total * config.init_carn_ratio) if selected_carns else 0

    _place_water(grid, n_water)

    def fill(n: int, factory) -> None:
        for _ in range(n):
            for _ in range(200):
                xr = random.randint(0, grid.w - 1)
                yr = random.randint(0, grid.h - 1)
                if grid.cells[yr][xr] is None:
                    entity = factory()
                    if entity:
                        grid.cells[yr][xr] = entity
                    break

    fill(n_plants, make_plant)
    fill(n_herbs, lambda: make_herb(selected_herbs))
    fill(n_carns, lambda: make_carn(selected_carns))


# -- Species picker -------------------------------------------------------


def _render_picker(herb_on: dict[str, bool], carn_on: dict[str, bool]) -> None:
    lines = []
    lines.append("\033[H  Emoji Zoo  --  Choose your animals\033[K")
    lines.append("  Toggle species on/off. Each has unique traits!\033[K")
    lines.append("\033[K")

    lines.append("  HERBIVORES (plant eaters)\033[K")
    for emoji, key, species in ALL_HERBIVORES:
        on = herb_on.get(emoji, True)
        mark = "\033[32m\xe2\x9c\x93\033[0m" if on else "\033[31m\xe2\x9c\x97\033[0m"
        t = HERBIVORE_TRAITS.get(species, SpeciesTraits())
        trait_str = f"vision:{t.vision} life:{t.max_age} breed:{t.repro_threshold}"
        lines.append(f"    {key}) {emoji}  {species:10s}  [{mark}]  {trait_str}\033[K")
    lines.append("\033[K")

    lines.append("  CARNIVORES (hunters)\033[K")
    for emoji, key, species in ALL_CARNIVORES:
        on = carn_on.get(emoji, True)
        mark = "\033[32m\xe2\x9c\x93\033[0m" if on else "\033[31m\xe2\x9c\x97\033[0m"
        t = CARNIVORE_TRAITS.get(species, SpeciesTraits())
        hunt = "can hunt carns" if t.can_hunt_carns else "no intra-pred"
        trait_str = f"vision:{t.vision} life:{t.max_age} {hunt}"
        lines.append(f"    {key}) {emoji}  {species:12s}  [{mark}]  {trait_str}\033[K")
    lines.append("\033[K")

    n_h = sum(herb_on.values())
    n_c = sum(carn_on.values())
    lines.append(f"  {n_h} herbivore(s), {n_c} carnivore(s) selected\033[K")
    lines.append("  a = all on  n = all off  Enter = start\033[K")

    sys.stdout.write("\n".join(lines) + "\033[J")
    sys.stdout.flush()


def species_picker() -> tuple[list[str], list[str]]:
    herb_on = {e: True for e, _, _ in ALL_HERBIVORES}
    carn_on = {e: True for e, _, _ in ALL_CARNIVORES}

    herb_keys = {k: e for e, k, _ in ALL_HERBIVORES}
    carn_keys = {k: e for e, k, _ in ALL_CARNIVORES}

    old = termios.tcgetattr(sys.stdin)
    tty.setcbreak(sys.stdin.fileno())
    sys.stdout.write("\033[?25l\033[2J")

    try:
        _render_picker(herb_on, carn_on)
        while True:
            r, _, _ = select.select([sys.stdin], [], [], None)
            if not r:
                continue
            ch = sys.stdin.read(1)
            if ch in ("\r", "\n"):
                break
            elif ch == "a":
                herb_on = {e: True for e, _, _ in ALL_HERBIVORES}
                carn_on = {e: True for e, _, _ in ALL_CARNIVORES}
            elif ch == "n":
                herb_on = {e: False for e, _, _ in ALL_HERBIVORES}
                carn_on = {e: False for e, _, _ in ALL_CARNIVORES}
            elif ch in herb_keys:
                e = herb_keys[ch]
                herb_on[e] = not herb_on[e]
            elif ch in carn_keys:
                e = carn_keys[ch]
                carn_on[e] = not carn_on[e]
            elif ch == "\x03":
                sys.stdout.write("\033[0m\033[?25h\033[2J\033[H")
                sys.stdout.flush()
                sys.exit(0)
            _render_picker(herb_on, carn_on)
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old)

    sel_herbs = [e for e, _, _ in ALL_HERBIVORES if herb_on[e]]
    sel_carns = [e for e, _, _ in ALL_CARNIVORES if carn_on[e]]

    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()
    return sel_herbs, sel_carns


# -- Save / Load ----------------------------------------------------------


def save_state(state: GameState, filepath: str) -> bool:
    try:
        data = {
            "tick": state.tick,
            "season": state.season,
            "selected_herbs": state.selected_herbs,
            "selected_carns": state.selected_carns,
            "config": asdict(state.config),
            "stats": {
                "total_births": state.stats.total_births,
                "total_kills": state.stats.total_kills,
                "total_starvations": state.stats.total_starvations,
                "total_deaths_age": state.stats.total_deaths_age,
                "total_deaths_disease": state.stats.total_deaths_disease,
                "peak_plants": state.stats.peak_plants,
                "peak_herbs": state.stats.peak_herbs,
                "peak_carns": state.stats.peak_carns,
                "death_ages": state.stats.death_ages[-200:],
            },
            "hist": state.hist,
            "ticker": state.ticker[-50:],
            "grid": {
                "w": state.grid.w,
                "h": state.grid.h,
                "cells": [[_entity_to_dict(c) for c in row]
                          for row in state.grid.cells],
                "nutrients": state.grid.nutrients,
            },
        }
        with open(filepath, "w") as f:
            json.dump(data, f)
        return True
    except Exception as e:
        logger.error("Save failed: %s", e)
        return False


def load_state(filepath: str) -> Optional[GameState]:
    try:
        with open(filepath) as f:
            data = json.load(f)

        config = Config(**data["config"])
        grid = Grid(data["grid"]["w"], data["grid"]["h"])
        for y in range(grid.h):
            for x in range(grid.w):
                cd = data["grid"]["cells"][y][x]
                if cd:
                    grid.cells[y][x] = _dict_to_entity(cd)
                grid.nutrients[y][x] = data["grid"]["nutrients"][y][x]

        stats = Stats(
            total_births=data["stats"]["total_births"],
            total_kills=data["stats"]["total_kills"],
            total_starvations=data["stats"]["total_starvations"],
            total_deaths_age=data["stats"]["total_deaths_age"],
            total_deaths_disease=data["stats"]["total_deaths_disease"],
            peak_plants=data["stats"]["peak_plants"],
            peak_herbs=data["stats"]["peak_herbs"],
            peak_carns=data["stats"]["peak_carns"],
            death_ages=data["stats"]["death_ages"],
        )

        state = GameState(
            grid=grid, config=config, stats=stats,
            selected_herbs=data["selected_herbs"],
            selected_carns=data["selected_carns"],
            tick=data["tick"], season=data["season"],
            hist=data["hist"], ticker=data["ticker"],
        )
        return state
    except Exception as e:
        logger.error("Load failed: %s", e)
        return None


def _entity_to_dict(e: Optional[Entity]) -> Optional[dict]:
    if e is None:
        return None
    return {
        "kind": e.kind.name,
        "emoji": e.emoji,
        "energy": e.energy,
        "growth": e.growth,
        "age": e.age,
        "name": e.name,
        "species": e.species,
        "thirst": e.thirst,
        "diseased": e.diseased,
    }


def _dict_to_entity(d: dict) -> Entity:
    kind = Kind[d["kind"]]
    species = d.get("species", "")
    traits = None
    if kind == Kind.HERBIVORE:
        traits = HERBIVORE_TRAITS.get(species, SpeciesTraits())
    elif kind == Kind.CARNIVORE:
        traits = CARNIVORE_TRAITS.get(species, SpeciesTraits())
    return Entity(
        kind=kind, emoji=d["emoji"], energy=d["energy"],
        growth=d.get("growth", 0), age=d.get("age", 0),
        name=d.get("name"), species=species,
        traits=traits, thirst=d.get("thirst", 0),
        diseased=d.get("diseased", 0),
    )


# -- Event formatting -----------------------------------------------------


FLASH_EMOJIS = {
    "kill": "\U0001F4A5", "birth": "\u2728", "starve": "\U0001F480",
    "age_death": "\U0001F534", "disease_death": "\U0001F9A0",
    "carn_kill": "\U0001F4A5",
}
FLASH_COLORS = {
    "kill": "\033[41m", "birth": "\033[44m", "starve": "\033[100m",
    "age_death": "\033[45m", "disease_death": "\033[48;5;52m",
    "carn_kill": "\033[41m",
}


def event_to_message(ev: dict) -> str:
    kind = ev["kind"]
    if kind == "kill":
        return (f"{ev['predator_emoji']} {ev['predator_name']} the {ev['predator_species']}"
                f" caught {ev['prey_emoji']} {ev['prey_name']} the {ev['prey_species']}!")
    elif kind == "carn_kill":
        return (f"{ev['predator_emoji']} {ev['predator_name']} the {ev['predator_species']}"
                f" hunted down {ev['prey_emoji']} {ev['prey_name']} the {ev['prey_species']}!")
    elif kind == "birth":
        return (f"\u2728 {ev['parent_emoji']} {ev['parent_name']} had a baby: "
                f"{ev['emoji']} {ev['name']} the {ev['species']}!")
    elif kind == "starve":
        return (f"\U0001F480 {ev['emoji']} {ev['name']} the {ev['species']} starved")
    elif kind == "age_death":
        return (f"\U0001F534 {ev['emoji']} {ev['name']} the {ev['species']}"
                f" died of old age ({ev.get('age', '?')} ticks)")
    elif kind == "disease_death":
        return (f"\U0001F9A0 {ev['emoji']} {ev['name']} the {ev['species']}"
                f" succumbed to disease")
    return ""


# -- Render ---------------------------------------------------------------


def render(state: GameState, paused: bool, speed: int,
           god_mode: bool, cursor: tuple[int, int],
           show_help: bool, show_params: bool, param_sel: int,
           terminal_resized: bool) -> None:
    grid = state.grid
    counts = count_pop(grid)
    p = counts[Kind.PLANT]
    h = counts[Kind.HERBIVORE]
    c = counts[Kind.CARNIVORE]

    cx, cy = cursor
    if show_params:
        status = "** PARAMS **  up/down select  +/- adjust  Enter/ESC close"
    elif god_mode:
        status = "** GOD MODE **  arrows  1/2/3 place  x delete  i inspect  ESC exit"
    elif paused:
        status = "PAUSED"
    else:
        status = "running"

    lines: list[str] = []
    season_bar = " ".join(
        f"{'>' if i == state.season else ' '}{SEASON_NAMES[i][:3]}"
        for i in range(4)
    )
    lines.append(
        f"\033[H  Emoji Zoo  --  tick {state.tick:>5}  speed {speed}x  [{status}]"
        f"  {state.season_name} ({state.season_progress}/{state.config.season_length})"
        f"  [{season_bar}]\033[K"
    )

    herb_sample = "  ".join(state.selected_herbs[:5]) if state.selected_herbs else "(none)"
    carn_sample = "  ".join(state.selected_carns[:5]) if state.selected_carns else "(none)"
    lines.append(
        f"  \U0001F33F plants \u2192 {herb_sample} herbivores \u2192 {carn_sample} carnivores\033[K"
    )
    lines.append("\033[K")

    for y in range(grid.h):
        row = ""
        for x in range(grid.w):
            if (x, y) in state.flashes:
                fkind = state.flashes[(x, y)]
                femoji = FLASH_EMOJIS.get(fkind, "?")
                color = FLASH_COLORS.get(fkind, "")
                row += f"{color}{femoji}\033[0m"
            else:
                e = grid.cells[y][x]
                if e is None:
                    content = EMPTY_STR
                else:
                    content = e.emoji
                    if e.is_diseased:
                        content = f"\033[48;5;52m{content}\033[0m"
                    elif e.color and e.kind in (Kind.HERBIVORE, Kind.CARNIVORE):
                        content = f"{e.color}{content}\033[0m"
                if god_mode and x == cx and y == cy:
                    row += f"\033[44m{content}\033[0m"
                else:
                    row += content
        lines.append(row + "\033[K")

    lines.append("\033[K")

    hist_max = max(
        max(state.hist["plant"]) if state.hist["plant"] else 1,
        max(state.hist["herb"]) if state.hist["herb"] else 1,
        max(state.hist["carn"]) if state.hist["carn"] else 1,
        1,
    )

    sp = sparkline(state.hist["plant"][-50:], hist_max)
    sh = sparkline(state.hist["herb"][-50:], hist_max)
    sc = sparkline(state.hist["carn"][-50:], hist_max)

    lines.append(f"  \U0001F33F plants      {p:>4}  {sp}\033[K")
    first_herb = state.selected_herbs[0] if state.selected_herbs else "?"
    lines.append(f"  {first_herb} herbivores  {h:>4}  {sh}\033[K")
    first_carn = state.selected_carns[0] if state.selected_carns else "?"
    lines.append(f"  {first_carn} carnivores  {c:>4}  {sc}\033[K")

    herb_species = count_by_species(grid, Kind.HERBIVORE)
    carn_species = count_by_species(grid, Kind.CARNIVORE)
    herb_str = "  ".join(f"{EMOJI_TO_SPECIES_TO_EMOJI(s)}{n}"
                        for s, n in sorted(herb_species.items(), key=lambda x: -x[1])[:6])
    carn_str = "  ".join(f"{EMOJI_TO_SPECIES_TO_EMOJI(s)}{n}"
                        for s, n in sorted(carn_species.items(), key=lambda x: -x[1])[:6])
    if herb_str or carn_str:
        lines.append(f"  {herb_str or '(none)'}  |  {carn_str or '(none)'}\033[K")
    else:
        lines.append("\033[K")

    lines.append("\033[K")

    s = state.stats
    lines.append(
        f"  Births:{s.total_births} Kills:{s.total_kills} "
        f"Starved:{s.total_starvations} Age:{s.total_deaths_age} "
        f"Disease:{s.total_deaths_disease}  |  "
        f"Peaks: P{s.peak_plants} H{s.peak_herbs} C{s.peak_carns}\033[K"
    )
    avg = f"{s.avg_lifespan:.0f}" if s.avg_lifespan > 0 else "-"
    lines.append(f"  Avg lifespan: {avg} ticks  Total deaths: {s.total_deaths}\033[K")

    lines.append("\033[K")

    total_ticker = len(state.ticker)
    if total_ticker > 0:
        base = max(0, total_ticker - 3 + state.ticker_offset)
        for i in range(3):
            idx = base + i
            if 0 <= idx < total_ticker:
                msg = state.ticker[idx]
                if len(msg) > 70:
                    msg = msg[:67] + "..."
                lines.append(f"  {msg}\033[K")
            else:
                lines.append("\033[K")
    else:
        for _ in range(3):
            lines.append("\033[K")

    if god_mode:
        e = grid.get(cx, cy)
        if e:
            info = f"  {e.emoji} {e.name or '?'} the {e.species}"
            if e.traits:
                info += f"  energy:{e.energy}/{e.traits.max_energy}"
                info += f"  age:{e.age}/{e.traits.max_age}"
            else:
                info += f"  energy:{e.energy}  age:{e.age}"
            info += f"  thirst:{e.thirst}"
            if e.is_diseased:
                info += f"  diseased:{e.diseased}t"
            info += f"  [{cx},{cy}]\033[K"
        else:
            info = f"  (empty)  [{cx},{cy}]\033[K"
        lines.append(info)
    else:
        lines.append("\033[K")

    lines.append("\033[K")
    lines.append(
        "  SPACE pause  s step  +/- speed  r reset  1/2/3 drop  g god"
        "  p params  h help  [/] scroll  S save  L load  q quit\033[K"
    )

    if show_help:
        lines.append("\033[K")
        lines.append("  -- HELP --\033[K")
        lines.append("  SPACE  pause/resume    s     step one tick     +/-  speed\033[K")
        lines.append("  r      reset           1/2/3 drop creatures    g    god mode\033[K")
        lines.append("  arrows move cursor     1/2/3 place in god     x    delete\033[K")
        lines.append("  p      tune params     h/?   this help         S    save\033[K")
        lines.append("  L      load            [ / ] scroll events    q    quit\033[K")

    if show_params:
        lines.append("\033[K")
        lines.append("  -- PARAMETERS (up/down select, +/- adjust) --\033[K")
        params = _param_list(state.config)
        for i, (name, val) in enumerate(params):
            mark = ">" if i == param_sel else " "
            lines.append(f"  {mark} {name}: {val}\033[K")

    if state.notification_ticks > 0 and state.notification:
        lines.append(f"\033[K")
        lines.append(f"  \033[44m {state.notification} \033[0m\033[K")
        state.notification_ticks -= 1

    sys.stdout.write("\n".join(lines))
    sys.stdout.flush()


_SPECIES_TO_EMOJI: dict[str, str] = {}


def _build_species_emoji_map() -> None:
    for e, _, s in ALL_HERBIVORES + ALL_CARNIVORES:
        _SPECIES_TO_EMOJI[s] = e


_build_species_emoji_map()


def EMOJI_TO_SPECIES_TO_EMOJI(species: str) -> str:
    return _SPECIES_TO_EMOJI.get(species, "?")


def _param_list(config: Config) -> list[tuple[str, str]]:
    return [
        ("Plant spread", f"{config.plant_spread_chance:.3f}"),
        ("Plant cap ratio", f"{config.plant_cap_ratio:.2f}"),
        ("Plant max age", str(config.plant_max_age)),
        ("Herb repro thresh", str(config.herb_repro_threshold)),
        ("Carn repro thresh", str(config.carn_repro_threshold)),
        ("Carn satiation", str(config.carn_satiation)),
        ("Disease chance", f"{config.disease_chance:.4f}"),
        ("Season length", str(config.season_length)),
        ("Base delay", f"{config.base_delay:.2f}s"),
    ]


def _adjust_param(config: Config, idx: int, direction: int) -> None:
    adjustments = [
        ("plant_spread_chance", 0.01, 0.01, 0.30),
        ("plant_cap_ratio", 0.05, 0.05, 0.50),
        ("plant_max_age", 10, 20, 500),
        ("herb_repro_threshold", 5, 10, 80),
        ("carn_repro_threshold", 5, 10, 80),
        ("carn_satiation", 5, 5, 60),
        ("disease_chance", 0.001, 0.0, 0.05),
        ("season_length", 10, 10, 300),
        ("base_delay", 0.05, 0.05, 2.0),
    ]
    if idx < 0 or idx >= len(adjustments):
        return
    name, step, minimum, maximum = adjustments[idx]
    current = getattr(config, name)
    new_val = current + step * direction
    if isinstance(step, float):
        new_val = round(new_val, 4)
    new_val = max(minimum, min(maximum, new_val))
    setattr(config, name, new_val)


# -- Input ----------------------------------------------------------------


def get_key() -> Optional[str]:
    r, _, _ = select.select([sys.stdin], [], [], 0)
    if not r:
        return None
    ch = sys.stdin.read(1)
    if ch == "\033":
        r2, _, _ = select.select([sys.stdin], [], [], 0.05)
        if not r2:
            return "ESC"
        ch2 = sys.stdin.read(1)
        if ch2 == "[":
            r3, _, _ = select.select([sys.stdin], [], [], 0.05)
            if r3:
                ch3 = sys.stdin.read(1)
                arrows = {"A": "UP", "B": "DOWN", "C": "RIGHT", "D": "LEFT",
                          "H": "UP", "F": "DOWN"}
                return arrows.get(ch3, ch3)
            return "ESC"
        return ch2
    return ch


# -- Main -----------------------------------------------------------------


SAVE_FILE = "emoji_zoo_save.json"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Emoji Zoo -- a terminal emoji ecosystem simulation")
    parser.add_argument("--seed", type=int, default=None,
                        help="random seed for reproducible runs")
    parser.add_argument("--width", type=int, default=None,
                        help="grid width (default: auto from terminal)")
    parser.add_argument("--height", type=int, default=None,
                        help="grid height (default: auto from terminal)")
    parser.add_argument("--speed", type=int, default=1,
                        help="initial speed multiplier (default 1)")
    parser.add_argument("--no-picker", action="store_true",
                        help="skip species picker, use all species")
    parser.add_argument("--preset", choices=list(PRESETS.keys()),
                        default="balanced", help="ecosystem preset")
    parser.add_argument("--save-file", default=SAVE_FILE,
                        help="save/load file path")
    parser.add_argument("--load", action="store_true",
                        help="load saved ecosystem on startup")
    parser.add_argument("--debug", action="store_true",
                        help="enable debug logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    if args.seed is not None:
        random.seed(args.seed)
        _fake.seed_instance(args.seed)
        logger.info("Seeded with %d", args.seed)

    config = make_config(args.preset)

    if not sys.stdin.isatty():
        print("Run this in a terminal, not a pipe.")
        sys.exit(1)

    if args.load:
        state = load_state(args.save_file)
        if state is None:
            print(f"Could not load from {args.save_file}")
            sys.exit(1)
    else:
        if args.no_picker:
            selected_herbs = [e for e, _, _ in ALL_HERBIVORES]
            selected_carns = [e for e, _, _ in ALL_CARNIVORES]
        else:
            selected_herbs, selected_carns = species_picker()

        ts = shutil.get_terminal_size()
        gw = args.width or min(120, max(20, (ts.columns - 2) // 2))
        gh = args.height or min(50, max(10, ts.lines - 24))

        if gw < 20 or gh < 10:
            print("Terminal too small. Need at least ~42 columns and ~28 lines.")
            sys.exit(1)

        grid = Grid(gw, gh)
        populate(grid, config, selected_herbs, selected_carns)
        state = GameState(
            grid=grid, config=config,
            selected_herbs=selected_herbs, selected_carns=selected_carns,
        )

    speed = max(1, args.speed)
    paused = False
    god_mode = False
    cursor = [state.grid.w // 2, state.grid.h // 2]
    show_help = False
    show_params = False
    param_sel = 0
    terminal_resized = False

    def on_resize(signum, frame):
        nonlocal terminal_resized
        terminal_resized = True

    signal.signal(signal.SIGWINCH, on_resize)

    old = termios.tcgetattr(sys.stdin)
    tty.setcbreak(sys.stdin.fileno())
    sys.stdout.write("\033[?25l\033[2J")

    try:
        while True:
            key = get_key()

            if show_params:
                if key in ("q", "\x03", "\r", "\n", "ESC"):
                    show_params = False
                elif key == "UP":
                    param_sel = max(0, param_sel - 1)
                elif key == "DOWN":
                    param_sel = min(len(_param_list(state.config)) - 1, param_sel + 1)
                elif key in ("+", "="):
                    _adjust_param(state.config, param_sel, 1)
                elif key == "-":
                    _adjust_param(state.config, param_sel, -1)
                elif key == " ":
                    paused = not paused
            elif show_help:
                if key in ("h", "?", "ESC", "q", "\x03"):
                    show_help = False
            elif god_mode:
                if key in ("q", "\x03"):
                    break
                elif key in ("ESC", "g"):
                    god_mode = False
                elif key == "UP":
                    cursor[1] = max(0, cursor[1] - 1)
                elif key == "DOWN":
                    cursor[1] = min(state.grid.h - 1, cursor[1] + 1)
                elif key == "LEFT":
                    cursor[0] = max(0, cursor[0] - 1)
                elif key == "RIGHT":
                    cursor[0] = min(state.grid.w - 1, cursor[0] + 1)
                elif key == "1":
                    cx, cy = cursor
                    if state.grid.cells[cy][cx] is None:
                        state.grid.cells[cy][cx] = make_plant()
                elif key == "2" and state.selected_herbs:
                    cx, cy = cursor
                    if state.grid.cells[cy][cx] is None:
                        e = make_herb(state.selected_herbs)
                        if e:
                            state.grid.cells[cy][cx] = e
                elif key == "3" and state.selected_carns:
                    cx, cy = cursor
                    if state.grid.cells[cy][cx] is None:
                        e = make_carn(state.selected_carns)
                        if e:
                            state.grid.cells[cy][cx] = e
                elif key == "x":
                    cx, cy = cursor
                    cell = state.grid.cells[cy][cx]
                    if cell and cell.kind != Kind.WATER:
                        state.grid.cells[cy][cx] = None
                elif key == " ":
                    paused = not paused
                elif key in ("+", "="):
                    speed = min(10, speed + 1)
                elif key == "-":
                    speed = max(1, speed - 1)
                elif key == "r":
                    gw, gh = state.grid.w, state.grid.h
                    state.grid = Grid(gw, gh)
                    populate(state.grid, state.config,
                             state.selected_herbs, state.selected_carns)
                    state.tick = 0
                    state.season = 0
                    state.hist = {"plant": [], "herb": [], "carn": []}
                    state.ticker = []
                    state.flashes = {}
                    state.stats = Stats()
                elif key == "s":
                    if paused:
                        events: list[dict] = []
                        try:
                            step(state, events)
                        except Exception as e:
                            logger.error("Step error: %s", e)
                            state.ticker.append(f"ERROR: {e}")
                        _process_events(state, events)
                elif key in ("h", "?"):
                    show_help = True
                elif key == "p":
                    show_params = True
                elif key == "S":
                    if save_state(state, args.save_file):
                        state.notification = f"Saved to {args.save_file}"
                        state.notification_ticks = 5
                    else:
                        state.notification = "Save failed!"
                        state.notification_ticks = 5
                elif key == "L":
                    loaded = load_state(args.save_file)
                    if loaded:
                        state = loaded
                        cursor = [state.grid.w // 2, state.grid.h // 2]
                        state.notification = f"Loaded from {args.save_file}"
                        state.notification_ticks = 5
                    else:
                        state.notification = f"Load failed! ({args.save_file})"
                        state.notification_ticks = 5
                elif key == "[":
                    state.ticker_offset = max(
                        -len(state.ticker),
                        state.ticker_offset - 1)
                elif key == "]":
                    state.ticker_offset = min(0, state.ticker_offset + 1)
            else:
                if key in ("q", "\x03"):
                    break
                elif key == " ":
                    paused = not paused
                elif key in ("+", "="):
                    speed = min(10, speed + 1)
                elif key == "-":
                    speed = max(1, speed - 1)
                elif key == "r":
                    gw, gh = state.grid.w, state.grid.h
                    state.grid = Grid(gw, gh)
                    populate(state.grid, state.config,
                             state.selected_herbs, state.selected_carns)
                    state.tick = 0
                    state.season = 0
                    state.hist = {"plant": [], "herb": [], "carn": []}
                    state.ticker = []
                    state.flashes = {}
                    state.stats = Stats()
                elif key == "1":
                    drop_creatures(state.grid, make_plant, state.config.drop_plant_n)
                elif key == "2" and state.selected_herbs:
                    drop_creatures(
                        state.grid,
                        lambda: make_herb(state.selected_herbs),
                        state.config.drop_herb_n)
                elif key == "3" and state.selected_carns:
                    drop_creatures(
                        state.grid,
                        lambda: make_carn(state.selected_carns),
                        state.config.drop_carn_n)
                elif key == "g":
                    god_mode = True
                    cursor = [state.grid.w // 2, state.grid.h // 2]
                elif key == "s":
                    if paused:
                        events = []
                        try:
                            step(state, events)
                        except Exception as e:
                            logger.error("Step error: %s", e)
                            state.ticker.append(f"ERROR: {e}")
                        _process_events(state, events)
                elif key in ("h", "?"):
                    show_help = True
                elif key == "p":
                    show_params = True
                elif key == "S":
                    if save_state(state, args.save_file):
                        state.notification = f"Saved to {args.save_file}"
                        state.notification_ticks = 5
                    else:
                        state.notification = "Save failed!"
                        state.notification_ticks = 5
                elif key == "L":
                    loaded = load_state(args.save_file)
                    if loaded:
                        state = loaded
                        cursor = [state.grid.w // 2, state.grid.h // 2]
                        state.notification = f"Loaded from {args.save_file}"
                        state.notification_ticks = 5
                    else:
                        state.notification = f"Load failed! ({args.save_file})"
                        state.notification_ticks = 5
                elif key == "[":
                    state.ticker_offset = max(
                        -len(state.ticker),
                        state.ticker_offset - 1)
                elif key == "]":
                    state.ticker_offset = min(0, state.ticker_offset + 1)

            if not paused and not show_help and not show_params:
                events = []
                try:
                    step(state, events)
                except Exception as e:
                    logger.error("Step error: %s", e)
                    state.ticker.append(f"ERROR: {e}")
                _process_events(state, events)

            if terminal_resized:
                terminal_resized = False
                sys.stdout.write("\033[2J\033[H")

            render(state, paused, speed, god_mode, tuple(cursor),
                   show_help, show_params, param_sel, terminal_resized)
            time.sleep(state.config.base_delay / speed)
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old)
        sys.stdout.write("\033[0m\033[?25h\033[2J\033[H")
        sys.stdout.flush()
        print("Emoji Zoo closed. Thanks for visiting!")


def _process_events(state: GameState, events: list[dict]) -> None:
    state.flashes = {}
    for ev in events:
        state.flashes[(ev["x"], ev["y"])] = ev["kind"]
        msg = event_to_message(ev)
        if msg:
            state.ticker.append(msg)
    if len(state.ticker) > 100:
        state.ticker = state.ticker[-100:]
    state.ticker_offset = 0


if __name__ == "__main__":
    main()
