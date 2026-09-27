from __future__ import annotations

from datetime import datetime, timezone
import uuid
from pydantic import BaseModel, Field


class KnowledgeCrystal(BaseModel):
    """A crystallized fragment of distilled knowledge assimilated into an organism's body."""
    crystal_id: str = Field(default_factory=lambda: f"cryst-{uuid.uuid4().hex[:8]}")
    organism_id: str
    species: str
    source_url: str
    concept_title: str
    core_insight: str
    tags: list[str] = Field(default_factory=list)
    nutritional_value: float  # Energy restored to the organism (e.g. 5.0 - 25.0)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_summary_dict(self) -> dict[str, str | float | list[str]]:
        return {
            "crystal_id": self.crystal_id,
            "organism_id": self.organism_id,
            "species": self.species,
            "source_url": self.source_url,
            "concept_title": self.concept_title,
            "core_insight": self.core_insight,
            "tags": self.tags,
            "nutritional_value": self.nutritional_value,
            "created_at": self.created_at,
        }
