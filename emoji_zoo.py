#!/usr/bin/env python3
"""emoji_zoo -- Conway's Game of Life meets a living, breathing emoji ecosystem.

Plants grow and spread. Herbivores graze and flee predators.
Carnivores hunt. Energy drives reproduction and death.
Watch population cycles emerge from simple rules.

Controls:
  SPACE  pause / resume
  + / -  speed up / slow down
  r      reset the ecosystem
  1      drop 5 plants at random spots
  2      drop 5 herbivores at random spots
  3      drop 3 carnivores at random spots
  g      god mode (cursor placement: arrows move, 1/2/3 place, x delete, ESC exit)
  q      quit
"""

import random
import sys
import time
import select
import termios
import tty
import shutil
from dataclasses import dataclass
from enum import Enum

# -- Tunable parameters ---------------------------------------------------

PLANT_SPREAD_CHANCE = 0.18
PLANT_MAX_GROWTH = 3
PLANT_SEED_COUNT = 2

HERB_START_ENERGY = 14
HERB_EAT_ENERGY = 8
HERB_REPRO_THRESHOLD = 30
HERB_REPRO_COST = 14
HERB_VISION = 4
HERB_FLEE_VISION = 2
HERB_MAX_ENERGY = 35

CARN_START_ENERGY = 22
CARN_EAT_ENERGY = 10
CARN_REPRO_THRESHOLD = 34
CARN_REPRO_COST = 16
CARN_VISION = 5
CARN_MAX_ENERGY = 45
CARN_SATIATION = 28
CARN_MAX_NEIGHBORS = 3
HERB_MAX_NEIGHBORS = 3

MIGRATE_HERB_THRESHOLD = 8
MIGRATE_HERB_CHANCE = 0.08
MIGRATE_HERB_GROUP = 3
MIGRATE_CARN_THRESHOLD = 2
MIGRATE_CARN_CHANCE = 0.03
PLANT_CAP_RATIO = 0.5

INIT_PLANT_RATIO = 0.08
INIT_HERB_RATIO = 0.03
INIT_CARN_RATIO = 0.005
WATER_RATIO = 0.04

DROP_PLANT_N = 5
DROP_HERB_N = 5
DROP_CARN_N = 3

# -- Emoji palettes -------------------------------------------------------

PLANT_STAGES = ["🌱", "🌿", "🍀", "🌾"]

ALL_HERBIVORES = [
    ("🐰", "1"), ("🐑", "2"), ("🦌", "3"), ("🐄", "4"),
    ("🐐", "5"), ("🐇", "6"), ("🐷", "7"), ("🐎", "8"),
]
ALL_CARNIVORES = [
    ("🦁", "q"), ("🐺", "w"), ("🦊", "e"), ("🐻", "r"),
    ("🐯", "t"), ("🦅", "y"), ("🐍", "u"), ("🐊", "i"),
]

WATER_EMOJI = "🌊"
EMPTY_STR = "  "
SPARK_CHARS = "\u2581\u2582\u2583\u2584\u2585\u2586\u2587\u2588"

SELECTED_HERBS = [e for e, _ in ALL_HERBIVORES]
SELECTED_CARNS = [e for e, _ in ALL_CARNIVORES]

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


class Grid:
    def __init__(self, w, h):
        self.w = w
        self.h = h
        self.cells = [[None] * w for _ in range(h)]

    def get(self, x, y):
        if 0 <= x < self.w and 0 <= y < self.h:
            return self.cells[y][x]
        return None

    def neighbors(self, x, y):
        out = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if 0 <= nx < self.w and 0 <= ny < self.h:
                    out.append((nx, ny))
        return out

    def empty_neighbors(self, x, y):
        return [(nx, ny) for nx, ny in self.neighbors(x, y) if self.cells[ny][nx] is None]

    def random_empty(self, tries=200):
        for _ in range(tries):
            x, y = random.randint(0, self.w - 1), random.randint(0, self.h - 1)
            if self.cells[y][x] is None:
                return (x, y)
        return None


# -- Helpers --------------------------------------------------------------


def sign(n):
    return (n > 0) - (n < 0)


def find_nearest(grid, x, y, kind, vision):
    best = None
    best_d = 999
    for dy in range(-vision, vision + 1):
        for dx in range(-vision, vision + 1):
            if dx == 0 and dy == 0:
                continue
            nx, ny = x + dx, y + dy
            c = grid.get(nx, ny)
            if c and c.kind == kind:
                d = abs(dx) + abs(dy)
                if d < best_d:
                    best_d = d
                    best = (nx, ny)
    return best


