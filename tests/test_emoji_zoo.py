"""Tests for emoji_zoo simulation, model, helpers, and new mechanics."""

import json
import os
import random
import tempfile

import pytest

from emoji_zoo import (
    Config, Entity, Grid, GameState, Kind, SpeciesTraits, Stats,
    HERBIVORE_TRAITS, CARNIVORE_TRAITS, PRESETS,
    ALL_HERBIVORES, ALL_CARNIVORES, EMOJI_TO_SPECIES,
    make_config, make_plant, make_herb, make_carn,
    make_herb_of_species, make_carn_of_species,
    make_event, species_of, sign, find_nearest, find_nearest_species,
    try_move, try_move_through_plants, sparkline,
    step, count_pop, count_by_species,
    populate, _place_water, drop_creatures,
    save_state, load_state,
    SEASON_NAMES, SEASON_PLANT_MOD, SEASON_ENERGY_MOD, SEASON_DIEOFF_CHANCE,
    event_to_message, _param_list, _adjust_param,
    get_traits,
)


# -- Fixtures --------------------------------------------------------------


@pytest.fixture
def small_grid():
    return Grid(10, 10)


@pytest.fixture
def config():
    return make_config("balanced")


@pytest.fixture
def state(small_grid, config):
    herbs = [e for e, _, _ in ALL_HERBIVORES]
    carns = [e for e, _, _ in ALL_CARNIVORES]
    return GameState(
        grid=small_grid, config=config,
        selected_herbs=herbs, selected_carns=carns,
    )


@pytest.fixture
def seeded_random():
    random.seed(42)


# -- Grid tests ------------------------------------------------------------


class TestGrid:
    def test_get_in_bounds(self, small_grid):
        assert small_grid.get(0, 0) is None
        assert small_grid.get(9, 9) is None

    def test_get_out_of_bounds(self, small_grid):
        assert small_grid.get(-1, 0) is None
        assert small_grid.get(0, -1) is None
        assert small_grid.get(10, 0) is None
        assert small_grid.get(0, 10) is None

    def test_set_and_get(self, small_grid):
        e = make_plant()
        small_grid.cells[0][0] = e
        assert small_grid.get(0, 0) is e

    def test_neighbors_center(self, small_grid):
        neighbors = small_grid.neighbors(5, 5)
        assert len(neighbors) == 8

    def test_neighbors_corner(self, small_grid):
        neighbors = small_grid.neighbors(0, 0)
        assert len(neighbors) == 3
        assert (0, 1) in neighbors
        assert (1, 0) in neighbors
        assert (1, 1) in neighbors

    def test_empty_neighbors(self, small_grid):
        empties = small_grid.empty_neighbors(5, 5)
        assert len(empties) == 8

    def test_empty_neighbors_with_entity(self, small_grid):
        small_grid.cells[4][5] = make_plant()
        empties = small_grid.empty_neighbors(5, 5)
        assert (5, 4) not in empties
        assert len(empties) == 7

    def test_passable_neighbors_empty(self, small_grid):
        passables = small_grid.passable_neighbors(5, 5)
        assert len(passables) == 8

    def test_passable_neighbors_with_plant(self, small_grid):
        small_grid.cells[5][4] = make_plant()
        passables = small_grid.passable_neighbors(5, 5)
        assert (4, 5) in passables

    def test_passable_neighbors_with_water(self, small_grid):
        small_grid.cells[5][4] = Entity(Kind.WATER, "\U0001F30A", 0)
        passables = small_grid.passable_neighbors(5, 5)
        assert (4, 5) not in passables

    def test_random_empty_found(self, small_grid):
        spot = small_grid.random_empty()
        assert spot is not None
        x, y = spot
        assert small_grid.cells[y][x] is None

    def test_random_empty_full_grid(self, small_grid):
        for y in range(10):
            for x in range(10):
                small_grid.cells[y][x] = make_plant()
        assert small_grid.random_empty(tries=5) is None

    def test_add_nutrients(self, small_grid):
        small_grid.add_nutrients(5, 5, 10.0)
        assert small_grid.nutrients[5][5] == 10.0

    def test_add_nutrients_out_of_bounds(self, small_grid):
        small_grid.add_nutrients(-1, 0, 10.0)
        small_grid.add_nutrients(10, 0, 10.0)
        assert all(all(v == 0.0 for v in row) for row in small_grid.nutrients)

    def test_decay_nutrients(self, small_grid):
        small_grid.add_nutrients(5, 5, 10.0)
        small_grid.decay_nutrients(0.5)
        assert small_grid.nutrients[5][5] == 5.0

    def test_decay_nutrients_all_cells(self, small_grid):
        small_grid.add_nutrients(0, 0, 10.0)
        small_grid.add_nutrients(9, 9, 20.0)
        small_grid.decay_nutrients(0.9)
        assert abs(small_grid.nutrients[0][0] - 9.0) < 0.01
        assert abs(small_grid.nutrients[9][9] - 18.0) < 0.01


# -- Helper tests ----------------------------------------------------------


class TestSign:
    def test_positive(self):
        assert sign(5) == 1

    def test_negative(self):
        assert sign(-5) == -1

    def test_zero(self):
        assert sign(0) == 0


