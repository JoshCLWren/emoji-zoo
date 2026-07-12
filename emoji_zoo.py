#!/usr/bin/env python3
"""emoji_zoo -- Conway's Game of Life meets a living, breathing emoji ecosystem.

Plants grow and spread. Herbivores graze and flee predators.
Carnivores hunt. Energy drives reproduction and death.
Population cycles emerge from simple rules.

Each species has unique traits: speed, vision, lifespan, reproduction
thresholds. Seasons affect plant growth and energy burn. Disease can
sweep through dense populations. Dead animals decompose into nutrients
that feed plants. Animals get thirsty and must drink from water.

Create your own species with custom traits and emojis! Press 'c' in the
species picker to start the creator.

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
import datetime
import json
import logging
import os
import random
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from enum import Enum

from faker import Faker
from rich.table import Table
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Static,
)

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
        speed=1,
        vision=4,
        flee_vision=3,
        start_energy=10,
        max_energy=25,
        eat_energy=8,
        repro_threshold=20,
        repro_cost=8,
        max_age=80,
        pack_bonus=0.15,
        color="\033[92m",
    ),
    "sheep": SpeciesTraits(
        speed=1,
        vision=5,
        flee_vision=2,
        start_energy=16,
        max_energy=40,
        eat_energy=11,
        repro_threshold=32,
        repro_cost=15,
        max_age=150,
        pack_bonus=0.08,
        color="\033[97m",
    ),
    "deer": SpeciesTraits(
        speed=1,
        vision=7,
        flee_vision=4,
        start_energy=18,
        max_energy=40,
        eat_energy=11,
        repro_threshold=32,
        repro_cost=15,
        max_age=160,
        pack_bonus=0.05,
        color="\033[33m",
    ),
    "cow": SpeciesTraits(
        speed=2,
        vision=4,
        flee_vision=2,
        start_energy=24,
        max_energy=50,
        eat_energy=14,
        repro_threshold=38,
        repro_cost=18,
        max_age=200,
        pack_bonus=0.0,
        color="\033[37m",
    ),
    "goat": SpeciesTraits(
        speed=1,
        vision=5,
        flee_vision=3,
        start_energy=16,
        max_energy=38,
        eat_energy=11,
        repro_threshold=30,
        repro_cost=14,
        max_age=170,
        pack_bonus=0.05,
        color="\033[93m",
    ),
    "bunny": SpeciesTraits(
        speed=1,
        vision=3,
        flee_vision=4,
        start_energy=8,
        max_energy=20,
        eat_energy=6,
        repro_threshold=16,
        repro_cost=6,
        max_age=60,
        pack_bonus=0.2,
        color="\033[32m",
    ),
    "pig": SpeciesTraits(
        speed=1,
        vision=5,
        flee_vision=2,
        start_energy=18,
        max_energy=42,
        eat_energy=12,
        repro_threshold=30,
        repro_cost=14,
        max_age=160,
        pack_bonus=0.05,
        color="\033[95m",
    ),
    "horse": SpeciesTraits(
        speed=1,
        vision=6,
        flee_vision=3,
        start_energy=22,
        max_energy=45,
        eat_energy=13,
        repro_threshold=34,
        repro_cost=16,
        max_age=190,
        pack_bonus=0.0,
        color="\033[90m",
    ),
}

CARNIVORE_TRAITS: dict[str, SpeciesTraits] = {
    "lion": SpeciesTraits(
        speed=1,
        vision=6,
        start_energy=26,
        max_energy=50,
        eat_energy=12,
        repro_threshold=36,
        repro_cost=18,
        max_age=200,
        pack_bonus=0.12,
        can_hunt_carns=False,
        color="\033[93m",
    ),
    "wolf": SpeciesTraits(
        speed=1,
        vision=7,
        start_energy=22,
        max_energy=42,
        eat_energy=11,
        repro_threshold=32,
        repro_cost=16,
        max_age=180,
        pack_bonus=0.15,
        can_hunt_carns=False,
        color="\033[90m",
    ),
    "fox": SpeciesTraits(
        speed=1,
        vision=6,
        start_energy=16,
        max_energy=30,
        eat_energy=9,
        repro_threshold=24,
        repro_cost=10,
        max_age=120,
        pack_bonus=0.0,
        can_hunt_carns=False,
        color="\033[91m",
    ),
    "bear": SpeciesTraits(
        speed=2,
        vision=5,
        start_energy=30,
        max_energy=55,
        eat_energy=14,
        repro_threshold=40,
        repro_cost=20,
        max_age=250,
        pack_bonus=0.0,
        can_hunt_carns=True,
        color="\033[33m",
    ),
    "tiger": SpeciesTraits(
        speed=1,
        vision=6,
        start_energy=28,
        max_energy=50,
        eat_energy=13,
        repro_threshold=38,
        repro_cost=18,
        max_age=220,
        pack_bonus=0.0,
        can_hunt_carns=True,
        color="\033[38;5;166m",
    ),
    "eagle": SpeciesTraits(
        speed=1,
        vision=9,
        start_energy=18,
        max_energy=35,
        eat_energy=10,
        repro_threshold=28,
        repro_cost=14,
        max_age=160,
        pack_bonus=0.0,
        can_hunt_carns=True,
        color="\033[97m",
    ),
    "snake": SpeciesTraits(
        speed=2,
        vision=4,
        start_energy=14,
        max_energy=28,
        eat_energy=8,
        repro_threshold=22,
        repro_cost=10,
        max_age=140,
        pack_bonus=0.0,
        can_hunt_carns=True,
        color="\033[32m",
    ),
    "crocodile": SpeciesTraits(
        speed=2,
        vision=4,
        start_energy=28,
        max_energy=50,
        eat_energy=13,
        repro_threshold=36,
        repro_cost=18,
        max_age=240,
        pack_bonus=0.0,
        can_hunt_carns=True,
        color="\033[38;5;22m",
    ),
}

TRAITS_BY_KIND: dict[str, dict[str, SpeciesTraits]] = {
    "herbivore": HERBIVORE_TRAITS,
    "carnivore": CARNIVORE_TRAITS,
}


def get_traits(kind_name: str, species: str) -> SpeciesTraits:
    built = TRAITS_BY_KIND.get(kind_name, {}).get(species)
    if built:
        return built
    custom = CUSTOM_TRAITS_BY_KIND.get(kind_name, {}).get(species)
    if custom:
        return custom
    return SpeciesTraits()


# -- Custom species -------------------------------------------------------


CUSTOM_SPECIES_DIR = os.path.join(os.path.expanduser("~"), ".emoji_zoo")
CUSTOM_SPECIES_FILE = os.path.join(CUSTOM_SPECIES_DIR, "custom_species.json")

CUSTOM_TRAITS_BY_KIND: dict[str, dict[str, SpeciesTraits]] = {
    "herbivore": {},
    "carnivore": {},
}
CUSTOM_HERBIVORES: list[tuple[str, str, str]] = []
CUSTOM_CARNIVORES: list[tuple[str, str, str]] = []
_CUSTOM_SPECIES_DATA: dict[str, dict] = {}

CUSTOM_EMOJI_GRID: list[list[tuple[str, str]]] = [
    [
        ("Mammals", ""),
        ("🐀", "rat"),
        ("🐁", "mouse"),
        ("🐇", "rabbit"),
        ("🐈", "cat"),
        ("🐕", "dog"),
        ("🦊", "fox"),
        ("🐻", "bear"),
        ("🐼", "panda"),
        ("🐨", "koala"),
        ("🐯", "tiger"),
        ("🦁", "lion"),
        ("🐮", "cow"),
        ("🐷", "pig"),
        ("🐸", "frog"),
    ],
    [
        ("", ""),
        ("🐴", "horse"),
        ("🐑", "sheep"),
        ("🐐", "goat"),
        ("🐪", "camel"),
        ("🐘", "elephant"),
        ("🦏", "rhino"),
        ("🐃", "buffalo"),
        ("🐂", "ox"),
        ("🐈\ufe0f", "lion2"),
        ("🐕\ufe0f", "dog2"),
        ("🐿", "squirrel"),
        ("🦔", "hedgehog"),
        ("🦇", "bat"),
        ("🦦", "otter"),
    ],
    [
        ("Birds", ""),
        ("🦅", "eagle"),
        ("🦆", "duck"),
        ("🦉", "owl"),
        ("🐧", "penguin"),
        ("🐦", "bird"),
        ("🐤", "chick"),
        ("🕊", "dove"),
        ("🦜", "parrot"),
        ("🦚", "peacock"),
        ("🦩", "flamingo"),
        ("🐔", "chicken"),
        ("🇹", "turkey"),
        ("🐓", "rooster"),
        ("🐦\ufe0f", "bird2"),
    ],
    [
        ("", ""),
        ("🦢", "swan"),
        ("🦇\ufe0f", "bat2"),
        ("🐗", "boar"),
        ("🐺", "wolf"),
        ("🦤", "dodo"),
        ("🦎", "lizard"),
        ("🐊", "crocodile"),
        ("🐍", "snake"),
        ("🐢", "turtle"),
        ("🦎\ufe0f", "gecko"),
        ("🐙", "octopus"),
        ("🦑", "squid"),
        ("🦐", "shrimp"),
        ("🦞", "lobster"),
    ],
    [
        ("Reptiles", ""),
        ("🐛", "bug"),
        ("🦋", "butterfly"),
        ("🐌", "snail"),
        ("🐝", "bee"),
        ("🐜", "ant"),
        ("🪲", "beetle"),
        ("🪳", "cockroach"),
        ("🦂", "scorpion"),
        ("🕷", "spider"),
        ("🪰", "fly"),
        ("🦗", "cricket"),
        ("🦟", "mosquito"),
        ("🪱", "worm"),
        ("🐛\ufe0f", "bug2"),
    ],
    [
        ("", ""),
        ("🐠", "tropical_fish"),
        ("🐟", "fish"),
        ("🐡", "blowfish"),
        ("🦈", "shark"),
        ("🐬", "dolphin"),
        ("鲸", "whale"),
        ("🦭", "seal"),
        ("🦀", "crab"),
        ("🦛", "hippo"),
        ("🦥", "sloth"),
        ("🐆", "leopard"),
        ("🦓", "zebra"),
        ("🦍", "gorilla"),
        ("🦧", "orangutan"),
    ],
]


def load_custom_species() -> None:
    if not os.path.isfile(CUSTOM_SPECIES_FILE):
        return
    try:
        with open(CUSTOM_SPECIES_FILE) as f:
            _CUSTOM_SPECIES_DATA.clear()
            _CUSTOM_SPECIES_DATA.update(json.load(f))
    except Exception as e:
        logger.warning("Failed to load custom species: %s", e)
        return

    CUSTOM_TRAITS_BY_KIND["herbivore"].clear()
    CUSTOM_TRAITS_BY_KIND["carnivore"].clear()
    CUSTOM_HERBIVORES.clear()
    CUSTOM_CARNIVORES.clear()

    for name, data in _CUSTOM_SPECIES_DATA.items():
        emoji = data["emoji"]
        kind = data["kind"]
        t = SpeciesTraits(**data["traits"])
        CUSTOM_TRAITS_BY_KIND[kind][name] = t
        entry = (emoji, "", name)
        if kind == "herbivore":
            CUSTOM_HERBIVORES.append(entry)
        else:
            CUSTOM_CARNIVORES.append(entry)

    update_emoji_maps()


def save_custom_species() -> bool:
    try:
        os.makedirs(CUSTOM_SPECIES_DIR, exist_ok=True)
        with open(CUSTOM_SPECIES_FILE, "w") as f:
            json.dump(_CUSTOM_SPECIES_DATA, f, indent=2)
        return True
    except Exception as e:
        logger.error("Failed to save custom species: %s", e)
        return False


def add_custom_species(name: str, emoji: str, kind: str, traits: SpeciesTraits) -> bool:
    if not name or not emoji or kind not in ("herbivore", "carnivore"):
        return False
    traits_dict = {
        "speed": traits.speed,
        "vision": traits.vision,
        "flee_vision": traits.flee_vision,
        "start_energy": traits.start_energy,
        "max_energy": traits.max_energy,
        "eat_energy": traits.eat_energy,
        "repro_threshold": traits.repro_threshold,
        "repro_cost": traits.repro_cost,
        "max_age": traits.max_age,
        "max_neighbors": traits.max_neighbors,
        "pack_bonus": traits.pack_bonus,
        "can_hunt_carns": traits.can_hunt_carns,
        "color": traits.color,
    }
    _CUSTOM_SPECIES_DATA[name] = {
        "emoji": emoji,
        "kind": kind,
        "traits": traits_dict,
    }
    CUSTOM_TRAITS_BY_KIND[kind][name] = traits
    entry = (emoji, "", name)
    if kind == "herbivore":
        CUSTOM_HERBIVORES.append(entry)
    else:
        CUSTOM_CARNIVORES.append(entry)

    update_emoji_maps()
    return save_custom_species()


def remove_custom_species(name: str) -> bool:
    data = _CUSTOM_SPECIES_DATA.pop(name, None)
    if data is None:
        return False
    kind = data["kind"]
    CUSTOM_TRAITS_BY_KIND[kind].pop(name, None)
    if kind == "herbivore":
        CUSTOM_HERBIVORES[:] = [e for e in CUSTOM_HERBIVORES if e[2] != name]
    else:
        CUSTOM_CARNIVORES[:] = [e for e in CUSTOM_CARNIVORES if e[2] != name]
    return save_custom_species()


def clear_custom_species() -> None:
    _CUSTOM_SPECIES_DATA.clear()
    CUSTOM_TRAITS_BY_KIND["herbivore"].clear()
    CUSTOM_TRAITS_BY_KIND["carnivore"].clear()
    CUSTOM_HERBIVORES.clear()
    CUSTOM_CARNIVORES.clear()
    try:
        if os.path.isfile(CUSTOM_SPECIES_FILE):
            os.remove(CUSTOM_SPECIES_FILE)
    except OSError:
        pass


def roll_traits(kind: str) -> SpeciesTraits:
    if kind == "herbivore":
        return SpeciesTraits(
            speed=random.choice([1, 1, 1, 2]),
            vision=random.randint(3, 8),
            flee_vision=random.randint(2, 6),
            start_energy=random.randint(8, 24),
            max_energy=random.randint(20, 50),
            eat_energy=random.randint(6, 14),
            repro_threshold=random.randint(16, 40),
            repro_cost=random.randint(6, 18),
            max_age=random.randint(60, 250),
            max_neighbors=random.choice([1, 2, 2, 3]),
            pack_bonus=round(random.uniform(0.0, 0.2), 2),
            can_hunt_carns=False,
            color=random.choice(
                [
                    "\033[92m",
                    "\033[97m",
                    "\033[33m",
                    "\033[37m",
                    "\033[93m",
                    "\033[32m",
                    "\033[95m",
                    "\033[90m",
                ]
            ),
        )
    return SpeciesTraits(
        speed=random.choice([1, 1, 2]),
        vision=random.randint(4, 9),
        start_energy=random.randint(14, 30),
        max_energy=random.randint(28, 55),
        eat_energy=random.randint(8, 14),
        repro_threshold=random.randint(22, 40),
        repro_cost=random.randint(10, 20),
        max_age=random.randint(120, 250),
        max_neighbors=random.choice([1, 2, 2]),
        pack_bonus=round(random.uniform(0.0, 0.15), 2),
        can_hunt_carns=random.choice([False, False, True]),
        color=random.choice(
            [
                "\033[93m",
                "\033[90m",
                "\033[91m",
                "\033[33m",
                "\033[38;5;166m",
                "\033[97m",
                "\033[32m",
                "\033[38;5;22m",
            ]
        ),
    )


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


def make_config(preset: str | None = None, **overrides) -> Config:
    cfg = Config()
    if preset and preset in PRESETS:
        for k, v in PRESETS[preset].items():
            setattr(cfg, k, v)
    for k, v in overrides.items():
        if hasattr(cfg, k):
            setattr(cfg, k, v)
    return cfg


# -- Emoji palettes -------------------------------------------------------

PLANT_STAGES = ["\U0001f331", "\U0001f33f", "\U0001f340", "\U0001f33e"]

ALL_HERBIVORES = [
    ("\U0001f430", "", "rabbit"),
    ("\U0001f411", "", "sheep"),
    ("\U0001f98c", "", "deer"),
    ("\U0001f404", "", "cow"),
    ("\U0001f410", "", "goat"),
    ("\U0001f407", "", "bunny"),
    ("\U0001f416", "", "pig"),
    ("\U0001f40e", "", "horse"),
]
ALL_CARNIVORES = [
    ("\U0001f981", "", "lion"),
    ("\U0001f43a", "", "wolf"),
    ("\U0001f98a", "", "fox"),
    ("\U0001f43b", "", "bear"),
    ("\U0001f42f", "", "tiger"),
    ("\U0001f985", "", "eagle"),
    ("\U0001f40d", "", "snake"),
    ("\U0001f40a", "", "crocodile"),
]

WATER_EMOJI = "\U0001f30a"
DISEASE_EMOJI = "\U0001f9a0"
EMPTY_STR = "  "
SPARK_CHARS = "\u2581\u2582\u2583\u2584\u2585\u2586\u2587\u2588"

EMOJI_TO_SPECIES: dict[str, str] = {}
for _e, _k, _s in ALL_HERBIVORES + ALL_CARNIVORES:
    EMOJI_TO_SPECIES[_e] = _s

_fake = Faker()

SEASON_NAMES = ["Spring", "Summer", "Autumn", "Winter"]
SEASON_PLANT_MOD = [1.5, 1.0, 0.6, 0.2]
SEASON_ENERGY_MOD = [0.8, 1.2, 1.0, 1.5]
SEASON_DIEOFF_CHANCE = [0.0, 0.0, 0.02, 0.08]


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
    name: str | None = None
    species: str = ""
    traits: SpeciesTraits | None = None
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
        self.cells: list[list[Entity | None]] = [[None] * w for _ in range(h)]
        self.nutrients: list[list[float]] = [[0.0] * w for _ in range(h)]
        self._dirty: set[tuple[int, int]] = set()

    def get(self, x: int, y: int) -> Entity | None:
        if 0 <= x < self.w and 0 <= y < self.h:
            return self.cells[y][x]
        return None

    def set_cell(self, x: int, y: int, entity: Entity | None) -> None:
        self.cells[y][x] = entity
        self._dirty.add((x, y))

    def mark_dirty(self, x: int, y: int) -> None:
        if 0 <= x < self.w and 0 <= y < self.h:
            self._dirty.add((x, y))

    def clear_dirty(self) -> None:
        self._dirty.clear()

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
        return [(nx, ny) for nx, ny in self.neighbors(x, y) if self.cells[ny][nx] is None]

    def passable_neighbors(self, x: int, y: int) -> list[tuple[int, int]]:
        out: list[tuple[int, int]] = []
        for nx, ny in self.neighbors(x, y):
            c = self.cells[ny][nx]
            if c is None or c.kind == Kind.PLANT:
                out.append((nx, ny))
        return out

    def random_empty(self, tries: int = 200) -> tuple[int, int] | None:
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


def find_nearest(grid: Grid, x: int, y: int, kind: Kind, vision: int) -> tuple[int, int] | None:
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


def find_nearest_species(grid: Grid, x: int, y: int, kind: Kind, species: str, vision: int) -> tuple[int, int] | None:
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


def try_move(grid: Grid, x: int, y: int, e: Entity, nx: int, ny: int) -> bool:
    if 0 <= nx < grid.w and 0 <= ny < grid.h and grid.cells[ny][nx] is None:
        grid.set_cell(x, y, None)
        grid.set_cell(nx, ny, e)
        return True
    return False


def try_move_through_plants(grid: Grid, x: int, y: int, e: Entity, nx: int, ny: int) -> bool:
    if 0 <= nx < grid.w and 0 <= ny < grid.h:
        target = grid.cells[ny][nx]
        if target is None or target.kind == Kind.PLANT:
            grid.set_cell(x, y, None)
            grid.set_cell(nx, ny, e)
            return True
    return False


def sparkline(values: list[int], max_val: int) -> str:
    if max_val <= 0:
        return SPARK_CHARS[0] * len(values)
    return "".join(SPARK_CHARS[min(7, max(0, int(v / max_val * 7.999)))] for v in values)


def random_name() -> str:
    return _fake.first_name()


def make_plant() -> Entity:
    g = random.randint(0, 3)
    return Entity(Kind.PLANT, PLANT_STAGES[g], 0, growth=g, species="plant")


def make_herb(selected: list[str]) -> Entity | None:
    if not selected:
        return None
    emoji = random.choice(selected)
    species = EMOJI_TO_SPECIES.get(emoji, "herbivore")
    traits = HERBIVORE_TRAITS.get(species) or CUSTOM_TRAITS_BY_KIND["herbivore"].get(species) or SpeciesTraits()
    return Entity(
        Kind.HERBIVORE,
        emoji,
        traits.start_energy,
        name=random_name(),
        species=species,
        traits=traits,
    )


def make_herb_of_species(species: str) -> Entity | None:
    traits = HERBIVORE_TRAITS.get(species) or CUSTOM_TRAITS_BY_KIND["herbivore"].get(species)
    if traits is None:
        return None
    emoji = _SPECIES_TO_EMOJI.get(species)
    if emoji is None:
        return None
    return Entity(
        Kind.HERBIVORE,
        emoji,
        traits.start_energy,
        name=random_name(),
        species=species,
        traits=traits,
    )


def make_carn(selected: list[str]) -> Entity | None:
    if not selected:
        return None
    emoji = random.choice(selected)
    species = EMOJI_TO_SPECIES.get(emoji, "carnivore")
    traits = CARNIVORE_TRAITS.get(species) or CUSTOM_TRAITS_BY_KIND["carnivore"].get(species) or SpeciesTraits()
    return Entity(
        Kind.CARNIVORE,
        emoji,
        traits.start_energy,
        name=random_name(),
        species=species,
        traits=traits,
    )


def make_carn_of_species(species: str) -> Entity | None:
    traits = CARNIVORE_TRAITS.get(species) or CUSTOM_TRAITS_BY_KIND["carnivore"].get(species)
    if traits is None:
        return None
    emoji = _SPECIES_TO_EMOJI.get(species)
    if emoji is None:
        return None
    return Entity(
        Kind.CARNIVORE,
        emoji,
        traits.start_energy,
        name=random_name(),
        species=species,
        traits=traits,
    )


def drop_creatures(grid: Grid, factory, n: int) -> None:
    for _ in range(n):
        spot = grid.random_empty()
        if spot:
            x, y = spot
            entity = factory()
            if entity:
                grid.set_cell(x, y, entity)


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
        return self.total_starvations + self.total_deaths_age + self.total_deaths_disease + self.total_kills

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
    hist: dict[str, list[int]] = field(default_factory=lambda: {"plant": [], "herb": [], "carn": []})
    ticker: list[str] = field(default_factory=list)
    flashes: dict[tuple[int, int], str] = field(default_factory=dict)
    ticker_offset: int = 0
    notification: str = ""
    notification_ticks: int = 0
    pop_counts: dict[Kind, int] = field(
        default_factory=lambda: {Kind.PLANT: 0, Kind.HERBIVORE: 0, Kind.CARNIVORE: 0, Kind.WATER: 0}
    )

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
    plant_n = sum(1 for row in grid.cells for c in row if c and c.kind == Kind.PLANT)
    plant_cap = grid.w * grid.h * config.plant_cap_ratio
    plant_deaths = [0]

    for x, y, e in entities:
        if grid.cells[y][x] is not e:
            continue
        e.age += 1
        if e.kind == Kind.PLANT:
            _tick_plant(state, x, y, e, births, plant_n, plant_cap, plant_mod, dieoff_chance, plant_deaths)
        elif e.kind == Kind.HERBIVORE:
            _tick_herb(state, x, y, e, births, events, energy_mod)
        elif e.kind == Kind.CARNIVORE:
            _tick_carn(state, x, y, e, births, events, energy_mod)

    for bx, by, be in births:
        if grid.cells[by][bx] is None:
            grid.set_cell(bx, by, be)

    plant_n = plant_n - plant_deaths[0] + len(births)
    if plant_n < plant_cap:
        for _ in range(config.plant_seed_count):
            spot = grid.random_empty(50)
            if spot:
                x, y = spot
                grid.set_cell(x, y, make_plant())
                plant_n += 1

    grid.decay_nutrients(config.nutrient_decay)

    state.tick += 1
    c = count_pop(grid)
    state.pop_counts = c
    state.hist["plant"].append(c[Kind.PLANT])
    state.hist["herb"].append(c[Kind.HERBIVORE])
    state.hist["carn"].append(c[Kind.CARNIVORE])
    for k in state.hist:
        if len(state.hist[k]) > 200:
            state.hist[k] = state.hist[k][-200:]
    state.stats.update_peaks(c[Kind.PLANT], c[Kind.HERBIVORE], c[Kind.CARNIVORE])


def _tick_plant(
    state: GameState,
    x: int,
    y: int,
    e: Entity,
    births: list,
    plant_n: int,
    plant_cap: float,
    plant_mod: float,
    dieoff_chance: float,
    plant_deaths: list[int],
) -> None:
    grid = state.grid
    config = state.config

    if e.age > config.plant_max_age:
        grid.set_cell(x, y, None)
        grid.add_nutrients(x, y, 2.0)
        plant_deaths[0] += 1
        return

    if dieoff_chance > 0 and random.random() < dieoff_chance:
        grid.set_cell(x, y, None)
        grid.add_nutrients(x, y, 1.0)
        plant_deaths[0] += 1
        return

    if e.growth < config.plant_max_growth:
        nutrient_bonus = grid.nutrients[y][x] * config.nutrient_growth_bonus
        if random.random() < (0.3 + nutrient_bonus) * plant_mod:
            e.growth += 1
            e.emoji = PLANT_STAGES[e.growth]
            grid.mark_dirty(x, y)

    spread_chance = config.plant_spread_chance * plant_mod
    if plant_n < plant_cap and random.random() < spread_chance:
        empties = grid.empty_neighbors(x, y)
        if empties:
            nx, ny = random.choice(empties)
            births.append((nx, ny, make_plant()))


def _tick_herb(state: GameState, x: int, y: int, e: Entity, births: list, events: list, energy_mod: float) -> None:
    grid = state.grid
    config = state.config
    traits = e.traits or SpeciesTraits()

    if e.is_diseased:
        e.energy -= int(config.disease_energy_drain * energy_mod)
        e.diseased -= 1
        if e.diseased <= 0 and random.random() < config.disease_death_chance:
            grid.set_cell(x, y, None)
            grid.add_nutrients(x, y, config.nutrient_spawn_amount)
            state.stats.record_death(e.age, "disease")
            events.append(make_event("disease_death", x, y, emoji=e.emoji, name=e.name, species=e.species))
            return
    else:
        if random.random() < config.disease_chance:
            e.diseased = config.disease_duration

    if traits.speed > 1 and e.age % traits.speed != 0:
        pass
    else:
        e.energy -= max(1, int(energy_mod))

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
            if c and c.kind == Kind.HERBIVORE and not c.is_diseased and random.random() < config.disease_spread_chance:
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
            e.energy = min(e.energy + traits.eat_energy + plant.growth * 3, traits.max_energy)
            grid.set_cell(ax, ay, None)
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
            1
            for nx, ny in grid.neighbors(x, y)
            if grid.cells[ny][nx]
            and grid.cells[ny][nx].kind == Kind.HERBIVORE
            and grid.cells[ny][nx].species == e.species
        )
        total_herbs = sum(
            1 for nx, ny in grid.neighbors(x, y) if grid.cells[ny][nx] and grid.cells[ny][nx].kind == Kind.HERBIVORE
        )
        if total_herbs < traits.max_neighbors:
            effective_threshold = traits.repro_threshold * (1.0 - traits.pack_bonus * min(same_species, 3))
            if e.energy >= effective_threshold:
                empties = grid.empty_neighbors(x, y)
                if empties:
                    nx, ny = random.choice(empties)
                    e.energy -= traits.repro_cost
                    baby = make_herb_of_species(e.species)
                    if baby:
                        births.append((nx, ny, baby))
                        state.stats.total_births += 1
                        events.append(
                            make_event(
                                "birth",
                                nx,
                                ny,
                                emoji=baby.emoji,
                                name=baby.name,
                                species=baby.species,
                                parent_name=e.name,
                                parent_emoji=e.emoji,
                            )
                        )

    if e.age > traits.max_age:
        grid.set_cell(x, y, None)
        grid.add_nutrients(x, y, config.nutrient_spawn_amount)
        state.stats.record_death(e.age, "age")
        events.append(make_event("age_death", x, y, emoji=e.emoji, name=e.name, species=e.species, age=e.age))
        return

    if e.energy <= 0:
        grid.set_cell(x, y, None)
        grid.add_nutrients(x, y, config.nutrient_spawn_amount * 0.5)
        state.stats.record_death(e.age, "starve")
        events.append(make_event("starve", x, y, emoji=e.emoji, name=e.name, species=e.species))


def _tick_carn(state: GameState, x: int, y: int, e: Entity, births: list, events: list, energy_mod: float) -> None:
    grid = state.grid
    config = state.config
    traits = e.traits or SpeciesTraits()

    if e.is_diseased:
        e.energy -= int(config.disease_energy_drain * energy_mod)
        e.diseased -= 1
        if e.diseased <= 0 and random.random() < config.disease_death_chance:
            grid.set_cell(x, y, None)
            grid.add_nutrients(x, y, config.nutrient_spawn_amount)
            state.stats.record_death(e.age, "disease")
            events.append(make_event("disease_death", x, y, emoji=e.emoji, name=e.name, species=e.species))
            return
    else:
        if random.random() < config.disease_chance:
            e.diseased = config.disease_duration

    if traits.speed > 1 and e.age % traits.speed != 0:
        pass
    else:
        e.energy -= max(1, int(energy_mod))

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
            if c and c.kind == Kind.CARNIVORE and not c.is_diseased and random.random() < config.disease_spread_chance:
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
        grid.set_cell(ax, ay, None)
        grid.add_nutrients(ax, ay, config.nutrient_spawn_amount * 0.5)
        state.stats.record_death(prey.age, "kill")
        events.append(
            make_event(
                "kill",
                ax,
                ay,
                predator_emoji=e.emoji,
                predator_name=e.name,
                predator_species=e.species,
                prey_emoji=prey.emoji,
                prey_name=prey.name,
                prey_species=prey.species,
            )
        )
    elif adjacent_carn_prey:
        ax, ay, target = adjacent_carn_prey
        e.energy = min(e.energy + traits.eat_energy, traits.max_energy)
        grid.set_cell(ax, ay, None)
        grid.add_nutrients(ax, ay, config.nutrient_spawn_amount * 0.5)
        state.stats.record_death(target.age, "kill")
        same_species = target.species == e.species
        ev_kind = "kill" if same_species else "carn_kill"
        events.append(
            make_event(
                ev_kind,
                ax,
                ay,
                predator_emoji=e.emoji,
                predator_name=e.name,
                predator_species=e.species,
                prey_emoji=target.emoji,
                prey_name=target.name,
                prey_species=target.species,
            )
        )
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
                        e.energy = min(e.energy + traits.eat_energy, traits.max_energy)
                        grid.set_cell(ax, ay, None)
                        grid.add_nutrients(ax, ay, config.nutrient_spawn_amount * 0.5)
                        state.stats.record_death(c.age, "kill")
                        events.append(
                            make_event(
                                "kill",
                                ax,
                                ay,
                                predator_emoji=e.emoji,
                                predator_name=e.name,
                                predator_species=e.species,
                                prey_emoji=c.emoji,
                                prey_name=c.name,
                                prey_species=c.species,
                            )
                        )
                        break
        else:
            dire = e.energy < traits.max_energy * 0.2
            hungry_carn = traits.can_hunt_carns or e.energy < traits.max_energy * 0.4
            carn_target = None
            if hungry_carn:
                carn_target = _find_carn_prey(grid, x, y, traits, traits.vision, e, dire)
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
                        is_valid = (
                            dire
                            or (c.species != e.species and c.traits.max_energy < traits.max_energy)
                            or (dire and c.species == e.species)
                        )
                        if is_valid:
                            e.energy = min(e.energy + traits.eat_energy, traits.max_energy)
                            grid.set_cell(ax, ay, None)
                            grid.add_nutrients(ax, ay, config.nutrient_spawn_amount * 0.5)
                            state.stats.record_death(c.age, "kill")
                            events.append(
                                make_event(
                                    "carn_kill",
                                    ax,
                                    ay,
                                    predator_emoji=e.emoji,
                                    predator_name=e.name,
                                    predator_species=e.species,
                                    prey_emoji=c.emoji,
                                    prey_name=c.name,
                                    prey_species=c.species,
                                )
                            )
                            break
            else:
                passables = grid.passable_neighbors(x, y)
                if passables:
                    nx, ny = random.choice(passables)
                    if try_move_through_plants(grid, x, y, e, nx, ny):
                        x, y = nx, ny

    if state.selected_carns and e.energy >= traits.repro_threshold:
        same_species = sum(
            1
            for nx, ny in grid.neighbors(x, y)
            if grid.cells[ny][nx]
            and grid.cells[ny][nx].kind == Kind.CARNIVORE
            and grid.cells[ny][nx].species == e.species
        )
        total_carns = sum(
            1 for nx, ny in grid.neighbors(x, y) if grid.cells[ny][nx] and grid.cells[ny][nx].kind == Kind.CARNIVORE
        )
        if total_carns < traits.max_neighbors:
            effective_threshold = traits.repro_threshold * (1.0 - traits.pack_bonus * min(same_species, 3))
            if e.energy >= effective_threshold:
                empties = grid.empty_neighbors(x, y)
                if empties:
                    nx, ny = random.choice(empties)
                    e.energy -= traits.repro_cost
                    baby = make_carn_of_species(e.species)
                    if baby:
                        births.append((nx, ny, baby))
                        state.stats.total_births += 1
                        events.append(
                            make_event(
                                "birth",
                                nx,
                                ny,
                                emoji=baby.emoji,
                                name=baby.name,
                                species=baby.species,
                                parent_name=e.name,
                                parent_emoji=e.emoji,
                            )
                        )

    if e.age > traits.max_age:
        grid.set_cell(x, y, None)
        grid.add_nutrients(x, y, config.nutrient_spawn_amount)
        state.stats.record_death(e.age, "age")
        events.append(make_event("age_death", x, y, emoji=e.emoji, name=e.name, species=e.species, age=e.age))
        return

    if e.energy <= 0:
        grid.set_cell(x, y, None)
        grid.add_nutrients(x, y, config.nutrient_spawn_amount * 0.5)
        state.stats.record_death(e.age, "starve")
        events.append(make_event("starve", x, y, emoji=e.emoji, name=e.name, species=e.species))


def _find_carn_prey(
    grid: Grid, x: int, y: int, traits: SpeciesTraits, vision: int, predator: Entity, dire: bool
) -> tuple[int, int, Entity] | None:
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
            grid.set_cell(x, y, Entity(Kind.WATER, WATER_EMOJI, 0, species="water"))
            placed += 1
        cluster_size = random.randint(2, 7)
        cx, cy = x, y
        for _ in range(cluster_size):
            dx, dy = random.choice([(-1, 0), (1, 0), (0, -1), (0, 1)])
            cx, cy = cx + dx, cy + dy
            if 0 <= cx < grid.w and 0 <= cy < grid.h and grid.cells[cy][cx] is None:
                grid.set_cell(cx, cy, Entity(Kind.WATER, WATER_EMOJI, 0, species="water"))
                placed += 1
        if placed >= n_water:
            break


def populate(grid: Grid, config: Config, selected_herbs: list[str], selected_carns: list[str]) -> None:
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
                        grid.set_cell(xr, yr, entity)
                    break

    fill(n_plants, make_plant)
    fill(n_herbs, lambda: make_herb(selected_herbs))
    fill(n_carns, lambda: make_carn(selected_carns))


# -- Species picker -------------------------------------------------------


_TRAIT_FIELDS = [
    ("speed", "int", 1, 3),
    ("vision", "int", 2, 10),
    ("flee_vision", "int", 1, 8),
    ("start_energy", "int", 5, 30),
    ("max_energy", "int", 15, 60),
    ("eat_energy", "int", 4, 16),
    ("repro_threshold", "int", 10, 50),
    ("repro_cost", "int", 4, 22),
    ("max_age", "int", 40, 300),
    ("max_neighbors", "int", 1, 4),
    ("pack_bonus", "float", 0.0, 0.3),
    ("can_hunt_carns", "bool", False, True),
]


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
                "cells": [[_entity_to_dict(c) for c in row] for row in state.grid.cells],
                "nutrients": state.grid.nutrients,
            },
        }
        with open(filepath, "w") as f:
            json.dump(data, f)
        return True
    except Exception as e:
        logger.error("Save failed: %s", e)
        return False


def load_state(filepath: str) -> GameState | None:
    try:
        with open(filepath) as f:
            data = json.load(f)

        config = Config(**data["config"])
        grid = Grid(data["grid"]["w"], data["grid"]["h"])
        for y in range(grid.h):
            for x in range(grid.w):
                cd = data["grid"]["cells"][y][x]
                if cd:
                    grid.set_cell(x, y, _dict_to_entity(cd))
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
            grid=grid,
            config=config,
            stats=stats,
            selected_herbs=data["selected_herbs"],
            selected_carns=data["selected_carns"],
            tick=data["tick"],
            season=data["season"],
            hist=data["hist"],
            ticker=data["ticker"],
        )
        return state
    except Exception as e:
        logger.error("Load failed: %s", e)
        return None


def _entity_to_dict(e: Entity | None) -> dict | None:
    if e is None:
        return None
    d = {
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
    if e.traits and e.kind in (Kind.HERBIVORE, Kind.CARNIVORE):
        is_builtin = (e.kind == Kind.HERBIVORE and e.species in HERBIVORE_TRAITS) or (
            e.kind == Kind.CARNIVORE and e.species in CARNIVORE_TRAITS
        )
        if not is_builtin:
            d["traits"] = asdict(e.traits)
    return d


def _dict_to_entity(d: dict) -> Entity:
    kind = Kind[d["kind"]]
    species = d.get("species", "")
    traits = None
    if d.get("traits"):
        traits = SpeciesTraits(**d["traits"])
    elif kind == Kind.HERBIVORE:
        traits = HERBIVORE_TRAITS.get(species) or CUSTOM_TRAITS_BY_KIND["herbivore"].get(species) or SpeciesTraits()
    elif kind == Kind.CARNIVORE:
        traits = CARNIVORE_TRAITS.get(species) or CUSTOM_TRAITS_BY_KIND["carnivore"].get(species) or SpeciesTraits()
    return Entity(
        kind=kind,
        emoji=d["emoji"],
        energy=d["energy"],
        growth=d.get("growth", 0),
        age=d.get("age", 0),
        name=d.get("name"),
        species=species,
        traits=traits,
        thirst=d.get("thirst", 0),
        diseased=d.get("diseased", 0),
    )


# -- Event formatting -----------------------------------------------------


FLASH_EMOJIS = {
    "kill": "\U0001f4a5",
    "birth": "\u2728",
    "starve": "\U0001f480",
    "age_death": "\U0001f534",
    "disease_death": "\U0001f9a0",
    "carn_kill": "\U0001f4a5",
}
FLASH_COLORS = {
    "kill": "\033[41m",
    "birth": "\033[44m",
    "starve": "\033[100m",
    "age_death": "\033[45m",
    "disease_death": "\033[48;5;52m",
    "carn_kill": "\033[41m",
}


def event_to_message(ev: dict) -> str:
    kind = ev["kind"]
    if kind == "kill":
        return (
            f"{ev['predator_emoji']} {ev['predator_name']} the {ev['predator_species']}"
            f" caught {ev['prey_emoji']} {ev['prey_name']} the {ev['prey_species']}!"
        )
    if kind == "carn_kill":
        return (
            f"{ev['predator_emoji']} {ev['predator_name']} the {ev['predator_species']}"
            f" hunted down {ev['prey_emoji']} {ev['prey_name']} the {ev['prey_species']}!"
        )
    if kind == "birth":
        return (
            f"\u2728 {ev['parent_emoji']} {ev['parent_name']} had a baby: "
            f"{ev['emoji']} {ev['name']} the {ev['species']}!"
        )
    if kind == "starve":
        return f"\U0001f480 {ev['emoji']} {ev['name']} the {ev['species']} starved"
    if kind == "age_death":
        return f"\U0001f534 {ev['emoji']} {ev['name']} the {ev['species']} died of old age ({ev.get('age', '?')} ticks)"
    if kind == "disease_death":
        return f"\U0001f9a0 {ev['emoji']} {ev['name']} the {ev['species']} succumbed to disease"
    return ""


# -- Emoji maps -----------------------------------------------------------


_SPECIES_TO_EMOJI: dict[str, str] = {}


def _build_species_emoji_map() -> None:
    for e, _, s in ALL_HERBIVORES + ALL_CARNIVORES:
        _SPECIES_TO_EMOJI[s] = e


_build_species_emoji_map()


def update_emoji_maps() -> None:
    for e, _, s in CUSTOM_HERBIVORES + CUSTOM_CARNIVORES:
        EMOJI_TO_SPECIES[e] = s
        _SPECIES_TO_EMOJI[s] = e


# -- Params ---------------------------------------------------------------


_PARAM_ADJUSTMENTS = [
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
    if idx < 0 or idx >= len(_PARAM_ADJUSTMENTS):
        return
    name, step, minimum, maximum = _PARAM_ADJUSTMENTS[idx]
    current = getattr(config, name)
    new_val = current + step * direction
    if isinstance(step, float):
        new_val = round(new_val, 4)
    new_val = max(minimum, min(maximum, new_val))
    setattr(config, name, new_val)


def _process_events(state: GameState, events: list[dict]) -> None:
    state.flashes = {}
    for ev in events:
        state.flashes[(ev["x"], ev["y"])] = ev["kind"]
        state.grid.mark_dirty(ev["x"], ev["y"])
        msg = event_to_message(ev)
        if msg:
            state.ticker.append(msg)
    if len(state.ticker) > 100:
        state.ticker = state.ticker[-100:]
    state.ticker_offset = 0


# -- Textual UI -----------------------------------------------------------


class SpeciesPickerScreen(Screen):
    BINDINGS = [
        Binding("enter", "toggle_or_start", "Toggle / Start"),
        Binding("space", "toggle_or_start", "Toggle / Start", show=False),
        Binding("c", "create", "Create Species"),
        Binding("d", "delete", "Delete Custom"),
        Binding("a", "all_on", "All On"),
        Binding("n", "all_off", "All Off"),
        Binding("escape", "quit", "Quit"),
        Binding("Q", "debug_dump", "Debug Dump", show=False),
    ]

    def __init__(self, config: Config, preset: str, args: argparse.Namespace, id: str | None = None) -> None:
        super().__init__(id=id)
        self.config = config
        self.preset = preset
        self.args = args
        self.on_map: dict[str, bool] = {e: True for e, _, _ in ALL_HERBIVORES}
        for e, _, _ in ALL_CARNIVORES:
            self.on_map[e] = True
        for e, _, _ in CUSTOM_HERBIVORES:
            self.on_map.setdefault(e, True)
        for e, _, _ in CUSTOM_CARNIVORES:
            self.on_map.setdefault(e, True)
        self.cursor_emoji: str | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(
            "[b]Click a row[/] or press [b]Enter/Space[/] to toggle on/off. "
            "[b]a[/] turn all on, [b]n[/] turn all off, [b]c[/] create species, "
            "[b]Esc[/] start the zoo.",
            id="picker-help",
        )
        yield DataTable(id="species-table")
        yield Button("Start Zoo ▶", id="start-button", variant="success")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#species-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.show_cursor = True
        table.add_columns("Emoji", "Type", "Species", "Status", "Traits")
        self._refresh_table()

    def _refresh_table(self) -> None:
        for he, _, _ in CUSTOM_HERBIVORES:
            self.on_map.setdefault(he, True)
        for ce, _, _ in CUSTOM_CARNIVORES:
            self.on_map.setdefault(ce, True)
        table = self.query_one("#species-table", DataTable)
        previous_cursor = self.cursor_emoji
        table.clear()
        first_emoji: str | None = None

        def add_entry(emoji: str, species: str, kind: str, traits_obj) -> None:
            nonlocal first_emoji
            on = self.on_map.get(emoji, True)
            mark = "[green]on[/]" if on else "[red]off[/]"
            hunt = " hunts carns" if getattr(traits_obj, "can_hunt_carns", False) else ""
            traits = f"vis:{traits_obj.vision} life:{traits_obj.max_age} breed:{traits_obj.repro_threshold}{hunt}"
            table.add_row(
                emoji,
                f"[{'green' if kind == 'herb' else 'red'}]{kind}[/]",
                species,
                mark,
                traits,
                key=emoji,
            )
            if first_emoji is None:
                first_emoji = emoji

        for emoji, _, species in ALL_HERBIVORES:
            add_entry(emoji, species, "herb", HERBIVORE_TRAITS.get(species, SpeciesTraits()))
        for emoji, _, species in CUSTOM_HERBIVORES:
            add_entry(
                emoji,
                f"{species} [cyan][custom][/]",
                "herb",
                CUSTOM_TRAITS_BY_KIND["herbivore"].get(species, SpeciesTraits()),
            )
        for emoji, _, species in ALL_CARNIVORES:
            add_entry(emoji, species, "carn", CARNIVORE_TRAITS.get(species, SpeciesTraits()))
        for emoji, _, species in CUSTOM_CARNIVORES:
            add_entry(
                emoji,
                f"{species} [cyan][custom][/]",
                "carn",
                CUSTOM_TRAITS_BY_KIND["carnivore"].get(species, SpeciesTraits()),
            )

        target = previous_cursor if previous_cursor in self.on_map else first_emoji
        if target is not None:
            try:
                row_index = table.get_row_index(target)
                table.move_cursor(row=row_index, animate=False)
                self.cursor_emoji = target
            except Exception:
                table.move_cursor(row=0, animate=False)
                self.cursor_emoji = first_emoji
        else:
            table.move_cursor(row=0, animate=False)

    def _emoji_at_cursor(self) -> str | None:
        table = self.query_one("#species-table", DataTable)
        if table.row_count == 0:
            return None
        try:
            row_index = table.cursor_row
        except Exception:
            return None
        if row_index is None or row_index < 0:
            return None
        try:
            row_key = table.coordinate_to_cell_key((row_index, 0)).row_key
        except Exception:
            return None
        if row_key is None or row_key.value is None:
            return None
        return str(row_key.value)

    def _toggle_at_cursor(self) -> None:
        emoji = self._emoji_at_cursor()
        if emoji is None or emoji not in self.on_map:
            return
        self.on_map[emoji] = not self.on_map.get(emoji, False)
        self._refresh_table()

    def on_data_table_row_highlighted(self, event) -> None:
        if event.row_key is not None and event.row_key.value is not None:
            self.cursor_emoji = str(event.row_key.value)

    def on_data_table_row_selected(self, event) -> None:
        if event.row_key is None or event.row_key.value is None:
            return
        emoji = str(event.row_key.value)
        if emoji not in self.on_map:
            return
        self.on_map[emoji] = not self.on_map.get(emoji, False)
        self._refresh_table()

    def on_button_pressed(self, event) -> None:
        if event.button.id == "start-button":
            self.action_start()

    def action_toggle_or_start(self) -> None:
        self._toggle_at_cursor()

    def action_start(self) -> None:
        sel_herbs = [e for e, _, _ in ALL_HERBIVORES if self.on_map.get(e)]
        sel_herbs += [e for e, _, _ in CUSTOM_HERBIVORES if self.on_map.get(e)]
        sel_carns = [e for e, _, _ in ALL_CARNIVORES if self.on_map.get(e)]
        sel_carns += [e for e, _, _ in CUSTOM_CARNIVORES if self.on_map.get(e)]
        self.app.push_screen(GameScreen(self.config, sel_herbs, sel_carns, self.args))

    def action_create(self) -> None:
        def on_done_and_refocus() -> None:
            self._refresh_table()
            self.query_one("#species-table").focus()

        self.app.push_screen(CreateSpeciesScreen(self.config, self.args, on_done=on_done_and_refocus))

    def action_delete(self) -> None:
        custom = [e for e, _, _ in CUSTOM_HERBIVORES] + [e for e, _, _ in CUSTOM_CARNIVORES]
        if custom:
            to_delete = custom[-1]
            name = EMOJI_TO_SPECIES.get(to_delete, "")
            if name:
                remove_custom_species(name)
                self.on_map.pop(to_delete, None)
                self._refresh_table()

    def action_all_on(self) -> None:
        for e in self.on_map:
            self.on_map[e] = True
        self._refresh_table()

    def action_all_off(self) -> None:
        for e in self.on_map:
            self.on_map[e] = False
        self._refresh_table()

    def action_quit(self) -> None:
        self.app.exit()

    def action_debug_dump(self) -> None:
        path = write_debug_dump()
        self.app.exit(message=f"Debug dump written to {path}")


class CreateSpeciesScreen(Screen):
    CSS = """
    #create-body { height: 1fr; }
    #emoji-grid { height: 8; }
    #name-kind-row { height: 3; align: left middle; }
    #name-input { width: 30; }
    #kind-herb { width: 20; margin-left: 2; }
    #kind-carn { width: 20; }
    #name-error { height: auto; max-height: 2; }
    #traits-table { height: 14; }
    #traits-help { height: 1; color: $text-muted; }
    #action-row { height: 3; align: center middle; }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("r", "roll", "Roll All"),
        Binding("1", "kind_herb", show=False),
        Binding("2", "kind_carn", show=False),
    ]

    def __init__(self, config: Config, args: argparse.Namespace, on_done: Callable[[], None] | None = None) -> None:
        super().__init__()
        self.config = config
        self.args = args
        self.on_done = on_done
        self._emoji: str | None = None
        self._name: str = ""
        self._kind: str | None = None
        self._traits: SpeciesTraits | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="create-body"):
            yield DataTable(id="emoji-grid", cursor_type="cell")
            with Horizontal(id="name-kind-row"):
                yield Input(
                    placeholder="species name (3-16 chars, a-z 0-9 _)",
                    id="name-input",
                )
                yield Button("1 Herbivore", id="kind-herb", variant="default")
                yield Button("2 Carnivore", id="kind-carn", variant="default")
            yield Static("", id="name-error")
            yield DataTable(id="traits-table", cursor_type="row")
            yield Static("\u2191/\u2193 select  +/- adjust  r roll all", id="traits-help")
            with Horizontal(id="action-row"):
                yield Button("Roll Random", id="btn-roll", variant="default")
                yield Button("Save Species", id="btn-save", variant="primary")
                yield Button("Cancel", id="btn-cancel", variant="default")
        yield Footer()

    def on_mount(self) -> None:
        self._build_emoji_grid()
        self._build_traits_table()
        self.query_one("#emoji-grid").focus()

    def _build_emoji_grid(self) -> None:
        table = self.query_one("#emoji-grid", DataTable)
        used_emojis = {e for e, _, _ in ALL_HERBIVORES + ALL_CARNIVORES + CUSTOM_HERBIVORES + CUSTOM_CARNIVORES}
        cols = []
        for r, row in enumerate(CUSTOM_EMOJI_GRID):
            for _c, (emoji, label) in enumerate(row):
                if r == 0:
                    cols.append(f" {emoji or label} ")
        table.add_columns(*cols)
        for row in CUSTOM_EMOJI_GRID:
            cells = []
            for emoji, label in row:
                if emoji:
                    if emoji in used_emojis:
                        cells.append(f"[dim]{emoji}[/]")
                    else:
                        cells.append(f" {emoji} ")
                else:
                    cells.append(f"[dim]{label}[/]")
            table.add_row(*cells)

    def _build_traits_table(self) -> None:
        if not self._traits:
            self._traits = roll_traits(self._kind or "herbivore")
        table = self.query_one("#traits-table", DataTable)
        cursor = table.cursor_coordinate
        table.clear()
        table.add_columns("Trait", "Value", "Range")
        for fname, ftype, lo, hi in _TRAIT_FIELDS:
            val = getattr(self._traits, fname)
            if ftype == "bool":
                val_str = "yes" if val else "no"
                rng = "y/n"
            elif ftype == "float":
                val_str = f"{val:.2f}"
                rng = f"{lo:.2f}\u2013{hi:.2f}"
            else:
                val_str = str(val)
                rng = f"{lo}\u2013{hi}"
            table.add_row(fname, val_str, rng)
        table.cursor_coordinate = cursor

    def on_data_table_cell_selected(self, event) -> None:
        if event.data_table.id != "emoji-grid":
            return
        r, c = event.coordinate
        if 0 <= r < len(CUSTOM_EMOJI_GRID) and 0 <= c < len(CUSTOM_EMOJI_GRID[0]):
            emoji, label = CUSTOM_EMOJI_GRID[r][c]
            if not emoji or not label:
                return
            used_emojis = {e for e, _, _ in ALL_HERBIVORES + ALL_CARNIVORES + CUSTOM_HERBIVORES + CUSTOM_CARNIVORES}
            if emoji in used_emojis:
                return
            self._emoji = emoji

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "name-input":
            return
        self._name = event.value.strip().lower().replace(" ", "_")
        error = ""
        if len(self._name) < 3 or len(self._name) > 16:
            error = f"Name must be 3-16 chars (got {len(self._name)})"
        elif not all(c.isalnum() or c == "_" for c in self._name):
            error = "Name must be alphanumeric + underscore only"
        elif self._name in HERBIVORE_TRAITS or self._name in CARNIVORE_TRAITS:
            error = f"'{self._name}' conflicts with a built-in species"
        self.query_one("#name-error").update(f"[red]{error}[/]" if error else "")

    def on_input_submitted(self, event) -> None:
        if event.input.id == "name-input":
            self.query_one("#traits-table").focus()

    def on_key(self, event) -> None:
        focused = self.app.focused
        if not focused:
            return
        if focused.id == "emoji-grid" and event.key == "enter":
            if self._emoji:
                self.query_one("#name-input").focus()
            event.prevent_default()
            return
        if focused.id == "traits-table" and self._traits:
            if event.key in ("plus", "="):
                self._adjust_trait(1)
                event.prevent_default()
            elif event.key in ("minus", "-"):
                self._adjust_trait(-1)
                event.prevent_default()

    def _adjust_trait(self, direction: int) -> None:
        if not self._traits:
            return
        table = self.query_one("#traits-table", DataTable)
        row = table.cursor_coordinate.row
        if row >= len(_TRAIT_FIELDS):
            return
        fname, ftype, lo, hi = _TRAIT_FIELDS[row]
        current = getattr(self._traits, fname)
        if ftype == "bool":
            setattr(self._traits, fname, not current)
        elif ftype == "float":
            new_val = round(current + 0.05 * direction, 2)
            setattr(self._traits, fname, max(lo, min(hi, new_val)))
        else:
            new_val = current + direction
            setattr(self._traits, fname, max(lo, min(hi, new_val)))
        self._build_traits_table()

    def on_button_pressed(self, event) -> None:
        if event.button.id == "btn-roll":
            self.action_roll()
        elif event.button.id == "btn-save":
            self.action_save()
        elif event.button.id == "btn-cancel":
            self.action_cancel()
        elif event.button.id == "kind-herb":
            self._set_kind("herbivore")
        elif event.button.id == "kind-carn":
            self._set_kind("carnivore")

    def _set_kind(self, kind: str) -> None:
        self._kind = kind
        self._refresh_kind_buttons()
        self._traits = roll_traits(kind)
        self._build_traits_table()

    def _refresh_kind_buttons(self) -> None:
        herb = self.query_one("#kind-herb", Button)
        carn = self.query_one("#kind-carn", Button)
        if self._kind == "herbivore":
            herb.variant = "success"
            carn.variant = "default"
        elif self._kind == "carnivore":
            herb.variant = "default"
            carn.variant = "error"
        else:
            herb.variant = "default"
            carn.variant = "default"

    def action_kind_herb(self) -> None:
        self._set_kind("herbivore")

    def action_kind_carn(self) -> None:
        self._set_kind("carnivore")

    def action_roll(self) -> None:
        if self._kind:
            self._traits = roll_traits(self._kind)
            self._build_traits_table()

    def action_save(self) -> None:
        err = self._validate()
        if err:
            self.query_one("#name-error").update(f"[red]{err}[/]")
            return
        add_custom_species(self._name, self._emoji, self._kind, self._traits)
        self.app.notify(f"Created '{self._emoji} {self._name}'!")
        if self.on_done:
            self.on_done()
        self.app.pop_screen()

    def _validate(self) -> str:
        if not self._emoji:
            return "Pick an emoji from the grid"
        if not self._name or len(self._name) < 3:
            return "Enter a name (3-16 chars)"
        if not all(c.isalnum() or c == "_" for c in self._name):
            return "Name must be alphanumeric + underscore only"
        if self._name in HERBIVORE_TRAITS or self._name in CARNIVORE_TRAITS:
            return f"'{self._name}' conflicts with a built-in species"
        if not self._kind:
            return "Choose herbivore or carnivore (press 1 or 2)"
        return ""

    def action_cancel(self) -> None:
        self.app.pop_screen()


