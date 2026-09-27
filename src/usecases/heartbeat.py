from __future__ import annotations

import asyncio
import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from src.adapters.jev_brain import ActionRequest, GrowthRequest, JevBrain, LocusRequest, Sprout
from src.adapters.vital_repo import VitalRepository
from src.adapters.web_forager import WebForager
from src.domain.knowledge_crystal import KnowledgeCrystal
from src.domain.organism import Organism
from src.domain.species import SPECIES_REGISTRY, SpeciesType

INGEST_ACTIONS = ("ingest_nourish", "reconcile_contradiction")
MAX_SPROUTS_PER_PULSE = 3

# Births are deliberately rare. An eligible Tierra DIVIDE only becomes a new organism with this probability,
# and each world accepts at most one birth per BIRTH_COOLDOWN, so long stretches without births are normal.
BIRTH_PROBABILITY = 0.005
BIRTH_COOLDOWN = timedelta(hours=24)

# A larger body costs more to maintain: every existing cell burns a little energy each pulse,
# which is what keeps growth from continuing forever instead of a hard cap on cell count.
PER_CELL_UPKEEP = 0.05

# Disease/parasite risk rises with body size (overcrowding) and prunes cells + drains energy when it
# strikes. Recovering those cells afterward still requires nutrition, same as any other growth.
HAZARD_FREE_CELLS = 10        # cells below this add no extra hazard risk
HAZARD_BASE_PROBABILITY = 0.03
HAZARD_CELL_SCALING = 0.001   # extra probability per cell beyond HAZARD_FREE_CELLS
HAZARD_PROBABILITY_CAP = 0.35
HAZARD_KINDS: dict[str, dict[str, Any]] = {
    "plague": {"energy_drain": (8.0, 20.0), "max_cells_lost": 3},
    "parasite": {"energy_drain": (5.0, 12.0), "max_cells_lost": 2},
}

SATIATED_DECISION = (
    "rest_meditate",
    0.5,
    "High somatic energy. Entering serene resting meditation to digest assimilated wisdom (API skipped).",
)


@dataclass
class _PulsePlan:
    organism: Organism
    prey: dict[str, Any]
    action: str
    noul_quality: float
    rationale: str
    energy_gain: float
    growth_gain: float
    new_locus: str
    divide_genomes: list[list[int]] = field(default_factory=list)
    crystal: KnowledgeCrystal | None = None
    growth_request: GrowthRequest | None = None
    locus_request: LocusRequest | None = None