class TestFindNearest:
    def test_finds_adjacent(self, small_grid):
        small_grid.cells[5][6] = make_plant()
        result = find_nearest(small_grid, 5, 5, Kind.PLANT, 3)
        assert result == (6, 5)

    def test_finds_nearest_not_furthest(self, small_grid):
        small_grid.cells[5][8] = make_plant()
        small_grid.cells[5][6] = make_plant()
        result = find_nearest(small_grid, 5, 5, Kind.PLANT, 5)
        assert result == (6, 5)

    def test_none_when_nothing_in_range(self, small_grid):
        small_grid.cells[0][0] = make_plant()
        result = find_nearest(small_grid, 5, 5, Kind.PLANT, 2)
        assert result is None

    def test_finds_herbivore(self, small_grid):
        herbs = [e for e, _, _ in ALL_HERBIVORES]
        e = make_herb(herbs)
        small_grid.cells[7][5] = e
        result = find_nearest(small_grid, 5, 5, Kind.HERBIVORE, 5)
        assert result == (5, 7)


class TestFindNearestSpecies:
    def test_finds_same_species(self, small_grid):
        herbs = [e for e, _, _ in ALL_HERBIVORES]
        e = make_herb(herbs)
        small_grid.cells[6][5] = e
        result = find_nearest_species(small_grid, 5, 5, Kind.HERBIVORE, e.species, 5)
        assert result == (5, 6)

    def test_ignores_different_species(self, small_grid):
        e1 = make_herb([ALL_HERBIVORES[0][0]])
        e2 = make_herb([ALL_HERBIVORES[1][0]])
        assert e1.species != e2.species
        small_grid.cells[6][5] = e2
        result = find_nearest_species(small_grid, 5, 5, Kind.HERBIVORE, e1.species, 5)
        assert result is None


class TestTryMove:
    def test_move_to_empty(self, small_grid):
        e = make_plant()
        small_grid.cells[5][5] = e
        assert try_move(small_grid, 5, 5, e, 6, 5)
        assert small_grid.cells[5][5] is None
        assert small_grid.cells[5][6] is e

    def test_move_to_occupied_fails(self, small_grid):
        e1 = make_plant()
        e2 = make_plant()
        small_grid.cells[5][5] = e1
        small_grid.cells[5][6] = e2
        assert not try_move(small_grid, 5, 5, e1, 6, 5)
        assert small_grid.cells[5][5] is e1

    def test_move_out_of_bounds_fails(self, small_grid):
        e = make_plant()
        small_grid.cells[0][0] = e
        assert not try_move(small_grid, 0, 0, e, -1, 0)


class TestTryMoveThroughPlants:
    def test_move_to_empty(self, small_grid):
        e = make_herb([ALL_HERBIVORES[0][0]])
        small_grid.cells[5][5] = e
        assert try_move_through_plants(small_grid, 5, 5, e, 6, 5)

    def test_move_through_plant(self, small_grid):
        e = make_carn([ALL_CARNIVORES[0][0]])
        plant = make_plant()
        small_grid.cells[5][5] = e
        small_grid.cells[5][6] = plant
        assert try_move_through_plants(small_grid, 5, 5, e, 6, 5)
        assert small_grid.cells[5][5] is None
        assert small_grid.cells[5][6] is e

    def test_blocked_by_water(self, small_grid):
        e = make_carn([ALL_CARNIVORES[0][0]])
        water = Entity(Kind.WATER, "\U0001F30A", 0)
        small_grid.cells[5][5] = e
        small_grid.cells[5][6] = water
        assert not try_move_through_plants(small_grid, 5, 5, e, 6, 5)


class TestSparkline:
    def test_empty(self):
        assert sparkline([], 10) == ""

    def test_zero_max(self):
        result = sparkline([0, 0, 0], 0)
        assert all(c == "\u2581" for c in result)

    def test_full(self):
        result = sparkline([10, 10, 10], 10)
        assert all(c == "\u2588" for c in result)

    def test_mixed(self):
        result = sparkline([0, 5, 10], 10)
        assert result[0] == "\u2581"
        assert result[2] == "\u2588"

    def test_length(self):
        assert len(sparkline([1, 2, 3, 4, 5], 5)) == 5


class TestSpeciesOf:
    def test_known_emoji(self):
        assert species_of("\U0001F430") == "rabbit"
        assert species_of("\U0001F981") == "lion"

    def test_unknown_emoji(self):
        assert species_of("?") == "animal"


# -- Config tests ----------------------------------------------------------


class TestConfig:
    def test_default_config(self):
        cfg = Config()
        assert cfg.plant_spread_chance == 0.06
        assert cfg.season_length == 50
        assert cfg.disease_chance == 0.002

    def test_make_config_default(self):
        cfg = make_config()
        assert cfg.plant_spread_chance == 0.06

    def test_make_config_preset(self):
        cfg = make_config("desert")
        assert cfg.init_plant_ratio == 0.02
        assert cfg.water_ratio == 0.08

    def test_make_config_preset_paradise(self):
        cfg = make_config("paradise")
        assert cfg.init_plant_ratio == 0.12
        assert cfg.disease_chance == 0.0

    def test_make_config_preset_chaos(self):
        cfg = make_config("chaos")
        assert cfg.season_length == 25

    def test_make_config_overrides(self):
        cfg = make_config(plant_spread_chance=0.5)
        assert cfg.plant_spread_chance == 0.5

    def test_make_config_preset_and_overrides(self):
        cfg = make_config("desert", water_ratio=0.10)
        assert cfg.init_plant_ratio == 0.02
        assert cfg.water_ratio == 0.10

    def test_all_presets_valid(self):
        for name in PRESETS:
            cfg = make_config(name)
            assert isinstance(cfg, Config)


# -- Species traits tests --------------------------------------------------