def try_move(grid, x, y, e, nx, ny):
    if 0 <= nx < grid.w and 0 <= ny < grid.h and grid.cells[ny][nx] is None:
        grid.cells[y][x] = None
        grid.cells[ny][nx] = e
        return True
    return False


def sparkline(values, max_val):
    if max_val <= 0:
        return SPARK_CHARS[0] * len(values)
    return "".join(
        SPARK_CHARS[min(7, max(0, int(v / max_val * 7.999)))] for v in values
    )


def make_plant():
    g = random.randint(0, PLANT_MAX_GROWTH)
    return Entity(Kind.PLANT, PLANT_STAGES[g], 0, growth=g)


def make_herb():
    return Entity(Kind.HERBIVORE, random.choice(SELECTED_HERBS), HERB_START_ENERGY)


def make_carn():
    return Entity(Kind.CARNIVORE, random.choice(SELECTED_CARNS), CARN_START_ENERGY)


def drop_creatures(grid, factory, n):
    for _ in range(n):
        spot = grid.random_empty()
        if spot:
            x, y = spot
            grid.cells[y][x] = factory()


# -- Simulation step ------------------------------------------------------


def step(grid):
    entities = []
    for y in range(grid.h):
        for x in range(grid.w):
            e = grid.cells[y][x]
            if e and e.kind in (Kind.PLANT, Kind.HERBIVORE, Kind.CARNIVORE):
                entities.append((x, y, e))
    random.shuffle(entities)

    births = []

    for x, y, e in entities:
        if grid.cells[y][x] is not e:
            continue
        e.age += 1
        if e.kind == Kind.PLANT:
            _tick_plant(grid, x, y, e, births)
        elif e.kind == Kind.HERBIVORE:
            _tick_herb(grid, x, y, e, births)
        elif e.kind == Kind.CARNIVORE:
            _tick_carn(grid, x, y, e, births)

    for bx, by, be in births:
        if grid.cells[by][bx] is None:
            grid.cells[by][bx] = be

    plant_n = sum(1 for row in grid.cells for c in row if c and c.kind == Kind.PLANT)
    if plant_n < grid.w * grid.h * PLANT_CAP_RATIO:
        for _ in range(PLANT_SEED_COUNT):
            spot = grid.random_empty(50)
            if spot:
                x, y = spot
                grid.cells[y][x] = make_plant()

    if SELECTED_HERBS:
        herb_n = sum(1 for row in grid.cells for c in row if c and c.kind == Kind.HERBIVORE)
        if herb_n < MIGRATE_HERB_THRESHOLD and random.random() < MIGRATE_HERB_CHANCE:
            for _ in range(MIGRATE_HERB_GROUP):
                spot = grid.random_empty()
                if spot:
                    x, y = spot
                    grid.cells[y][x] = make_herb()

    if SELECTED_CARNS:
        carn_n = sum(1 for row in grid.cells for c in row if c and c.kind == Kind.CARNIVORE)
        if carn_n < MIGRATE_CARN_THRESHOLD and random.random() < MIGRATE_CARN_CHANCE:
            spot = grid.random_empty()
            if spot:
                x, y = spot
                grid.cells[y][x] = make_carn()


def _tick_plant(grid, x, y, e, births):
    if e.growth < PLANT_MAX_GROWTH:
        e.growth += 1
        e.emoji = PLANT_STAGES[e.growth]
    if random.random() < PLANT_SPREAD_CHANCE:
        empties = grid.empty_neighbors(x, y)
        if empties:
            nx, ny = random.choice(empties)
            births.append((nx, ny, Entity(Kind.PLANT, PLANT_STAGES[0], 0, growth=0)))


def _tick_herb(grid, x, y, e, births):
    e.energy -= 1

    threat = find_nearest(grid, x, y, Kind.CARNIVORE, HERB_FLEE_VISION)
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
            e.energy = min(e.energy + HERB_EAT_ENERGY + plant.growth * 3, HERB_MAX_ENERGY)
            grid.cells[ay][ax] = None
        else:
            food = find_nearest(grid, x, y, Kind.PLANT, HERB_VISION)
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

    if SELECTED_HERBS and e.energy >= HERB_REPRO_THRESHOLD:
        herb_count = sum(
            1 for nx, ny in grid.neighbors(x, y)
            if grid.cells[ny][nx] and grid.cells[ny][nx].kind == Kind.HERBIVORE
        )
        if herb_count < HERB_MAX_NEIGHBORS:
            empties = grid.empty_neighbors(x, y)
            if empties:
                nx, ny = random.choice(empties)
                e.energy -= HERB_REPRO_COST
                births.append((nx, ny, make_herb()))

    if e.energy <= 0:
        grid.cells[y][x] = None