_COLOR_STYLE: dict[str, str] = {
    "92": "green",
    "97": "white",
    "33": "yellow",
    "37": "grey82",
    "93": "bright_yellow",
    "32": "dark_green",
    "95": "magenta",
    "90": "grey50",
    "91": "red",
    "38;5;166": "dark_orange",
    "38;5;22": "dark_green",
}

_FLASH_STYLE: dict[str, str] = {
    "41": "on dark_red",
    "44": "on dark_blue",
    "100": "on grey37",
    "45": "on dark_magenta",
    "105": "on dark_magenta",
    "52": "on #531",
}


def _make_cell_text(e: Entity | None, flash: str | None = None) -> Text:
    if flash is not None:
        t = Text(flash)
        style = _FLASH_STYLE.get(flash, "")
        if style:
            t.stylize(style)
        return t
    if e is None:
        return Text(EMPTY_STR)
    t = Text(e.emoji)
    if e.is_diseased:
        t.stylize("on #531")
    elif e.color and e.kind in (Kind.HERBIVORE, Kind.CARNIVORE):
        style = _COLOR_STYLE.get(e.color, "")
        if style:
            t.stylize(style)
    return t


class GridView(Static):
    def __init__(
        self, state: GameState, god_cursor: tuple[int, int] = (0, 0), god_mode: bool = False, **kwargs
    ) -> None:
        super().__init__(**kwargs)
        self.state = state
        self.god_cursor = god_cursor
        self.god_mode = god_mode
        self._cell_cache: dict[tuple[int, int], Text] = {}
        self._grid_id: int = id(state.grid)

    def render(self) -> Table:
        grid = self.state.grid

        if id(grid) != self._grid_id:
            self._cell_cache.clear()
            grid._dirty = {(x, y) for x in range(grid.w) for y in range(grid.h)}
            self._grid_id = id(grid)

        dirty = grid._dirty
        cache = self._cell_cache
        flashes = self.state.flashes
        gc = self.god_cursor if self.god_mode else None

        table = Table(
            show_header=False,
            show_edge=False,
            box=None,
            pad_edge=False,
            padding=(0, 0),
        )
        for _ in range(grid.w):
            table.add_column(width=2, no_wrap=True)

        if not dirty and cache:
            for y in range(grid.h):
                row = [cache.get((x, y), Text(EMPTY_STR)) for x in range(grid.w)]
                table.add_row(*row)
            return table

        for y in range(grid.h):
            row: list[Text] = []
            for x in range(grid.w):
                pos = (x, y)
                is_dirty = pos in dirty or pos == gc
                if not is_dirty and pos in cache:
                    row.append(cache[pos])
                    continue
                flash = flashes.get(pos)
                if flash:
                    t = _make_cell_text(None, flash)
                else:
                    e = grid.cells[y][x]
                    t = _make_cell_text(e)
                if gc and pos == gc:
                    t.stylize("on blue")
                cache[pos] = t
                row.append(t)
            table.add_row(*row)

        dirty.clear()
        return table