class TestSpeciesTraits:
    def test_all_herbivores_have_traits(self):
        for _, _, species in ALL_HERBIVORES:
            assert species in HERBIVORE_TRAITS, f"Missing traits for {species}"

    def test_all_carnivores_have_traits(self):
        for _, _, species in ALL_CARNIVORES:
            assert species in CARNIVORE_TRAITS, f"Missing traits for {species}"

    def test_traits_are_varied_herbivores(self):
        visions = {t.vision for t in HERBIVORE_TRAITS.values()}
        assert len(visions) > 1, "All herbivores have same vision"

        max_ages = {t.max_age for t in HERBIVORE_TRAITS.values()}
        assert len(max_ages) > 1, "All herbivores have same max_age"

        repro_thresholds = {t.repro_threshold for t in HERBIVORE_TRAITS.values()}
        assert len(repro_thresholds) > 1, "All herbivores have same repro_threshold"

    def test_traits_are_varied_carnivores(self):
        visions = {t.vision for t in CARNIVORE_TRAITS.values()}
        assert len(visions) > 1, "All carnivores have same vision"

        max_ages = {t.max_age for t in CARNIVORE_TRAITS.values()}
        assert len(max_ages) > 1, "All carnivores have same max_age"

    def test_some_carns_can_hunt_carns(self):
        can_hunt = [t.can_hunt_carns for t in CARNIVORE_TRAITS.values()]
        assert any(can_hunt), "No carnivore can hunt other carnivores"
        assert not all(can_hunt), "All carnivores can hunt carns (should be selective)"

    def test_all_traits_have_colors(self):
        for t in HERBIVORE_TRAITS.values():
            assert t.color != "", "Herbivore trait missing color"
        for t in CARNIVORE_TRAITS.values():
            assert t.color != "", "Carnivore trait missing color"

    def test_get_traits_herbivore(self):
        t = get_traits("herbivore", "rabbit")
        assert t.vision == 4
        assert t.max_age == 80

    def test_get_traits_carnivore(self):
        t = get_traits("carnivore", "eagle")
        assert t.vision == 9

    def test_get_traits_unknown(self):
        t = get_traits("herbivore", "nonexistent")
        assert t.vision == 5

    def test_rabbit_breeds_faster_than_cow(self):
        rabbit = HERBIVORE_TRAITS["rabbit"]
        cow = HERBIVORE_TRAITS["cow"]
        assert rabbit.repro_threshold < cow.repro_threshold
        assert rabbit.repro_cost < cow.repro_cost

    def test_eagle_has_highest_vision(self):
        eagle = CARNIVORE_TRAITS["eagle"]
        for t in CARNIVORE_TRAITS.values():
            assert t.vision <= eagle.vision

    def test_bunny_has_shortest_lifespan(self):
        bunny = HERBIVORE_TRAITS["bunny"]
        for t in HERBIVORE_TRAITS.values():
            assert t.max_age >= bunny.max_age

    def test_pack_bonus_varies(self):
        bonuses = {t.pack_bonus for t in HERBIVORE_TRAITS.values()}
        assert len(bonuses) > 1


# -- Entity factory tests --------------------------------------------------


class TestEntityFactories:
    def test_make_plant(self):
        e = make_plant()
        assert e.kind == Kind.PLANT
        assert e.growth >= 0
        assert e.energy == 0

    def test_make_herb_has_traits(self):
        herbs = [ALL_HERBIVORES[0][0]]
        e = make_herb(herbs)
        assert e is not None
        assert e.kind == Kind.HERBIVORE
        assert e.traits is not None
        assert e.species == "rabbit"
        assert e.energy == e.traits.start_energy

    def test_make_carn_has_traits(self):
        carns = [ALL_CARNIVORES[0][0]]
        e = make_carn(carns)
        assert e is not None
        assert e.kind == Kind.CARNIVORE
        assert e.traits is not None
        assert e.species == "lion"
        assert e.energy == e.traits.start_energy

    def test_make_herb_empty_returns_none(self):
        assert make_herb([]) is None

    def test_make_carn_empty_returns_none(self):
        assert make_carn([]) is None

    def test_make_herb_has_name(self):
        herbs = [e for e, _, _ in ALL_HERBIVORES]
        e = make_herb(herbs)
        assert e is not None
        assert e.name is not None
        assert len(e.name) > 0

    def test_make_herb_has_thirst_zero(self):
        herbs = [ALL_HERBIVORES[0][0]]
        e = make_herb(herbs)
        assert e.thirst == 0

    def test_make_herb_not_diseased(self):
        herbs = [ALL_HERBIVORES[0][0]]
        e = make_herb(herbs)
        assert not e.is_diseased


# -- Statistics tests ------------------------------------------------------


class TestStats:
    def test_initial_stats(self):
        s = Stats()
        assert s.total_births == 0
        assert s.total_kills == 0
        assert s.avg_lifespan == 0.0

    def test_record_death_starve(self):
        s = Stats()
        s.record_death(10, "starve")
        assert s.total_starvations == 1
        assert s.death_ages == [10]

    def test_record_death_age(self):
        s = Stats()
        s.record_death(200, "age")
        assert s.total_deaths_age == 1

    def test_record_death_disease(self):
        s = Stats()
        s.record_death(50, "disease")
        assert s.total_deaths_disease == 1

    def test_record_death_kill(self):
        s = Stats()
        s.record_death(30, "kill")
        assert s.total_kills == 1

    def test_avg_lifespan(self):
        s = Stats()
        s.record_death(10, "starve")
        s.record_death(20, "age")
        s.record_death(30, "kill")
        assert s.avg_lifespan == 20.0

    def test_total_deaths(self):
        s = Stats()
        s.record_death(10, "starve")
        s.record_death(20, "age")
        s.record_death(30, "disease")
        s.record_death(40, "kill")
        assert s.total_deaths == 4

    def test_update_peaks(self):
        s = Stats()
        s.update_peaks(10, 5, 2)
        s.update_peaks(8, 7, 3)
        s.update_peaks(12, 4, 1)
        assert s.peak_plants == 12
        assert s.peak_herbs == 7
        assert s.peak_carns == 3


