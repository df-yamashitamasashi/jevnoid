from __future__ import annotations

from typing import Any
from src.adapters.jev_brain import JevBrain
from src.adapters.vital_repo import VitalRepository


class TelepathyUsecase:
    """Handles communication between human observers and organisms."""

    def __init__(self, repo: VitalRepository, brain: JevBrain) -> None:
        self.repo = repo
        self.brain = brain

    async def converse(self, organism_id: str, user_message: str) -> dict[str, Any]:
        organism = await self.repo.get_organism(organism_id)
        if not organism:
            return {"error": f"Organism with ID '{organism_id}' not found."}

        # Fetch recent knowledge crystals assimilated by this organism
        all_crystals = await self.repo.get_crystals(limit=50)
        species_crystals = [
            c
            for c in all_crystals
            if c.organism_id == organism.id or c.species == organism.species.value
        ]

        reply = self.brain.generate_telepathy_response(
            species=organism.species,
            user_message=user_message,
            growth_score=organism.growth_score,
            phase=organism.phase.value,
            crystals=species_crystals,
            energy=organism.energy,
        )

        return {
            "organism_id": organism.id,
            "species": organism.species.value,
            "phase": organism.phase.value,
            "reply": reply,
            "crystals_referred_count": len(species_crystals),
        }