class StatsBar(Static):
    def __init__(self, state: GameState, **kwargs) -> None:
        super().__init__(**kwargs)
        self.state = state

    def render(self) -> Table:
        s = self.state
        counts = s.pop_counts
        p = counts[Kind.PLANT]
        h = counts[Kind.HERBIVORE]
        c = counts[Kind.CARNIVORE]
        hist_max = max(
            max(s.hist["plant"]) if s.hist["plant"] else 1,
            max(s.hist["herb"]) if s.hist["herb"] else 1,
            max(s.hist["carn"]) if s.hist["carn"] else 1,
            1,
        )
        sp = sparkline(s.hist["plant"][-50:], hist_max)
        sh = sparkline(s.hist["herb"][-50:], hist_max)
        sc = sparkline(s.hist["carn"][-50:], hist_max)
        first_h = s.selected_herbs[0] if s.selected_herbs else "?"
        first_c = s.selected_carns[0] if s.selected_carns else "?"
        st = s.stats
        avg = f"{st.avg_lifespan:.0f}" if st.avg_lifespan > 0 else "-"
        table = Table(show_header=False, show_edge=False, box=None, padding=(0, 1))
        table.add_column(ratio=1)
        table.add_row(Text.assemble((f"🌿 plants      {p:>4}  {sp}", "")))
        table.add_row(Text.assemble((f"{first_h} herbivores  {h:>4}  {sh}", "")))
        table.add_row(Text.assemble((f"{first_c} carnivores  {c:>4}  {sc}", "")))
        table.add_row(
            Text.assemble(
                (
                    f"Births:{st.total_births} Kills:{st.total_kills} "
                    f"Starved:{st.total_starvations} Age:{st.total_deaths_age} "
                    f"Disease:{st.total_deaths_disease}",
                    "",
                )
            )
        )
        table.add_row(Text.assemble((f"Avg lifespan: {avg}  Total deaths: {st.total_deaths}", "")))
        return table