def _tick_carn(grid, x, y, e, births):
    if e.age % 2 == 0:
        e.energy -= 1

    adjacent_prey = None
    if e.energy < CARN_SATIATION:
        for ax, ay in grid.neighbors(x, y):
            c = grid.cells[ay][ax]
            if c and c.kind == Kind.HERBIVORE:
                adjacent_prey = (ax, ay, c)
                break
    if adjacent_prey:
        ax, ay, prey = adjacent_prey
        e.energy = min(e.energy + CARN_EAT_ENERGY, CARN_MAX_ENERGY)
        grid.cells[ay][ax] = None
    else:
        prey = find_nearest(grid, x, y, Kind.HERBIVORE, CARN_VISION)
        if prey:
            px, py = prey
            nx, ny = x + sign(px - x), y + sign(py - y)
            if try_move(grid, x, y, e, nx, ny):
                x, y = nx, ny
                if e.energy < CARN_SATIATION:
                    for ax, ay in grid.neighbors(x, y):
                        c = grid.cells[ay][ax]
                        if c and c.kind == Kind.HERBIVORE:
                            e.energy = min(e.energy + CARN_EAT_ENERGY, CARN_MAX_ENERGY)
                            grid.cells[ay][ax] = None
                            break
        else:
            empties = grid.empty_neighbors(x, y)
            if empties:
                nx, ny = random.choice(empties)
                if try_move(grid, x, y, e, nx, ny):
                    x, y = nx, ny

    if SELECTED_CARNS and e.energy >= CARN_REPRO_THRESHOLD:
        carn_count = sum(
            1 for nx, ny in grid.neighbors(x, y)
            if grid.cells[ny][nx] and grid.cells[ny][nx].kind == Kind.CARNIVORE
        )
        if carn_count < CARN_MAX_NEIGHBORS:
            empties = grid.empty_neighbors(x, y)
            if empties:
                nx, ny = random.choice(empties)
                e.energy -= CARN_REPRO_COST
                births.append((nx, ny, make_carn()))

    if e.energy <= 0:
        grid.cells[y][x] = None


# -- Setup ----------------------------------------------------------------


