from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.domain.knowledge_crystal import KnowledgeCrystal
from src.domain.organism import Organism
from src.domain.species import SPECIES_REGISTRY
from src.domain.tierra_vm import calculate_diversity_index


def build_vitals_snapshot(
    organisms: list[Organism],
    crystals: list[KnowledgeCrystal],
    jev_connected: bool,
) -> dict[str, Any]:
    """Public, read-only view of the ecosystem served to observers."""
    lineages = [o.lineage for o in organisms if o.lineage]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "jev_connected": jev_connected,
        "tierra_ecosystem": {
            "diversity_index": calculate_diversity_index(lineages),
            "parasite_count": sum(1 for o in organisms if "parasite" in (o.lineage or "").lower()),
            "total_living": len(organisms),
            "max_generation": max((o.generation for o in organisms), default=0),
        },
        "organisms": [_organism_view(o) for o in organisms],
        "recent_crystals": [c.to_summary_dict() for c in crystals],
    }


def _organism_view(o: Organism) -> dict[str, Any]:
    profile = SPECIES_REGISTRY[o.species]
    vm = o.tierra_vm
    return {
        "id": o.id,
        "species": o.species.value,
        "name": o.name,
        "lineage": o.lineage,
        "generation": o.generation,
        "parent_id": o.parent_id,
        "born_at": o.created_at,
        "mutations_count": o.mutations_count,
        "phase": o.phase.value,
        "energy": o.energy,
        "hunger_level": o.hunger_level,
        "growth_score": o.growth_score,
        "age_pulses": o.age_pulses,
        "current_locus": o.current_locus,
        "crystals_count": o.crystals_count,
        "cells_count": len(o.morphology.cells),
        "theme_color": profile.theme_color,
        "special_metric_name": profile.special_metric_name,
        "morphology": {
            "cells": [c.model_dump() for c in o.morphology.cells],
            "edges": [e.model_dump() for e in o.morphology.edges],
        },
        "tierra_vm": {
            "total_cycles": vm.total_cycles_executed,
            "ip": vm.ip,
            "divide_count": vm.divide_count,
            "genome_size": vm.genome_size,
            "borrowed_host_cycles": vm.borrowed_host_cycles,
            "error_count": vm.error_count,
            "start_address": vm.start_address,
            "registers": {"AX": vm.ax, "BX": vm.bx, "CX": vm.cx, "DX": vm.dx},
            "soup_preview": vm.get_soup_snippet(16),
        },
        "last_thought": o.last_thought.model_dump() if o.last_thought else None,
        "last_pulse_at": o.last_pulse_at,
    }