class HeartbeatUsecase:
    """One heartbeat advances every living organism; Jev is asked about all of them in batched calls."""

    def __init__(self, repo: VitalRepository, brain: JevBrain, forager: WebForager, rng: random.Random | None = None) -> None:
        self.repo = repo
        self.brain = brain
        self.forager = forager
        self.rng = rng or random.Random()

    async def pulse_all(self) -> list[dict[str, Any]]:
        organisms = await self.repo.get_all_organisms()
        if not organisms:
            return []

        # 1. Perception: satiated organisms digest internally; the rest forage their locus concurrently.
        satiated = [self._is_satiated(o) for o in organisms]
        preys = await asyncio.gather(*(self._perceive(o, s) for o, s in zip(organisms, satiated)))

        # 2. Decision: one Jev call for every hungry organism's action.
        decisions = self.brain.decide_actions([
            ActionRequest(
                key=o.id,
                species=o.species,
                perception=f"Title: {prey.get('title')}\nExcerpt: {prey.get('content', '')[:600]}",
                energy=o.energy,
                hunger=o.hunger_level,
            )
            for o, prey, full in zip(organisms, preys, satiated) if not full
        ])

        # 3. Metabolism & Tierra VM execution per organism.
        plans = []
        for o, prey, full in zip(organisms, preys, satiated):
            action, noul_quality, rationale = SATIATED_DECISION if full else decisions[o.id]
            plans.append(self._metabolize(o, prey, action, noul_quality, rationale))
        await self.repo.save_crystals([p.crystal for p in plans if p.crystal])

        # 4. One Jev call for all 3D growth and next-locus choices.
        sprouts, next_loci = self.brain.decide_growth_and_locus(
            [p.growth_request for p in plans if p.growth_request],
            [p.locus_request for p in plans if p.locus_request],
        )

        # 5. Develop, then persist everything in one write per world. Newborns go last so the Reaper
        #    weighs them against every updated organism instead of resurrecting a reaped one.
        births_this_pulse: set[SpeciesType] = set()
        updated_all: list[Organism] = []
        dead: list[Organism] = []
        newborns: list[Organism] = []
        results = []
        for plan in plans:
            updated, daughter = self._develop(plan, sprouts.get(plan.organism.id, []), next_loci.get(plan.organism.id), organisms, births_this_pulse)
            if updated is None:
                dead.append(plan.organism)
                results.append(self._death_summary(plan))
                continue
            updated_all.append(updated)
            if daughter:
                newborns.append(daughter)
                births_this_pulse.add(daughter.species)
            results.append(self._summary(updated, plan, daughter))
        await self.repo.save_organisms(updated_all + newborns, removals=dead)
        return results

    @staticmethod
    def _is_satiated(organism: Organism) -> bool:
        """Well-fed organisms beyond the larval stage meditate without calling Jev."""
        return organism.energy >= 85.0 and organism.hunger_level <= 0.15 and len(organism.morphology.cells) >= 6

    async def _perceive(self, organism: Organism, satiated: bool) -> dict[str, Any]:
        if satiated:
            return {"title": "Internal Meditation", "content": "", "url": organism.current_locus}
        return await self.forager.forage_locus(organism.species, organism.current_locus)

    def _metabolize(self, organism: Organism, prey: dict[str, Any], action: str, noul_quality: float, rationale: str) -> _PulsePlan:
        profile = SPECIES_REGISTRY[organism.species]
        plan = _PulsePlan(organism, prey, action, noul_quality, rationale, 0.0, 0.0, organism.current_locus)

        # Ray Tierra: knowledge nutrition directly earns CPU execution time-slices
        cpu_slice_awarded = 15
        if action in INGEST_ACTIONS:
            plan.energy_gain = round(12.0 * noul_quality + 4.0, 1)
            plan.growth_gain = round(8.0 * noul_quality + 2.0, 1)
            cpu_slice_awarded = int(45 + noul_quality * 60)  # 45-105 cycles: triggers 1-2 Ancestor divides
            plan.crystal = KnowledgeCrystal(
                organism_id=organism.id,
                species=organism.species.value,
                source_url=prey.get("url", organism.current_locus),
                concept_title=prey.get("title", f"{profile.name} Intuition"),
                core_insight=self._distill_core_insight(prey.get("content", ""), organism.species.value),
                tags=prey.get("tags", "").split(", ") if prey.get("tags") else [organism.species.value],
                nutritional_value=plan.energy_gain,
            )
            if prey.get("candidate_links") and noul_quality >= 0.4:
                plan.locus_request = LocusRequest(
                    key=organism.id,
                    species=organism.species,
                    prey_title=prey.get("title", ""),
                    prey_content=prey.get("content", ""),
                    candidate_links=prey["candidate_links"],
                    current_locus=organism.current_locus,
                )
        elif action == "swim_next":
            candidates = [s for s in profile.default_prey_sources if s != organism.current_locus]
            plan.new_locus = random.choice(candidates) if candidates else organism.current_locus
            plan.growth_gain = 1.0
            cpu_slice_awarded = 25
        elif action == "rest_meditate":
            plan.growth_gain = 0.2
            cpu_slice_awarded = 10

        # Execute the authentic 32-instruction Tierra VM in its RAM soup
        organism.tierra_vm.award_cpu_slice(cpu_slice_awarded)
        organism.tierra_vm.execute_slice(on_divide_callback=lambda _count, genome: plan.divide_genomes.append(genome))

        # Each DIVIDE sprouts a cell in 3D space; feeding sprouts at least one even mid-copy-loop.
        sprout_count = max(len(plan.divide_genomes), 1 if action in INGEST_ACTIONS else 0)
        if sprout_count:
            plan.growth_request = GrowthRequest(
                key=organism.id,
                species=organism.species,
                prey_title=prey.get("title", "Undiscovered Wisdom"),
                prey_content=prey.get("content", ""),
                cells_count=len(organism.morphology.cells),
                energy=organism.energy,
                sprouts=min(sprout_count, MAX_SPROUTS_PER_PULSE),
            )
        return plan

    def _develop(
        self,
        plan: _PulsePlan,
        sprouts: list[Sprout],
        chosen_locus: str | None,
        population: list[Organism],
        births_this_pulse: set[SpeciesType],
    ) -> tuple[Organism | None, Organism | None]:
        organism, prey = plan.organism, plan.prey
        cells_at_start = len(organism.morphology.cells)
        cell_upkeep = round(cells_at_start * PER_CELL_UPKEEP, 2)

        # Nutrition first heals any cells lost to a past hazard, capped at the prior peak; only once
        # fully recovered does further nutrition extend the peak (real growth).
        peak = max(organism.peak_cells, cells_at_start)
        allowance = len(sprouts) if cells_at_start >= peak else max(0, peak - cells_at_start)
        morphology = organism.morphology
        for anchor, az, el, dist, radius, color in sprouts[:allowance]:
            morphology = morphology.grow_cell(
                anchor_choice=anchor,
                azimuth_deg=az,
                elevation_deg=el,
                growth_distance=dist,
                cell_radius=radius,
                cell_color=color,
                source_title=prey.get("title", "Tierra Replicated Cell"),
            )

        rationale = plan.rationale
        hazard_drain = 0.0
        hazard = self._roll_hazard(cells_at_start)
        if hazard:
            kind, hazard_drain, cells_lost = hazard
            morphology = morphology.lose_cells(cells_lost)
            rationale = f"{rationale} A {kind} strikes: -{cells_lost} cells, -{hazard_drain:.1f} energy."

        updated = organism.apply_metabolism(
            action=plan.action,
            noul_quality=plan.noul_quality,
            rationale=rationale,
            locus=chosen_locus or plan.new_locus,
            energy_gain=plan.energy_gain,
            growth_gain=plan.growth_gain,
            cell_upkeep=cell_upkeep,
            hazard_energy_drain=hazard_drain,
            new_morphology=morphology,
            new_tierra_vm=organism.tierra_vm,
            new_peak_cells=max(peak, len(morphology.cells)),
        )

        if updated.energy <= 0.0:
            # Starved or succumbed to affliction. The world respawns a fresh Ancestor-80 next heartbeat.
            return None, None

        # Ray's Tierra reproduction: a mature parent whose VM executed DIVIDE may bear a mutated daughter.
        if not (plan.divide_genomes and updated.energy >= 65.0 and len(updated.morphology.cells) >= 3):
            return updated, None
        if organism.species in births_this_pulse or not self._birth_allowed(organism.species, population):
            return updated, None
        if self.rng.random() >= BIRTH_PROBABILITY:
            return updated, None

        angle = random.uniform(0, 2 * math.pi)
        dist_3d = random.uniform(14.0, 26.0)
        spawn_offset = (math.cos(angle) * dist_3d, random.uniform(-8.0, 8.0), math.sin(angle) * dist_3d)
        updated, daughter = updated.reproduce(daughter_genome=plan.divide_genomes[-1], spawn_offset=spawn_offset)
        daughter = daughter.apply_metabolism(
            action="ingest_nourish",
            noul_quality=0.5,
            rationale=f"Born from {organism.name} via Tierra DIVIDE. Lineage: {daughter.lineage} (Gen {daughter.generation}).",
            locus=updated.current_locus,
        )
        return updated, daughter

    @staticmethod
    def _birth_allowed(species: SpeciesType, population: list[Organism]) -> bool:
        """At most one birth per world per BIRTH_COOLDOWN, judged by the youngest offspring still alive."""
        cutoff = datetime.now(timezone.utc) - BIRTH_COOLDOWN
        for o in population:
            if o.species == species and o.generation > 0:
                try:
                    if datetime.fromisoformat(o.created_at) > cutoff:
                        return False
                except ValueError:
                    continue
        return True

    def _roll_hazard(self, cells_count: int) -> tuple[str, float, int] | None:
        """Disease/parasite risk grows with body size (overcrowding); every draw goes through `self.rng`
        (never the module-level `random`) so hazard outcomes are as deterministic and testable as the
        birth roll below, instead of `.choice`/`.randint` silently bypassing an injected RNG double."""
        if cells_count <= 1:
            return None
        probability = min(
            HAZARD_PROBABILITY_CAP,
            HAZARD_BASE_PROBABILITY + max(0, cells_count - HAZARD_FREE_CELLS) * HAZARD_CELL_SCALING,
        )
        if self.rng.random() >= probability:
            return None
        kinds = list(HAZARD_KINDS)
        kind = kinds[min(int(self.rng.random() * len(kinds)), len(kinds) - 1)]
        spec = HAZARD_KINDS[kind]
        lo, hi = spec["energy_drain"]
        energy_drain = round(lo + (hi - lo) * self.rng.random(), 1)
        cells_lost = min(spec["max_cells_lost"], 1 + int(self.rng.random() * spec["max_cells_lost"]))
        return kind, energy_drain, cells_lost

    @staticmethod
    def _summary(updated: Organism, plan: _PulsePlan, daughter: Organism | None) -> dict[str, Any]:
        return {
            "organism_id": updated.id,
            "species": updated.species.value,
            "name": updated.name,
            "lineage": updated.lineage,
            "generation": updated.generation,
            "action": plan.action,
            "noul_quality": plan.noul_quality,
            "rationale": updated.last_thought.rationale if updated.last_thought else plan.rationale,
            "energy": updated.energy,
            "growth_score": updated.growth_score,
            "phase": updated.phase.value,
            "cells_count": len(updated.morphology.cells),
            "daughter_born": daughter.name if daughter else None,
            "crystal_created": plan.crystal.to_summary_dict() if plan.crystal else None,
            "timestamp": updated.last_pulse_at,
        }

    @staticmethod
    def _death_summary(plan: _PulsePlan) -> dict[str, Any]:
        organism = plan.organism
        return {
            "organism_id": organism.id,
            "species": organism.species.value,
            "name": organism.name,
            "lineage": organism.lineage,
            "generation": organism.generation,
            "action": "deceased",
            "noul_quality": plan.noul_quality,
            "rationale": f"{plan.rationale} Energy depleted to zero; the organism has died.",
            "energy": 0.0,
            "growth_score": organism.growth_score,
            "phase": organism.phase.value,
            "cells_count": len(organism.morphology.cells),
            "daughter_born": None,
            "crystal_created": plan.crystal.to_summary_dict() if plan.crystal else None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _distill_core_insight(self, content: str, species_name: str) -> str:
        """Create a concentrated essence string of the assimilated text."""
        sentences = [s.strip() for s in content.replace("。", ".").split(".") if len(s.strip()) > 20]
        if sentences:
            return sentences[0] + "."
        return f"Fundamental insight intuitively assimilated by {species_name} from the environment."