# -- Simulation step tests -------------------------------------------------


class TestSimulation:
    def test_step_increments_tick(self, state):
        initial_tick = state.tick
        step(state, [])
        assert state.tick == initial_tick + 1

    def test_step_records_history(self, state):
        step(state, [])
        assert len(state.hist["plant"]) == 1
        assert len(state.hist["herb"]) == 1
        assert len(state.hist["carn"]) == 1

    def test_step_advances_entity_age(self, state):
        e = make_plant()
        state.grid.cells[5][5] = e
        step(state, [])
        assert e.age == 1

    def test_herbivore_eats_adjacent_plant(self, state):
        state.grid = Grid(5, 5)
        herbs = [ALL_HERBIVORES[0][0]]
        herb = make_herb(herbs)
        plant = make_plant()
        state.grid.cells[2][2] = herb
        state.grid.cells[2][3] = plant
        initial_energy = herb.energy
        step(state, [])
        assert herb.energy >= initial_energy

    def test_herbivore_starves_without_food(self, state):
        state.grid = Grid(5, 5)
        herbs = [ALL_HERBIVORES[0][0]]
        herb = make_herb(herbs)
        herb.energy = 1
        state.grid.cells[2][2] = herb
        events = []
        step(state, events)
        starve_events = [e for e in events if e["kind"] == "starve"]
        assert len(starve_events) >= 1

    def test_carnivore_eats_adjacent_herbivore(self, state):
        state.grid = Grid(5, 5)
        carns = [ALL_CARNIVORES[0][0]]
        herbs = [ALL_HERBIVORES[0][0]]
        carn = make_carn(carns)
        carn.energy = 10
        herb = make_herb(herbs)
        state.grid.cells[2][2] = carn
        state.grid.cells[2][3] = herb
        events = []
        step(state, events)
        kill_events = [e for e in events if e["kind"] == "kill"]
        assert len(kill_events) >= 1

    def test_natural_aging_death(self, state):
        state.grid = Grid(5, 5)
        herbs = [ALL_HERBIVORES[0][0]]
        herb = make_herb(herbs)
        herb.age = herb.traits.max_age
        herb.energy = 100
        state.grid.cells[2][2] = herb
        events = []
        step(state, events)
        age_deaths = [e for e in events if e["kind"] == "age_death"]
        assert len(age_deaths) >= 1
        assert state.stats.total_deaths_age >= 1

    def test_disease_can_infect(self, state):
        state.grid = Grid(5, 5)
        herbs = [ALL_HERBIVORES[0][0]]
        herb = make_herb(herbs)
        herb.diseased = state.config.disease_duration
        herb.energy = 100
        state.grid.cells[2][2] = herb
        events = []
        step(state, events)
        assert herb.diseased < state.config.disease_duration

    def test_disease_spreads_to_neighbor(self, state):
        state.grid = Grid(4, 4)
        herbs = [ALL_HERBIVORES[0][0]]
        e1 = make_herb(herbs)
        e2 = make_herb(herbs)
        e1.diseased = state.config.disease_duration
        e1.energy = 100
        e2.energy = 100
        for y in range(4):
            for x in range(4):
                if (x, y) not in [(1, 1), (2, 1)]:
                    state.grid.cells[y][x] = Entity(
                        Kind.WATER, "\U0001F30A", 0, species="water")
        state.grid.cells[1][1] = e1
        state.grid.cells[1][2] = e2
        state.config.disease_spread_chance = 1.0
        events = []
        step(state, events)
        assert e2.diseased > 0

    def test_decomposition_adds_nutrients(self, state):
        state.grid = Grid(3, 3)
        herbs = [ALL_HERBIVORES[0][0]]
        herb = make_herb(herbs)
        herb.energy = 1
        state.grid.cells[1][1] = herb
        for nx, ny in state.grid.neighbors(1, 1):
            state.grid.cells[ny][nx] = Entity(Kind.WATER, "\U0001F30A", 0, species="water")
        step(state, [])
        total_nutrients = sum(
            state.grid.nutrients[y][x]
            for y in range(3) for x in range(3)
        )
        assert total_nutrients > 0

    def test_water_drinking_resets_thirst(self, state):
        state.grid = Grid(5, 5)
        herbs = [ALL_HERBIVORES[0][0]]
        herb = make_herb(herbs)
        herb.thirst = 20
        herb.energy = 100
        water = Entity(Kind.WATER, "\U0001F30A", 0, species="water")
        state.grid.cells[2][2] = herb
        state.grid.cells[2][3] = water
        step(state, [])
        assert herb.thirst == 0

    def test_thirst_increases_over_time(self, state):
        state.grid = Grid(5, 5)
        herbs = [ALL_HERBIVORES[0][0]]
        herb = make_herb(herbs)
        herb.energy = 100
        state.grid.cells[2][2] = herb
        initial_thirst = herb.thirst
        step(state, [])
        assert herb.thirst > initial_thirst

    def test_seasons_change(self, state):
        state.config.season_length = 5
        seasons_seen = set()
        for i in range(20):
            step(state, [])
            seasons_seen.add(state.season)
        assert state.season == ((state.tick - 1) // 5) % 4
        assert len(seasons_seen) >= 2

    def test_season_name_correct(self, state):
        state.config.season_length = 5
        state.tick = 0
        state.season = 0
        assert state.season_name == "Spring"
        state.tick = 5
        state.season = 1
        assert state.season_name == "Summer"

    def test_plant_cap_prevents_overgrowth(self, state):
        state.grid = Grid(10, 10)
        state.config.plant_cap_ratio = 0.1
        for _ in range(100):
            step(state, [])
        plant_count = count_pop(state.grid)[Kind.PLANT]
        assert plant_count <= 100 * 0.1 + 5

    def test_stats_track_births(self, state):
        state.grid = Grid(10, 10)
        herbs = [ALL_HERBIVORES[0][0]]
        herb = make_herb(herbs)
        herb.energy = 200
        state.grid.cells[5][5] = herb
        state.config.herb_repro_threshold = 10
        for _ in range(20):
            step(state, [])
        assert state.stats.total_births > 0

    def test_offspring_inherit_parent_species(self, state):
        state.grid = Grid(10, 10)
        rabbit_emoji = ALL_HERBIVORES[0][0]
        herb = make_herb([rabbit_emoji])
        assert herb.species == "rabbit"
        herb.energy = 500
        state.grid.cells[5][5] = herb
        state.config.herb_repro_threshold = 5
        for _ in range(30):
            step(state, [])
        herbs_after = count_by_species(state.grid, Kind.HERBIVORE)
        species_present = set(herbs_after.keys())
        assert "rabbit" in species_present, \
            f"Expected rabbits to survive, got {species_present}"
        assert species_present == {"rabbit"}, \
            f"Expected only rabbits, got {species_present}"

    def test_carn_offspring_inherit_parent_species(self, state):
        state.grid = Grid(10, 10)
        lion_emoji = ALL_CARNIVORES[0][0]
        carn = make_carn([lion_emoji])
        assert carn.species == "lion"
        carn.energy = 500
        state.grid.cells[5][5] = carn
        state.config.carn_repro_threshold = 5
        for _ in range(30):
            step(state, [])
        carns_after = count_by_species(state.grid, Kind.CARNIVORE)
        species_present = set(carns_after.keys())
        assert "lion" in species_present, \
            f"Expected lions to survive, got {species_present}"
        assert species_present == {"lion"}, \
            f"Expected only lions, got {species_present}"

    def test_make_herb_of_species(self):
        e = make_herb_of_species("rabbit")
        assert e is not None
        assert e.species == "rabbit"
        assert e.traits is not None
        assert e.traits.vision == 4

    def test_make_carn_of_species(self):
        e = make_carn_of_species("eagle")
        assert e is not None
        assert e.species == "eagle"
        assert e.traits is not None
        assert e.traits.vision == 9

    def test_make_herb_of_species_unknown(self):
        assert make_herb_of_species("nonexistent") is None

    def test_make_carn_of_species_unknown(self):
        assert make_carn_of_species("nonexistent") is None

    def test_stats_track_kills(self, state):
        state.grid = Grid(5, 5)
        carns = [ALL_CARNIVORES[0][0]]
        herbs = [ALL_HERBIVORES[0][0]]
        carn = make_carn(carns)
        carn.energy = 5
        herb = make_herb(herbs)
        state.grid.cells[2][2] = carn
        state.grid.cells[2][3] = herb
        events = []
        step(state, events)
        assert state.stats.total_kills >= 1

    def test_pack_bonus_lowers_repro_threshold(self, state):
        state.grid = Grid(5, 5)
        herbs = [ALL_HERBIVORES[0][0]]
        e1 = make_herb(herbs)
        e2 = make_herb(herbs)
        e1.energy = e1.traits.repro_threshold - 1
        e2.energy = 100
        state.grid.cells[2][2] = e1
        state.grid.cells[2][3] = e2
        if e1.traits.pack_bonus > 0:
            effective = e1.traits.repro_threshold * (
                1.0 - e1.traits.pack_bonus * 1)
            assert effective < e1.traits.repro_threshold

    def test_intra_carnivore_predation(self, state):
        state.grid = Grid(5, 5)
        bear_emoji = "\U0001F43B"
        snake_emoji = "\U0001F40D"
        bear = make_carn([bear_emoji])
        snake = make_carn([snake_emoji])
        bear.energy = 10
        snake.energy = 100
        assert bear.traits.can_hunt_carns
        assert bear.traits.max_energy > snake.traits.max_energy
        state.grid.cells[2][2] = bear
        state.grid.cells[2][3] = snake
        events = []
        for _ in range(10):
            step(state, events)
        carn_kill_events = [e for e in events if e["kind"] == "carn_kill"]
        assert len(carn_kill_events) >= 1

    def test_any_carn_eats_other_carn_species(self, state):
        state.grid = Grid(5, 5)
        lion_emoji = "\U0001F981"
        fox_emoji = "\U0001F98A"
        lion = make_carn([lion_emoji])
        fox = make_carn([fox_emoji])
        lion.energy = 5
        fox.energy = 100
        assert not lion.traits.can_hunt_carns
        assert lion.traits.max_energy > fox.traits.max_energy
        state.grid.cells[2][2] = lion
        state.grid.cells[2][3] = fox
        events = []
        for _ in range(20):
            step(state, events)
        carn_kill_events = [e for e in events if e["kind"] == "carn_kill"]
        assert len(carn_kill_events) >= 1

    def test_cannibalism_when_dire(self, state):
        state.grid = Grid(5, 5)
        lion_emoji = "\U0001F981"
        lion1 = make_carn([lion_emoji])
        lion2 = make_carn([lion_emoji])
        lion1.energy = 3
        lion2.energy = 100
        assert lion1.species == lion2.species
        state.grid.cells[2][2] = lion1
        state.grid.cells[2][3] = lion2
        events = []
        for _ in range(20):
            step(state, events)
        carn_kill_events = [e for e in events if e["kind"] == "carn_kill"]
        assert len(carn_kill_events) >= 1

    def test_no_cannibalism_when_well_fed(self, state):
        state.grid = Grid(5, 5)
        lion_emoji = "\U0001F981"
        lion1 = make_carn([lion_emoji])
        lion2 = make_carn([lion_emoji])
        lion1.energy = lion1.traits.max_energy - 1
        lion2.energy = 100
        state.grid.cells[2][2] = lion1
        state.grid.cells[2][3] = lion2
        events = []
        step(state, events)
        carn_kills = [e for e in events if e["kind"] == "carn_kill"
                      and e.get("predator_species") == "lion"
                      and e.get("prey_species") == "lion"]
        assert len(carn_kills) == 0

    def test_plant_dies_of_old_age(self, state):
        state.grid = Grid(5, 5)
        plant = make_plant()
        plant.age = state.config.plant_max_age + 1
        state.grid.cells[2][2] = plant
        step(state, [])
        assert state.grid.cells[2][2] is None

    def test_energy_not_negative_after_eat(self, state):
        state.grid = Grid(5, 5)
        herbs = [ALL_HERBIVORES[0][0]]
        herb = make_herb(herbs)
        plant = make_plant()
        plant.growth = 3
        state.grid.cells[2][2] = herb
        state.grid.cells[2][3] = plant
        step(state, [])
        assert herb.energy <= herb.traits.max_energy

    def test_step_with_empty_grid(self, state):
        state.grid = Grid(5, 5)
        step(state, [])
        assert state.tick == 1

    def test_step_handles_water_only(self, state):
        state.grid = Grid(5, 5)
        state.grid.cells[0][0] = Entity(Kind.WATER, "\U0001F30A", 0, species="water")
        step(state, [])
        assert state.grid.cells[0][0] is not None
        assert state.grid.cells[0][0].kind == Kind.WATER


# -- Count tests -----------------------------------------------------------


class TestCountPop:
    def test_empty_grid(self, small_grid):
        counts = count_pop(small_grid)
        assert counts[Kind.PLANT] == 0
        assert counts[Kind.HERBIVORE] == 0
        assert counts[Kind.CARNIVORE] == 0
        assert counts[Kind.WATER] == 0

    def test_mixed_grid(self, small_grid):
        small_grid.cells[0][0] = make_plant()
        small_grid.cells[0][1] = make_herb([ALL_HERBIVORES[0][0]])
        small_grid.cells[0][2] = Entity(Kind.WATER, "\U0001F30A", 0, species="water")
        counts = count_pop(small_grid)
        assert counts[Kind.PLANT] == 1
        assert counts[Kind.HERBIVORE] == 1
        assert counts[Kind.WATER] == 1


class TestCountBySpecies:
    def test_empty_grid(self, small_grid):
        counts = count_by_species(small_grid, Kind.HERBIVORE)
        assert counts == {}

    def test_multiple_species(self, small_grid):
        small_grid.cells[0][0] = make_herb([ALL_HERBIVORES[0][0]])
        small_grid.cells[0][1] = make_herb([ALL_HERBIVORES[0][0]])
        small_grid.cells[0][2] = make_herb([ALL_HERBIVORES[1][0]])
        counts = count_by_species(small_grid, Kind.HERBIVORE)
        assert counts["rabbit"] == 2
        assert counts["sheep"] == 1


# -- Populate / setup tests ------------------------------------------------


class TestPopulate:
    def test_populate_creates_entities(self, config):
        grid = Grid(50, 50)
        herbs = [e for e, _, _ in ALL_HERBIVORES]
        carns = [e for e, _, _ in ALL_CARNIVORES]
        populate(grid, config, herbs, carns)
        counts = count_pop(grid)
        assert counts[Kind.PLANT] > 0
        assert counts[Kind.HERBIVORE] > 0
        assert counts[Kind.CARNIVORE] > 0
        assert counts[Kind.WATER] > 0

    def test_populate_no_herbs(self, small_grid, config):
        populate(small_grid, config, [], [])
        counts = count_pop(small_grid)
        assert counts[Kind.HERBIVORE] == 0
        assert counts[Kind.CARNIVORE] == 0
        assert counts[Kind.PLANT] > 0

    def test_place_water_creates_clusters(self, small_grid):
        _place_water(small_grid, 10)
        water_count = count_pop(small_grid)[Kind.WATER]
        assert water_count > 0

    def test_drop_creatures(self, small_grid):
        initial = count_pop(small_grid)[Kind.PLANT]
        drop_creatures(small_grid, make_plant, 5)
        after = count_pop(small_grid)[Kind.PLANT]
        assert after >= initial
        assert after <= initial + 5


# -- Save / Load tests -----------------------------------------------------


class TestSaveLoad:
    def test_save_creates_file(self, state):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            filepath = f.name
        try:
            result = save_state(state, filepath)
            assert result
            assert os.path.exists(filepath)
            with open(filepath) as f:
                data = json.load(f)
            assert "tick" in data
            assert "grid" in data
            assert "config" in data
        finally:
            if os.path.exists(filepath):
                os.remove(filepath)

    def test_load_returns_state(self, state):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            filepath = f.name
        try:
            state.tick = 42
            state.selected_herbs = [ALL_HERBIVORES[0][0]]
            state.selected_carns = [ALL_CARNIVORES[0][0]]
            save_state(state, filepath)
            loaded = load_state(filepath)
            assert loaded is not None
            assert loaded.tick == 42
            assert loaded.selected_herbs == [ALL_HERBIVORES[0][0]]
            assert loaded.selected_carns == [ALL_CARNIVORES[0][0]]
        finally:
            if os.path.exists(filepath):
                os.remove(filepath)

    def test_save_load_roundtrip_preserves_grid(self, state):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            filepath = f.name
        try:
            populate(state.grid, state.config, state.selected_herbs, state.selected_carns)
            original_counts = count_pop(state.grid)
            save_state(state, filepath)
            loaded = load_state(filepath)
            assert loaded is not None
            loaded_counts = count_pop(loaded.grid)
            assert loaded_counts == original_counts
        finally:
            if os.path.exists(filepath):
                os.remove(filepath)

    def test_save_load_preserves_nutrients(self, state):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            filepath = f.name
        try:
            state.grid.add_nutrients(5, 5, 7.5)
            save_state(state, filepath)
            loaded = load_state(filepath)
            assert loaded is not None
            assert abs(loaded.grid.nutrients[5][5] - 7.5) < 0.01
        finally:
            if os.path.exists(filepath):
                os.remove(filepath)

    def test_save_load_preserves_entity_state(self, state):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            filepath = f.name
        try:
            herbs = [ALL_HERBIVORES[0][0]]
            e = make_herb(herbs)
            e.energy = 25
            e.age = 10
            e.thirst = 15
            e.diseased = 5
            state.grid.cells[5][5] = e
            save_state(state, filepath)
            loaded = load_state(filepath)
            assert loaded is not None
            le = loaded.grid.get(5, 5)
            assert le is not None
            assert le.energy == 25
            assert le.age == 10
            assert le.thirst == 15
            assert le.diseased == 5
            assert le.species == e.species
            assert le.traits is not None
        finally:
            if os.path.exists(filepath):
                os.remove(filepath)

    def test_save_load_preserves_stats(self, state):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            filepath = f.name
        try:
            state.stats.total_births = 10
            state.stats.total_kills = 5
            state.stats.peak_plants = 100
            state.stats.death_ages = [10, 20, 30]
            save_state(state, filepath)
            loaded = load_state(filepath)
            assert loaded is not None
            assert loaded.stats.total_births == 10
            assert loaded.stats.total_kills == 5
            assert loaded.stats.peak_plants == 100
            assert loaded.stats.death_ages == [10, 20, 30]
        finally:
            if os.path.exists(filepath):
                os.remove(filepath)

    def test_load_nonexistent_returns_none(self):
        result = load_state("/nonexistent/path/file.json")
        assert result is None

    def test_save_load_preserves_config(self, state):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            filepath = f.name
        try:
            state.config.plant_spread_chance = 0.15
            state.config.season_length = 75
            save_state(state, filepath)
            loaded = load_state(filepath)
            assert loaded is not None
            assert loaded.config.plant_spread_chance == 0.15
            assert loaded.config.season_length == 75
        finally:
            if os.path.exists(filepath):
                os.remove(filepath)


# -- Event formatting tests ------------------------------------------------


class TestEventFormatting:
    def test_kill_event(self):
        ev = make_event("kill", 1, 2,
                        predator_emoji="\U0001F981", predator_name="Leo",
                        predator_species="lion",
                        prey_emoji="\U0001F430", prey_name="Bugs",
                        prey_species="rabbit")
        msg = event_to_message(ev)
        assert "Leo" in msg
        assert "Bugs" in msg
        assert "lion" in msg
        assert "rabbit" in msg

    def test_birth_event(self):
        ev = make_event("birth", 1, 2,
                        emoji="\U0001F430", name="Junior",
                        species="rabbit",
                        parent_name="Mama", parent_emoji="\U0001F430")
        msg = event_to_message(ev)
        assert "Junior" in msg
        assert "Mama" in msg

    def test_starve_event(self):
        ev = make_event("starve", 1, 2,
                        emoji="\U0001F430", name="Hungry",
                        species="rabbit")
        msg = event_to_message(ev)
        assert "Hungry" in msg
        assert "starved" in msg

    def test_age_death_event(self):
        ev = make_event("age_death", 1, 2,
                        emoji="\U0001F430", name="Old",
                        species="rabbit")
        msg = event_to_message(ev)
        assert "Old" in msg
        assert "old age" in msg

    def test_disease_death_event(self):
        ev = make_event("disease_death", 1, 2,
                        emoji="\U0001F430", name="Sickly",
                        species="rabbit")
        msg = event_to_message(ev)
        assert "Sickly" in msg
        assert "disease" in msg

    def test_carn_kill_event(self):
        ev = make_event("carn_kill", 1, 2,
                        predator_emoji="\U0001F43B", predator_name="Bear",
                        predator_species="bear",
                        prey_emoji="\U0001F40D", prey_name="Slithery",
                        prey_species="snake")
        msg = event_to_message(ev)
        assert "Bear" in msg
        assert "Slithery" in msg

    def test_unknown_event(self):
        ev = make_event("unknown", 1, 2)
        assert event_to_message(ev) == ""


# -- Parameter tuning tests ------------------------------------------------


class TestParamTuning:
    def test_param_list_not_empty(self, config):
        params = _param_list(config)
        assert len(params) > 0

    def test_param_list_has_names(self, config):
        params = _param_list(config)
        for name, val in params:
            assert len(name) > 0
            assert len(val) > 0

    def test_adjust_param_increases(self, config):
        original = config.plant_spread_chance
        _adjust_param(config, 0, 1)
        assert config.plant_spread_chance > original

    def test_adjust_param_decreases(self, config):
        original = config.plant_spread_chance
        _adjust_param(config, 0, -1)
        assert config.plant_spread_chance < original

    def test_adjust_param_clamps_min(self, config):
        config.plant_spread_chance = 0.01
        _adjust_param(config, 0, -1)
        assert config.plant_spread_chance >= 0.01

    def test_adjust_param_clamps_max(self, config):
        config.plant_spread_chance = 0.30
        _adjust_param(config, 0, 1)
        assert config.plant_spread_chance <= 0.30

    def test_adjust_param_invalid_idx(self, config):
        _adjust_param(config, -1, 1)
        _adjust_param(config, 999, 1)


# -- Season tests ----------------------------------------------------------


class TestSeasons:
    def test_four_seasons(self):
        assert len(SEASON_NAMES) == 4

    def test_season_names(self):
        assert SEASON_NAMES == ["Spring", "Summer", "Autumn", "Winter"]

    def test_plant_mod_values(self):
        assert SEASON_PLANT_MOD[0] > SEASON_PLANT_MOD[1]
        assert SEASON_PLANT_MOD[3] < SEASON_PLANT_MOD[2]

    def test_energy_mod_values(self):
        assert SEASON_ENERGY_MOD[3] > SEASON_ENERGY_MOD[0]

    def test_winter_has_dieoff(self):
        assert SEASON_DIEOFF_CHANCE[3] > 0
        assert SEASON_DIEOFF_CHANCE[0] == 0

    def test_season_progress(self, state):
        state.config.season_length = 10
        state.tick = 3
        assert state.season_progress == 3

    def test_season_cycles(self, state):
        state.config.season_length = 5
        state.tick = 0
        assert (state.tick // 5) % 4 == 0
        state.tick = 5
        assert (state.tick // 5) % 4 == 1
        state.tick = 15
        assert (state.tick // 5) % 4 == 3
        state.tick = 20
        assert (state.tick // 5) % 4 == 0


# -- Energy conservation tests ---------------------------------------------


class TestEnergyConservation:
    def test_herbivore_eat_gains_energy(self, state):
        state.grid = Grid(5, 5)
        herbs = [ALL_HERBIVORES[0][0]]
        herb = make_herb(herbs)
        plant = make_plant()
        plant.growth = 3
        state.grid.cells[2][2] = herb
        state.grid.cells[2][3] = plant
        initial = herb.energy
        step(state, [])
        assert herb.energy >= initial

    def test_herbivore_loses_energy_without_food(self, state):
        state.grid = Grid(5, 5)
        herbs = [ALL_HERBIVORES[0][0]]
        herb = make_herb(herbs)
        herb.energy = 50
        state.grid.cells[2][2] = herb
        initial = herb.energy
        step(state, [])
        assert herb.energy < initial

    def test_carnivore_gains_from_kill(self, state):
        state.grid = Grid(5, 5)
        carns = [ALL_CARNIVORES[0][0]]
        herbs = [ALL_HERBIVORES[0][0]]
        carn = make_carn(carns)
        carn.energy = 5
        herb = make_herb(herbs)
        state.grid.cells[2][2] = carn
        state.grid.cells[2][3] = herb
        initial = carn.energy
        events = []
        step(state, events)
        if any(e["kind"] == "kill" for e in events):
            assert carn.energy > initial

    def test_reproduction_costs_energy(self, state):
        state.grid = Grid(5, 5)
        herbs = [ALL_HERBIVORES[0][0]]
        herb = make_herb(herbs)
        herb.energy = 200
        state.grid.cells[5 % 5][5 % 5] = herb
        state.config.herb_repro_threshold = 10
        initial = herb.energy
        for _ in range(5):
            step(state, [])
        assert herb.energy < initial

    def test_energy_capped_at_max(self, state):
        state.grid = Grid(5, 5)
        herbs = [ALL_HERBIVORES[0][0]]
        herb = make_herb(herbs)
        herb.energy = herb.traits.max_energy - 1
        plant = make_plant()
        plant.growth = 3
        state.grid.cells[2][2] = herb
        state.grid.cells[2][3] = plant
        step(state, [])
        assert herb.energy <= herb.traits.max_energy


# -- Integration tests -----------------------------------------------------


class TestIntegration:
    def test_long_run_does_not_crash(self, state):
        for _ in range(100):
            events = []
            step(state, events)

    def test_long_run_with_seed_reproducible(self):
        random.seed(123)
        herbs = [ALL_HERBIVORES[0][0]]
        carns = [ALL_CARNIVORES[0][0]]
        cfg = make_config("balanced")
        g1 = Grid(10, 10)
        populate(g1, cfg, herbs, carns)
        s1 = GameState(grid=g1, config=cfg, selected_herbs=herbs, selected_carns=carns)
        for _ in range(20):
            step(s1, [])
        counts1 = count_pop(g1)

        random.seed(123)
        g2 = Grid(10, 10)
        populate(g2, cfg, herbs, carns)
        s2 = GameState(grid=g2, config=cfg, selected_herbs=herbs, selected_carns=carns)
        for _ in range(20):
            step(s2, [])
        counts2 = count_pop(g2)

        assert counts1 == counts2

    def test_reset_works(self, state):
        for _ in range(10):
            step(state, [])
        assert state.tick > 0
        state.grid = Grid(10, 10)
        populate(state.grid, state.config, state.selected_herbs, state.selected_carns)
        state.tick = 0
        state.season = 0
        state.hist = {"plant": [], "herb": [], "carn": []}
        state.ticker = []
        state.flashes = {}
        state.stats = Stats()
        assert state.tick == 0
        assert count_pop(state.grid)[Kind.PLANT] > 0
