import random

from src.domain.morphology import Morphology3D
from src.domain.organism import Organism
from src.domain.species import SpeciesType
from src.usecases.heartbeat import HAZARD_BASE_PROBABILITY, HAZARD_FREE_CELLS, PER_CELL_UPKEEP, HeartbeatUsecase, _PulsePlan


def grown(species=SpeciesType.GAIA, cells=4, energy=95.0, peak_cells=None):
    org = Organism.spawn(species)
    morph = org.morphology
    for _ in range(cells - 1):
        morph = morph.grow_cell(anchor_choice="latest_tip", azimuth_deg=0, elevation_deg=0, growth_distance=5,
                                cell_radius=1, cell_color="#fff", source_title="t")
    return org.model_copy(update={"energy": energy, "morphology": morph, "peak_cells": peak_cells if peak_cells is not None else cells})


def plan_for(org, action="rest_meditate", divide=True):
    return _PulsePlan(org, {"title": "t", "content": "c"}, action, 0.5, "r", 0.0, 0.0, org.current_locus,
                      divide_genomes=[[0]] if divide else [])


class FixedRng(random.Random):
    def __init__(self, value):
        super().__init__()
        self.value = value

    def random(self):
        return self.value


def uc(rng_value):
    return HeartbeatUsecase(None, None, None, rng=FixedRng(rng_value))


def test_lose_cells_keeps_at_least_one_and_drops_referencing_edges():
    m = Morphology3D.initial_seed("#fff")
    for _ in range(5):
        m = m.grow_cell(anchor_choice="latest_tip", azimuth_deg=0, elevation_deg=0, growth_distance=5,
                        cell_radius=1, cell_color="#fff", source_title="t")
    assert len(m.cells) == 6

    trimmed = m.lose_cells(3)
    assert len(trimmed.cells) == 3
    remaining_ids = {c.id for c in trimmed.cells}
    assert all(e.source_id in remaining_ids and e.target_id in remaining_ids for e in trimmed.edges)

    assert len(m.lose_cells(999).cells) == 1  # never drops to zero
    assert m.lose_cells(0).cells == m.cells


def test_bigger_body_burns_more_energy_per_pulse():
    small = grown(cells=1, energy=50.0)
    big = grown(cells=40, energy=50.0)
    engine = uc(rng_value=0.99)  # 0.99 clears the hazard gate at any cell count used here -> no hazard noise

    small_after, _ = engine._develop(plan_for(small, divide=False), [], None, [small], set())
    big_after, _ = engine._develop(plan_for(big, divide=False), [], None, [big], set())

    assert small_after.energy == 50.0 - 1.5  # base rest_meditate burn only, no cell upkeep at 1 cell
    assert big_after.energy == round(50.0 - 1.5 - 40 * PER_CELL_UPKEEP, 1)


def test_hazard_drains_energy_and_prunes_cells_when_it_fires():
    org = grown(cells=20, energy=90.0)
    hit, _ = uc(rng_value=0.0)._develop(plan_for(org, divide=False), [], None, [org], set())  # 0.0 always clears the gate
    spared, _ = uc(rng_value=0.999)._develop(plan_for(org, divide=False), [], None, [org], set())

    assert len(hit.morphology.cells) < 20
    assert hit.energy < spared.energy
    assert "strikes" in hit.last_thought.rationale


def test_hazard_probability_rises_with_cell_count_but_never_fires_for_a_single_cell():
    lone = grown(cells=1, energy=90.0)
    assert uc(rng_value=HAZARD_BASE_PROBABILITY / 2)._roll_hazard(1) is None

    below_threshold = uc(rng_value=HAZARD_BASE_PROBABILITY + 0.001)._roll_hazard(HAZARD_FREE_CELLS)
    above_threshold = uc(rng_value=HAZARD_BASE_PROBABILITY + 0.001)._roll_hazard(HAZARD_FREE_CELLS + 50)
    assert below_threshold is None and above_threshold is not None


def test_recovery_is_capped_at_peak_then_further_nutrition_grows_past_it():
    damaged = grown(cells=5, peak_cells=10, energy=90.0)  # lost cells earlier; peak remembers the high-water mark
    plan = plan_for(damaged, action="ingest_nourish")
    sprouts = [("latest_tip", 0.0, 0.0, 5.0, 1.0, "#fff")] * 8  # more sprouts than the 5-cell shortfall to peak

    healed, _ = uc(rng_value=0.99)._develop(plan, sprouts, None, [damaged], set())
    assert len(healed.morphology.cells) == 10  # capped at peak, not 5+8=13
    assert healed.peak_cells == 10

    at_peak = damaged.model_copy(update={"morphology": healed.morphology, "peak_cells": 10})
    grown_further, _ = uc(rng_value=0.99)._develop(plan_for(at_peak, action="ingest_nourish"), sprouts, None, [at_peak], set())
    assert len(grown_further.morphology.cells) == 10 + len(sprouts)  # no longer capped once fully recovered
    assert grown_further.peak_cells == len(grown_further.morphology.cells)


def test_organism_dies_when_energy_reaches_zero():
    dying = grown(cells=1, energy=1.0)
    updated, daughter = uc(rng_value=0.99)._develop(plan_for(dying, action="rest_meditate", divide=False), [], None, [dying], set())
    assert updated is None and daughter is None
