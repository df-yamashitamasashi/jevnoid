from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field

from .species import SpeciesType, SPECIES_REGISTRY
from .morphology import Morphology3D
from .tierra_vm import TierraVM


class LifePhase(str, Enum):
    LARVA = "larva"              # 幼生（単細胞・初期探索）
    JUVENILE = "juvenile"        # 青年（多細胞・活発な摂食）
    ADULT = "adult"              # 成体（成熟・独自の選択基準の確立）
    TRANSCENDENT = "transcendent"  # 超越体（高次存在・環境そのものと同化）


class ThoughtRecord(BaseModel):
    """Snapshot of a System One decision made by Jev."""
    pulse_index: int
    action_chosen: str
    rationale: str
    noul_quality: float
    locus_visited: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class Organism(BaseModel):
    """An autonomous digital organism inhabiting the network with an authentic Tierra VM core."""
    id: str
    species: SpeciesType
    name: str
    phase: LifePhase = LifePhase.LARVA
    energy: float = 80.0                # 0.0 - 100.0 (death/hibernation below 5.0)
    hunger_level: float = 0.2           # 0.0 - 1.0 (approaches 1.0 as time passes)
    age_pulses: int = 0                 # Total heartbeat cycles survived
    growth_score: float = 10.0          # Species-specific score (Divinity, Harmony, etc.)
    current_locus: str = ""
    crystals_count: int = 0
    lineage: str = "Ancestor-80"        # e.g. "Ancestor-80", "Parasite-45p", "Mutant-Lineage-2β"
    generation: int = 0                 # 0 for ancestral seed, 1, 2, ... for offspring
    parent_id: str | None = None
    mutations_count: int = 0
    is_alive: bool = True
    peak_cells: int = 1                 # Highest cell count ever reached; nutrition heals up to this before it can rise further
    morphology: Morphology3D = Field(default_factory=lambda: Morphology3D.initial_seed("#ffffff"))
    tierra_vm: TierraVM = Field(default_factory=lambda: TierraVM.create_with_ancestor())
    last_thought: ThoughtRecord | None = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_pulse_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @classmethod
    def spawn(cls, species: SpeciesType, custom_id: str | None = None) -> Organism:
        profile = SPECIES_REGISTRY[species]
        return cls(
            id=custom_id or f"{species.value}-{uuid_suffix()}",
            species=species,
            name=f"{profile.name} ({profile.japanese_name})",
            current_locus=profile.initial_locus,
            lineage="Ancestor-80",
            generation=0,
            morphology=Morphology3D.initial_seed(profile.theme_color),
            tierra_vm=TierraVM.create_with_ancestor(),
        )

    def reproduce(
        self,
        daughter_genome: list[int],
        spawn_offset: tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> tuple[Organism, Organism]:
        """Tierra binary fission / budding:
        Parent divides into Parent + Offspring.
        Parent transfers 35% of its energy to endow the daughter.
        Offspring inherits mutated bytecode in its own Tierra VM.
        """
        from .tierra_vm import classify_genome, TierraVM
        lineage_name, diffs = classify_genome(daughter_genome)

        parent_energy = round(self.energy * 0.65, 1)
        daughter_energy = round(self.energy * 0.35, 1)

        parent_updated = self.model_copy(
            update={
                "energy": parent_energy,
            }
        )

        daughter_id = f"{self.species.value}-{uuid_suffix()}"
        profile = SPECIES_REGISTRY[self.species]

        # Daughter gets its own Tierra VM seeded with the daughter_genome in soup
        daughter_vm = TierraVM.create_with_ancestor()
        for i, b in enumerate(daughter_genome):
            daughter_vm.soup[daughter_vm.start_address + i] = int(b)
        daughter_vm.genome_size = len(daughter_genome)

        # Mutated strain visual styling
        tint_color = profile.theme_color
        if "Parasite" in lineage_name:
            tint_color = "#e63946"  # Parasites glow predatory crimson
        elif "Hyper" in lineage_name:
            tint_color = "#f72585"  # Hyper-replicators glow fluorescent neon
        elif diffs > 0:
            tint_color = _shift_hex_color(profile.theme_color, diffs * 30)

        from .morphology import CellNode, Morphology3D
        ox, oy, oz = spawn_offset
        seed_cell = CellNode(
            id="cell-origin",
            parent_id=None,
            x=ox,
            y=oy,
            z=oz,
            radius=1.8,
            color=tint_color,
            generation=0,
            source_title=f"{lineage_name} (Gen {self.generation + 1})",
        )
        daughter_morphology = Morphology3D(cells=[seed_cell], edges=[])

        daughter = Organism(
            id=daughter_id,
            species=self.species,
            name=f"{self.species.value.capitalize()}-{lineage_name} (Gen {self.generation + 1})",
            generation=self.generation + 1,
            lineage=lineage_name,
            parent_id=self.id,
            mutations_count=diffs,
            energy=daughter_energy,
            hunger_level=0.1,
            age_pulses=0,
            growth_score=round(self.growth_score * 0.4, 1),
            current_locus=self.current_locus,
            crystals_count=0,
            morphology=daughter_morphology,
            tierra_vm=daughter_vm,
        )

        return parent_updated, daughter

    def apply_metabolism(
        self,
        action: str,
        noul_quality: float,
        rationale: str,
        locus: str,
        energy_gain: float = 0.0,
        growth_gain: float = 0.0,
        cell_upkeep: float = 0.0,
        hazard_energy_drain: float = 0.0,
        new_morphology: Morphology3D | None = None,
        new_tierra_vm: TierraVM | None = None,
        new_peak_cells: int | None = None,
    ) -> Organism:
        """Immutable state transition representing one pulse of metabolism.

        A larger body costs more to maintain (`cell_upkeep`) and a hazard event can drain extra
        energy directly (`hazard_energy_drain`); both push energy toward the death threshold (<= 0).
        """
        # Baseline metabolic cost for living & thinking, plus the upkeep of the body's current size
        metabolic_burn = (1.5 if action == "rest_meditate" else 3.5) + cell_upkeep + hazard_energy_drain

        new_energy = max(0.0, min(100.0, self.energy - metabolic_burn + energy_gain))
        # When not assimilating substantial food, hunger naturally accumulates (+0.12 per pulse)
        hunger_delta = -0.30 if energy_gain > 5.0 else +0.12
        new_hunger = max(0.0, min(1.0, self.hunger_level + hunger_delta))
        new_growth = round(self.growth_score + growth_gain, 2)
        new_age = self.age_pulses + 1

        # Phase evolution threshold check
        new_phase = self.phase
        if new_growth >= 100.0 and self.crystals_count >= 20:
            new_phase = LifePhase.TRANSCENDENT
        elif new_growth >= 50.0 and self.crystals_count >= 10:
            new_phase = LifePhase.ADULT
        elif new_growth >= 25.0 and self.crystals_count >= 3:
            new_phase = LifePhase.JUVENILE

        now_str = datetime.now(timezone.utc).isoformat()
        new_thought = ThoughtRecord(
            pulse_index=new_age,
            action_chosen=action,
            rationale=rationale,
            noul_quality=round(noul_quality, 3),
            locus_visited=locus,
            timestamp=now_str,
        )

        return self.model_copy(
            update={
                "energy": round(new_energy, 1),
                "hunger_level": round(new_hunger, 2),
                "growth_score": new_growth,
                "age_pulses": new_age,
                "phase": new_phase,
                "current_locus": locus,
                "last_thought": new_thought,
                "last_pulse_at": now_str,
                "crystals_count": self.crystals_count + (1 if energy_gain > 5.0 else 0),
                "morphology": new_morphology or self.morphology,
                "tierra_vm": new_tierra_vm or self.tierra_vm,
                "peak_cells": self.peak_cells if new_peak_cells is None else new_peak_cells,
            }
        )


def uuid_suffix() -> str:
    import uuid
    return uuid.uuid4().hex[:6]


def _shift_hex_color(hex_str: str, deg: int) -> str:
    """Deterministically tint hex color for mutant strains."""
    try:
        r = int(hex_str[1:3], 16)
        g = int(hex_str[3:5], 16)
        b = int(hex_str[5:7], 16)
        step = (deg // 30) % 3
        if step == 1:
            r, g, b = (r + 40) % 255, (g + 20) % 255, (b + 60) % 255
        elif step == 2:
            r, g, b = (r + 60) % 255, (g + 50) % 255, (b + 10) % 255
        return f"#{r:02x}{g:02x}{b:02x}"
    except Exception:
        return hex_str