def _place_water(grid, n_water):
    seeds = max(1, n_water // 6)
    placed = 0
    for _ in range(seeds):
        x = random.randint(0, grid.w - 1)
        y = random.randint(0, grid.h - 1)
        if grid.cells[y][x] is None:
            grid.cells[y][x] = Entity(Kind.WATER, WATER_EMOJI, 0)
            placed += 1
        cluster_size = random.randint(2, 7)
        cx, cy = x, y
        for _ in range(cluster_size):
            dx, dy = random.choice([(-1, 0), (1, 0), (0, -1), (0, 1)])
            cx, cy = cx + dx, cy + dy
            if 0 <= cx < grid.w and 0 <= cy < grid.h and grid.cells[cy][cx] is None:
                grid.cells[cy][cx] = Entity(Kind.WATER, WATER_EMOJI, 0)
                placed += 1
        if placed >= n_water:
            break


def populate(grid):
    total = grid.w * grid.h
    n_water = int(total * WATER_RATIO)
    n_plants = int(total * INIT_PLANT_RATIO)
    n_herbs = int(total * INIT_HERB_RATIO) if SELECTED_HERBS else 0
    n_carns = int(total * INIT_CARN_RATIO) if SELECTED_CARNS else 0

    _place_water(grid, n_water)

    def fill(n, factory):
        for _ in range(n):
            for _ in range(200):
                x, y = random.randint(0, grid.w - 1), random.randint(0, grid.h - 1)
                if grid.cells[y][x] is None:
                    grid.cells[y][x] = factory()
                    break

    fill(n_plants, make_plant)
    fill(n_herbs, make_herb)
    fill(n_carns, make_carn)


# -- Species picker -------------------------------------------------------


def _render_picker(herb_on, carn_on):
    lines = []
    lines.append("\033[H  Emoji Zoo  --  Choose your animals\033[K")
    lines.append("  Toggle species on/off, then press Enter to start.\033[K")
    lines.append("\033[K")

    lines.append("  HERBIVORES\033[K")
    for emoji, key in ALL_HERBIVORES:
        mark = "\033[32m\xe2\x9c\x93\033[0m" if herb_on.get(emoji, True) else "\033[31m\xe2\x9c\x97\033[0m"
        lines.append(f"    {key}) {emoji}  [{mark}]\033[K")
    lines.append("\033[K")

    lines.append("  CARNIVORES\033[K")
    for emoji, key in ALL_CARNIVORES:
        mark = "\033[32m\xe2\x9c\x93\033[0m" if carn_on.get(emoji, True) else "\033[31m\xe2\x9c\x97\033[0m"
        lines.append(f"    {key}) {emoji}  [{mark}]\033[K")
    lines.append("\033[K")

    n_h = sum(herb_on.values())
    n_c = sum(carn_on.values())
    lines.append(f"  {n_h} herbivore(s), {n_c} carnivore(s) selected\033[K")
    lines.append("  a = all on  n = all off  Enter = start\033[K")

    sys.stdout.write("\n".join(lines) + "\033[J")
    sys.stdout.flush()


def species_picker():
    global SELECTED_HERBS, SELECTED_CARNS

    herb_on = {e: True for e, _ in ALL_HERBIVORES}
    carn_on = {e: True for e, _ in ALL_CARNIVORES}

    herb_keys = {k: e for e, k in ALL_HERBIVORES}
    carn_keys = {k: e for e, k in ALL_CARNIVORES}

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
            if ch == "\r" or ch == "\n":
                break
            elif ch == "a":
                herb_on = {e: True for e, _ in ALL_HERBIVORES}
                carn_on = {e: True for e, _ in ALL_CARNIVORES}
            elif ch == "n":
                herb_on = {e: False for e, _ in ALL_HERBIVORES}
                carn_on = {e: False for e, _ in ALL_CARNIVORES}
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

    SELECTED_HERBS = [e for e, _ in ALL_HERBIVORES if herb_on[e]]
    SELECTED_CARNS = [e for e, _ in ALL_CARNIVORES if carn_on[e]]

    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()


# -- Render ---------------------------------------------------------------


def count_pop(grid):
    counts = {Kind.PLANT: 0, Kind.HERBIVORE: 0, Kind.CARNIVORE: 0, Kind.WATER: 0}
    for y in range(grid.h):
        for x in range(grid.w):
            e = grid.cells[y][x]
            if e:
                counts[e.kind] = counts.get(e.kind, 0) + 1
    return counts


def render(grid, tick, paused, speed, hist, god_mode=False, cursor=(0, 0)):
    counts = count_pop(grid)
    p = counts[Kind.PLANT]
    h = counts[Kind.HERBIVORE]
    c = counts[Kind.CARNIVORE]

    cx, cy = cursor
    if god_mode:
        status = "** GOD MODE **  arrows=move  1=plant  2=herb  3=carn  x=delete  ESC=exit"
    elif paused:
        status = "PAUSED"
    else:
        status = "running"
    lines = []
    lines.append(f"\033[H  Emoji Zoo  --  tick {tick:>5}  speed {speed}x  [{status}]\033[K")
    lines.append("\033[K")

    for y in range(grid.h):
        row = ""
        for x in range(grid.w):
            e = grid.cells[y][x]
            content = e.emoji if e else EMPTY_STR
            if god_mode and x == cx and y == cy:
                row += f"\033[44m{content}\033[0m"
            else:
                row += content
        lines.append(row + "\033[K")

    lines.append("\033[K")

    hist_max = max(
        max(hist["plant"]) if hist["plant"] else 1,
        max(hist["herb"]) if hist["herb"] else 1,
        max(hist["carn"]) if hist["carn"] else 1,
        1,
    )

    sp = sparkline(hist["plant"][-50:], hist_max)
    sh = sparkline(hist["herb"][-50:], hist_max)
    sc = sparkline(hist["carn"][-50:], hist_max)

    lines.append(f"  plants      {p:>4}  {sp}\033[K")
    lines.append(f"  herbivores  {h:>4}  {sh}\033[K")
    lines.append(f"  carnivores  {c:>4}  {sc}\033[K")
    lines.append("\033[K")
    lines.append("  SPACE pause  +/- speed  r reset  1/2/3 drop  g god mode  q quit\033[K")

    sys.stdout.write("\n".join(lines))
    sys.stdout.flush()


# -- Input ----------------------------------------------------------------


def get_key():
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
                arrows = {"A": "UP", "B": "DOWN", "C": "RIGHT", "D": "LEFT", "H": "UP", "F": "DOWN"}
                return arrows.get(ch3, ch3)
            return "ESC"
        return ch2
    return ch


# -- Main -----------------------------------------------------------------


def main():
    global SELECTED_HERBS, SELECTED_CARNS

    if not sys.stdin.isatty():
        print("Run this in a terminal, not a pipe.")
        sys.exit(1)

    ts = shutil.get_terminal_size()
    gw = min(60, max(20, (ts.columns - 2) // 2))
    gh = min(35, max(10, ts.lines - 10))

    if gw < 20 or gh < 10:
        print("Terminal too small. Need at least ~42 columns and ~20 lines.")
        sys.exit(1)

    species_picker()

    grid = Grid(gw, gh)
    populate(grid)

    tick = 0
    paused = False
    speed = 1
    base_delay = 0.15
    hist = {"plant": [], "herb": [], "carn": []}
    god_mode = False
    cursor = [gw // 2, gh // 2]

    old = termios.tcgetattr(sys.stdin)
    tty.setcbreak(sys.stdin.fileno())
    sys.stdout.write("\033[?25l\033[2J")

    try:
        while True:
            key = get_key()

            if god_mode:
                if key in ("q", "\x03"):
                    break
                elif key == "ESC" or key == "g":
                    god_mode = False
                elif key == "UP":
                    cursor[1] = max(0, cursor[1] - 1)
                elif key == "DOWN":
                    cursor[1] = min(gh - 1, cursor[1] + 1)
                elif key == "LEFT":
                    cursor[0] = max(0, cursor[0] - 1)
                elif key == "RIGHT":
                    cursor[0] = min(gw - 1, cursor[0] + 1)
                elif key == "1":
                    cx, cy = cursor
                    if grid.cells[cy][cx] is None:
                        grid.cells[cy][cx] = make_plant()
                elif key == "2" and SELECTED_HERBS:
                    cx, cy = cursor
                    if grid.cells[cy][cx] is None:
                        grid.cells[cy][cx] = make_herb()
                elif key == "3" and SELECTED_CARNS:
                    cx, cy = cursor
                    if grid.cells[cy][cx] is None:
                        grid.cells[cy][cx] = make_carn()
                elif key == "x":
                    cx, cy = cursor
                    if grid.cells[cy][cx] and grid.cells[cy][cx].kind != Kind.WATER:
                        grid.cells[cy][cx] = None
                elif key == " ":
                    paused = not paused
                elif key in ("+", "="):
                    speed = min(10, speed + 1)
                elif key == "-":
                    speed = max(1, speed - 1)
                elif key == "r":
                    grid = Grid(gw, gh)
                    populate(grid)
                    tick = 0
                    hist = {"plant": [], "herb": [], "carn": []}
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
                    grid = Grid(gw, gh)
                    populate(grid)
                    tick = 0
                    hist = {"plant": [], "herb": [], "carn": []}
                elif key == "1":
                    drop_creatures(grid, make_plant, DROP_PLANT_N)
                elif key == "2" and SELECTED_HERBS:
                    drop_creatures(grid, make_herb, DROP_HERB_N)
                elif key == "3" and SELECTED_CARNS:
                    drop_creatures(grid, make_carn, DROP_CARN_N)
                elif key == "g":
                    god_mode = True
                    cursor = [gw // 2, gh // 2]

            if not paused:
                step(grid)
                tick += 1
                c = count_pop(grid)
                hist["plant"].append(c[Kind.PLANT])
                hist["herb"].append(c[Kind.HERBIVORE])
                hist["carn"].append(c[Kind.CARNIVORE])
                for k in hist:
                    if len(hist[k]) > 200:
                        hist[k] = hist[k][-200:]

            render(grid, tick, paused, speed, hist, god_mode, cursor)
            time.sleep(base_delay / speed)
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old)
        sys.stdout.write("\033[0m\033[?25h\033[2J\033[H")
        sys.stdout.flush()
        print("Emoji Zoo closed. Thanks for visiting!")


if __name__ == "__main__":
    main()