class TickerWidget(Static):
    def __init__(self, state: GameState, **kwargs) -> None:
        super().__init__(**kwargs)
        self.state = state

    def render(self) -> Table:
        table = Table(show_header=False, show_edge=False, box=None, padding=(0, 1))
        table.add_column(ratio=1)
        total = len(self.state.ticker)
        if total > 0:
            base = max(0, total - 3 + self.state.ticker_offset)
            for i in range(3):
                idx = base + i
                if 0 <= idx < total:
                    msg = self.state.ticker[idx]
                    if len(msg) > 70:
                        msg = msg[:67] + "..."
                    table.add_row(msg)
                else:
                    table.add_row("")
        else:
            for _ in range(3):
                table.add_row("")
        return table


def write_debug_dump(state: GameState | None = None) -> str:
    dump: dict[str, object] = {
        "timestamp": datetime.datetime.now().isoformat(),
        "custom_species_file": CUSTOM_SPECIES_FILE,
        "custom_species_file_exists": os.path.isfile(CUSTOM_SPECIES_FILE),
    }
    try:
        if os.path.isfile(CUSTOM_SPECIES_FILE):
            with open(CUSTOM_SPECIES_FILE) as f:
                dump["custom_species_data"] = json.load(f)
    except Exception as e:
        dump["custom_species_load_error"] = str(e)

    dump["CUSTOM_HERBIVORES"] = CUSTOM_HERBIVORES
    dump["CUSTOM_CARNIVORES"] = CUSTOM_CARNIVORES
    dump["CUSTOM_TRAITS_HERB"] = {k: asdict(v) for k, v in CUSTOM_TRAITS_BY_KIND["herbivore"].items()}
    dump["CUSTOM_TRAITS_CARN"] = {k: asdict(v) for k, v in CUSTOM_TRAITS_BY_KIND["carnivore"].items()}
    dump["_SPECIES_TO_EMOJI_custom"] = {
        s: e
        for s, e in _SPECIES_TO_EMOJI.items()
        if s in CUSTOM_TRAITS_BY_KIND["herbivore"] or s in CUSTOM_TRAITS_BY_KIND["carnivore"]
    }
    dump["EMOJI_TO_SPECIES_custom"] = {
        e: s
        for e, s in EMOJI_TO_SPECIES.items()
        if s in CUSTOM_TRAITS_BY_KIND["herbivore"] or s in CUSTOM_TRAITS_BY_KIND["carnivore"]
    }

    if state is not None:
        grid_counts: dict[str, int] = {}
        for row in state.grid.cells:
            for c in row:
                if c is None:
                    continue
                key = f"{c.kind.name}:{c.species}:{c.emoji}"
                grid_counts[key] = grid_counts.get(key, 0) + 1
        dump["grid_counts"] = grid_counts
        dump["tick"] = state.tick
        dump["season"] = state.season
        dump["selected_herbs"] = state.selected_herbs
        dump["selected_carns"] = state.selected_carns
        cfg = asdict(state.config)
        cfg.pop("default_herb_species", None)
        cfg.pop("default_carn_species", None)
        dump["config"] = cfg

    path = os.path.join(os.path.expanduser("~"), ".emoji_zoo", "debug_dump.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(dump, f, indent=2, default=str)
    return path


class GameScreen(Screen):
    BINDINGS = [
        Binding("space", "toggle_pause", "Pause"),
        Binding("s", "step_tick", "Step", show=False),
        Binding("plus", "speed_up", "Faster", show=False),
        Binding("minus", "slow_down", "Slower", show=False),
        Binding("equal", "speed_up", "Faster", show=False),
        Binding("r", "reset", "Reset", show=False),
        Binding("one", "drop_plants", "Drop Plants", show=False),
        Binding("two", "drop_herbs", "Drop Herbs", show=False),
        Binding("three", "drop_carns", "Drop Carns", show=False),
        Binding("g", "toggle_god", "God Mode", show=False),
        Binding("x", "god_delete", "Delete", show=False),
        Binding("p", "toggle_params", "Params", show=False),
        Binding("h", "toggle_help", "Help", show=False),
        Binding("question", "toggle_help", "Help", show=False),
        Binding("left_square_bracket", "scroll_back", "Scroll Back", show=False),
        Binding("right_square_bracket", "scroll_fwd", "Scroll Fwd", show=False),
        Binding("S", "save", "Save", show=False),
        Binding("L", "load", "Load", show=False),
        Binding("q", "quit", "Quit", show=False),
        Binding("Q", "debug_dump", "Debug Dump", show=False),
        Binding("escape", "god_exit", "Exit God", show=False),
    ]

    CSS = """
    Screen { layer: default; }
    #grid-view { height: 1fr; overflow-y: auto; }
    #stats-bar { height: auto; max-height: 8; }
    #ticker { height: auto; max-height: 5; }
    #header-bar { height: auto; }
    #help-bar { height: auto; }
    #god-bar { height: auto; }
    #param-bar { height: auto; }
    """

    def __init__(
        self, config: Config, selected_herbs: list[str], selected_carns: list[str], args: argparse.Namespace
    ) -> None:
        super().__init__()
        self.game_state = GameState(
            grid=Grid(80, 30), config=config, selected_herbs=selected_herbs, selected_carns=selected_carns
        )
        populate(self.game_state.grid, config, selected_herbs, selected_carns)
        self.speed = max(1, args.speed)
        self.paused = False
        self.god_mode = False
        self.cursor = [self.game_state.grid.w // 2, self.game_state.grid.h // 2]
        self.show_help = False
        self.show_params = False
        self.param_sel = 0
        self.save_file = args.save_file
        self._timer = None

    def compose(self) -> ComposeResult:
        yield Static(id="header-bar")
        yield GridView(self.game_state, id="grid-view")
        yield StatsBar(self.game_state, id="stats-bar")
        yield TickerWidget(self.game_state, id="ticker")
        yield Static(self._controls_text(), id="help-bar")
        yield Static("", id="god-bar")
        yield Static("", id="param-bar")

    def on_mount(self) -> None:
        self._timer = self.set_interval(self.game_state.config.base_delay / self.speed, self._tick)

    def _tick(self) -> None:
        if self.paused:
            return
        events: list[dict] = []
        try:
            step(self.game_state, events)
        except Exception as e:
            logger.error("Step error: %s", e)
            self.game_state.ticker.append(f"ERROR: {e}")
        _process_events(self.game_state, events)
        self._refresh_all()

    def _refresh_all(self) -> None:
        self.query_one("#header-bar").update(self._header_text())
        gv = self.query_one("#grid-view", GridView)
        gv.god_cursor = tuple(self.cursor)
        gv.god_mode = self.god_mode
        gv.refresh()
        self.query_one("#stats-bar", StatsBar).refresh()
        self.query_one("#ticker", TickerWidget).refresh()
        god_bar = self.query_one("#god-bar")
        param_bar = self.query_one("#param-bar")
        if self.god_mode:
            god_bar.update(self._god_text())
            god_bar.display = True
        else:
            god_bar.display = False
        if self.show_params:
            param_bar.update(self._params_text())
            param_bar.display = True
        else:
            param_bar.display = False

    def _header_text(self) -> str:
        gs = self.game_state
        status = (
            "** PARAMS **"
            if self.show_params
            else "** GOD **"
            if self.god_mode
            else "PAUSED"
            if self.paused
            else "running"
        )
        season_bar = " ".join(f"{'>' if i == gs.season else ' '}{SEASON_NAMES[i][:3]}" for i in range(4))
        return (
            f"  Emoji Zoo -- tick {gs.tick:>5}  speed {self.speed}x  "
            f"[{status}]  {gs.season_name} "
            f"({gs.season_progress}/{gs.config.season_length})  "
            f"[{season_bar}]"
        )

    def _controls_text(self) -> str:
        return (
            "  SPACE pause  s step  +/- speed  r reset  1/2/3 drop  "
            "g god  p params  h help  [\\[]/\\[]] scroll  S save  L load  q quit"
        )

    def _god_text(self) -> str:
        gs = self.game_state
        cx, cy = self.cursor
        e = gs.grid.get(cx, cy)
        if e:
            info = f"  {e.emoji} {e.name or '?'} the {e.species}"
            if e.traits:
                info += f"  energy:{e.energy}/{e.traits.max_energy}  age:{e.age}/{e.traits.max_age}"
            info += f"  thirst:{e.thirst}"
            if e.is_diseased:
                info += f"  diseased:{e.diseased}t"
            info += f"  [{cx},{cy}]"
        else:
            info = f"  (empty)  [{cx},{cy}]"
        return info

    def _params_text(self) -> str:
        params = _param_list(self.game_state.config)
        lines = ["  -- PARAMETERS (up/down select, +/- adjust) --"]
        for i, (name, val) in enumerate(params):
            mark = ">" if i == self.param_sel else " "
            lines.append(f"  {mark} {name}: {val}")
        return "\n".join(lines)

    def on_key(self, event) -> None:
        if self.show_params:
            if event.key in ("p", "escape"):
                self.show_params = False
                self._refresh_all()
                event.prevent_default()
            elif event.key == "up":
                self.param_sel = max(0, self.param_sel - 1)
                self._refresh_all()
                event.prevent_default()
            elif event.key == "down":
                mx = len(_param_list(self.game_state.config)) - 1
                self.param_sel = min(mx, self.param_sel + 1)
                self._refresh_all()
                event.prevent_default()
            elif event.key in ("plus", "equal"):
                _adjust_param(self.game_state.config, self.param_sel, 1)
                self._refresh_all()
                event.prevent_default()
            elif event.key == "minus":
                _adjust_param(self.game_state.config, self.param_sel, -1)
                self._refresh_all()
                event.prevent_default()
            return

        if self.god_mode:
            self._handle_god_key(event)
            return

        if event.key in ("plus", "equal"):
            self.speed = min(10, self.speed + 1)
            self._restart_timer()
            self._refresh_all()
            event.prevent_default()
        elif event.key == "minus":
            self.speed = max(1, self.speed - 1)
            self._restart_timer()
            self._refresh_all()
            event.prevent_default()

    def _handle_god_key(self, event) -> None:
        gs = self.game_state
        handled = True
        if event.key == "escape":
            self.god_mode = False
        elif event.key == "up":
            self.cursor[1] = max(0, self.cursor[1] - 1)
        elif event.key == "down":
            self.cursor[1] = min(gs.grid.h - 1, self.cursor[1] + 1)
        elif event.key == "left":
            self.cursor[0] = max(0, self.cursor[0] - 1)
        elif event.key == "right":
            self.cursor[0] = min(gs.grid.w - 1, self.cursor[0] + 1)
        elif event.character == "1":
            cx, cy = self.cursor
            if gs.grid.cells[cy][cx] is None:
                gs.grid.set_cell(cx, cy, make_plant())
        elif event.character == "2" and gs.selected_herbs:
            cx, cy = self.cursor
            if gs.grid.cells[cy][cx] is None:
                e = make_herb(gs.selected_herbs)
                if e:
                    gs.grid.set_cell(cx, cy, e)
        elif event.character == "3" and gs.selected_carns:
            cx, cy = self.cursor
            if gs.grid.cells[cy][cx] is None:
                e = make_carn(gs.selected_carns)
                if e:
                    gs.grid.set_cell(cx, cy, e)
        elif event.character == "x":
            cx, cy = self.cursor
            cell = gs.grid.cells[cy][cx]
            if cell and cell.kind != Kind.WATER:
                gs.grid.set_cell(cx, cy, None)
        elif event.character == "g":
            self.god_mode = False
        elif event.character == "r":
            gw, gh = gs.grid.w, gs.grid.h
            gs.grid = Grid(gw, gh)
            populate(gs.grid, gs.config, gs.selected_herbs, gs.selected_carns)
            gs.tick = 0
            gs.season = 0
            gs.hist = {"plant": [], "herb": [], "carn": []}
            gs.ticker = []
            gs.flashes = {}
            gs.stats = Stats()
        elif event.character == "s" and self.paused:
            events: list[dict] = []
            try:
                step(gs, events)
            except Exception as e:
                logger.error("Step error: %s", e)
                gs.ticker.append(f"ERROR: {e}")
            _process_events(gs, events)
        elif event.character == "S":
            if save_state(gs, self.save_file):
                gs.notification = f"Saved to {self.save_file}"
                gs.notification_ticks = 5
        elif event.character == "L":
            loaded = load_state(self.save_file)
            if loaded:
                self.game_state = loaded
                self.cursor = [loaded.grid.w // 2, loaded.grid.h // 2]
                loaded.notification = f"Loaded from {self.save_file}"
                loaded.notification_ticks = 5
        else:
            handled = False
        if handled:
            self._refresh_all()
            event.prevent_default()

    def action_toggle_pause(self) -> None:
        self.paused = not self.paused
        self._refresh_all()

    def action_step_tick(self) -> None:
        if self.paused:
            events: list[dict] = []
            try:
                step(self.game_state, events)
            except Exception as e:
                logger.error("Step error: %s", e)
                self.game_state.ticker.append(f"ERROR: {e}")
            _process_events(self.game_state, events)
            self._refresh_all()

    def action_speed_up(self) -> None:
        self.speed = min(10, self.speed + 1)
        self._restart_timer()
        self._refresh_all()

    def action_slow_down(self) -> None:
        self.speed = max(1, self.speed - 1)
        self._restart_timer()
        self._refresh_all()

    def action_reset(self) -> None:
        gs = self.game_state
        gw, gh = gs.grid.w, gs.grid.h
        gs.grid = Grid(gw, gh)
        populate(gs.grid, gs.config, gs.selected_herbs, gs.selected_carns)
        gs.tick = 0
        gs.season = 0
        gs.hist = {"plant": [], "herb": [], "carn": []}
        gs.ticker = []
        gs.flashes = {}
        gs.stats = Stats()
        self._refresh_all()

    def action_drop_plants(self) -> None:
        drop_creatures(self.game_state.grid, make_plant, self.game_state.config.drop_plant_n)
        self._refresh_all()

    def action_drop_herbs(self) -> None:
        gs = self.game_state
        if gs.selected_herbs:
            drop_creatures(gs.grid, lambda: make_herb(gs.selected_herbs), gs.config.drop_herb_n)
            self._refresh_all()

    def action_drop_carns(self) -> None:
        gs = self.game_state
        if gs.selected_carns:
            drop_creatures(gs.grid, lambda: make_carn(gs.selected_carns), gs.config.drop_carn_n)
            self._refresh_all()

    def action_toggle_god(self) -> None:
        self.god_mode = not self.god_mode
        if self.god_mode:
            self.cursor = [self.game_state.grid.w // 2, self.game_state.grid.h // 2]
        self._refresh_all()

    def action_god_delete(self) -> None:
        if self.god_mode:
            cx, cy = self.cursor
            cell = self.game_state.grid.cells[cy][cx]
            if cell and cell.kind != Kind.WATER:
                self.game_state.grid.set_cell(cx, cy, None)
                self._refresh_all()

    def action_god_exit(self) -> None:
        if self.god_mode:
            self.god_mode = False
            self._refresh_all()

    def action_toggle_params(self) -> None:
        self.show_params = not self.show_params
        if self.show_params:
            self.param_sel = 0
        self._refresh_all()

    def action_toggle_help(self) -> None:
        self.show_help = not self.show_help
        hb = self.query_one("#help-bar")
        if self.show_help:
            hb.update(
                "  SPACE pause  s step  +/- speed  r reset  "
                "1/2/3 drop  g god  p params  [\\[]/\\[]] scroll  "
                "S save  L load  q quit"
            )
        else:
            hb.update(self._controls_text())
        hb.refresh()

    def action_scroll_back(self) -> None:
        gs = self.game_state
        gs.ticker_offset = max(-len(gs.ticker), gs.ticker_offset - 1)
        self.query_one("#ticker", TickerWidget).refresh()

    def action_scroll_fwd(self) -> None:
        gs = self.game_state
        gs.ticker_offset = min(0, gs.ticker_offset + 1)
        self.query_one("#ticker", TickerWidget).refresh()

    def action_save(self) -> None:
        if save_state(self.game_state, self.save_file):
            self.game_state.notification = f"Saved to {self.save_file}"
            self.game_state.notification_ticks = 5
        else:
            self.game_state.notification = "Save failed!"
            self.game_state.notification_ticks = 5
        self._refresh_all()

    def action_load(self) -> None:
        loaded = load_state(self.save_file)
        if loaded:
            self.game_state = loaded
            self.cursor = [loaded.grid.w // 2, loaded.grid.h // 2]
            loaded.notification = f"Loaded from {self.save_file}"
            loaded.notification_ticks = 5
        else:
            self.game_state.notification = f"Load failed! ({self.save_file})"
            self.game_state.notification_ticks = 5
        self._refresh_all()

    def action_quit(self) -> None:
        self.app.exit()

    def action_debug_dump(self) -> None:
        path = write_debug_dump(self.game_state)
        self.game_state.notification = f"Debug dump written to {path}"
        self.game_state.notification_ticks = 8
        self._refresh_all()

    def _restart_timer(self) -> None:
        if self._timer:
            self._timer.stop()
        self._timer = self.set_interval(self.game_state.config.base_delay / self.speed, self._tick)


class ZooApp(App):
    CSS = """
    Screen { background: $surface; }
    """

    def __init__(self, config: Config, preset: str, args: argparse.Namespace) -> None:
        super().__init__()
        self.config = config
        self.preset = preset
        self.args = args

    def on_mount(self) -> None:
        load_custom_species()
        if self.args.load:
            state = load_state(self.args.save_file)
            if state:
                self.push_screen(GameScreen(state.config, state.selected_herbs, state.selected_carns, self.args))
            else:
                self.exit(message=f"Could not load from {self.args.save_file}")
        elif self.args.no_picker:
            herbs = [e for e, _, _ in ALL_HERBIVORES]
            herbs += [e for e, _, _ in CUSTOM_HERBIVORES]
            carns = [e for e, _, _ in ALL_CARNIVORES]
            carns += [e for e, _, _ in CUSTOM_CARNIVORES]
            self.push_screen(GameScreen(self.config, herbs, carns, self.args))
        else:
            self.push_screen(SpeciesPickerScreen(self.config, self.preset, self.args, id="picker"))


SAVE_FILE = "emoji_zoo_save.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Emoji Zoo -- a terminal emoji ecosystem simulation")
    parser.add_argument("--seed", type=int, default=None, help="random seed for reproducible runs")
    parser.add_argument("--width", type=int, default=None, help="grid width (default: auto from terminal)")
    parser.add_argument("--height", type=int, default=None, help="grid height (default: auto from terminal)")
    parser.add_argument("--speed", type=int, default=1, help="initial speed multiplier (default 1)")
    parser.add_argument("--no-picker", action="store_true", help="skip species picker, use all species")
    parser.add_argument("--preset", choices=list(PRESETS.keys()), default="balanced", help="ecosystem preset")
    parser.add_argument("--save-file", default=SAVE_FILE, help="save/load file path")
    parser.add_argument("--load", action="store_true", help="load saved ecosystem on startup")
    parser.add_argument("--debug", action="store_true", help="enable debug logging")
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
    app = ZooApp(config, args.preset, args)
    app.run()


if __name__ == "__main__":
    main()
