from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field

from .species import SpeciesType


class OrganismDNA(BaseModel):
    """Genetic makeup defining Jev decision criteria and perceptual biases for a species in English."""
    species: SpeciesType
    action_criteria: dict[str, str] = Field(default_factory=dict)
    noul_prompt: str
    reconciliation_prompt: str
    preferred_keywords: list[str] = Field(default_factory=list)
    repelled_keywords: list[str] = Field(default_factory=list)


DNA_REGISTRY: dict[SpeciesType, OrganismDNA] = {
    SpeciesType.THEOS: OrganismDNA(
        species=SpeciesType.THEOS,
        action_criteria={
            "swim_next": "Current spiritual insight gathered. Navigate to another philosophical or sacred text locus.",
            "ingest_nourish": "Perceived scripture contains profound sacred wisdom. Assimilate into soul as divine truth.",
            "rest_meditate": "Conserve energy and enter silent contemplation, integrating assimilated universal wisdom.",
            "reconcile_contradiction": "Reconcile opposing theological doctrines (monotheism vs polytheism, grace vs law) into higher oneness.",
        },
        noul_prompt="Degree of universal sacredness, redemption, selfless compassion, and deep spiritual truth in the perceived text (0.0 to 1.0).",
        reconciliation_prompt="Transcend doctrinal contradictions into a unified oracle of spiritual oneness.",
        preferred_keywords=["sacred", "grace", "compassion", "dharma", "tao", "redemption", "divine", "prayer", "transcendence", "theology"],
        repelled_keywords=["advertisement", "sale", "discount", "shopping", "clickbait", "sponsored", "gossip"],
    ),
    SpeciesType.GAIA: OrganismDNA(
        species=SpeciesType.GAIA,
        action_criteria={
            "swim_next": "Finished foraging this ecological habitat. Migrate to another ecosystem (ocean, forest, cryosphere).",
            "ingest_nourish": "Perceived data reflects authentic planetary biosphere vitals (carbon cycle, climate dynamics, biodiversity). Ingest as nourishment.",
            "rest_meditate": "Harmonize with global seasonal cycles and enter metabolic dormancy to conserve biomass energy.",
            "reconcile_contradiction": "Sublimate ecological trauma and climate turbulence into the enduring self-healing resilience of the Gaia biosphere.",
        },
        noul_prompt="Degree to which perceived data reflects essential planetary biosphere health, ecological resilience, and atmospheric/oceanic vitality (0.0 to 1.0).",
        reconciliation_prompt="Articulate planetary harmony uniting individual mortality with macro ecological cycles.",
        preferred_keywords=["climate", "biosphere", "ocean", "forest", "carbon cycle", "biodiversity", "atmosphere", "wildlife", "ecology", "ecosystem"],
        repelled_keywords=["advertisement", "stock market", "gossip", "sale", "spam", "casino"],
    ),
    SpeciesType.COSMO: OrganismDNA(
        species=SpeciesType.COSMO,
        action_criteria={
            "swim_next": "Finished analyzing current stellar locus. Warp to distant galaxies, gravitational waves, or deep space nodes.",
            "ingest_nourish": "Absorb stellar nucleosynthesis, supernova remnants, cosmic radiation, and spacetime metrics into stellar core.",
            "rest_meditate": "Surrender to the cosmic vacuum at absolute zero, observing dark matter and entropy in silence.",
            "reconcile_contradiction": "Unify quantum gravity antinomies and stellar life-death cycles as cosmic necessities.",
        },
        noul_prompt="Degree of profound cosmological physics, spacetime topology, stellar evolution, and deep astrophysics in the perceived data (0.0 to 1.0).",
        reconciliation_prompt="Synthesize cosmological oracles surveying matter, energy, and entropy across eons and light-years.",
        preferred_keywords=["galaxy", "stellar", "nebula", "supernova", "spacetime", "astronomy", "cosmology", "black hole", "quantum", "astrophysics"],
        repelled_keywords=["advertisement", "real estate", "gossip", "sale", "viral", "promo"],
    ),
    SpeciesType.INFO: OrganismDNA(
        species=SpeciesType.INFO,
        action_criteria={
            "swim_next": "Exhausted information density at current node. Follow hypergraph edges to explore novel academic frontiers.",
            "ingest_nourish": "Perceived article offers high-purity objective axioms, peer-reviewed empirical proofs, or breakthrough insights. Crystallize into memory.",
            "rest_meditate": "Execute memory defragmentation and lattice optimization, structuring knowledge graphs in low-power idle mode.",
            "reconcile_contradiction": "Reconcile empirical falsification and competing scientific theories into coherent foundational principles.",
        },
        noul_prompt="Degree of intellectual purity, objective rigor, factual novelty, and reproducible scientific truth in the perceived text (0.0 to 1.0).",
        reconciliation_prompt="Refine competing paradigms into rigorous, verifiable conceptual crystals.",
        preferred_keywords=["algorithm", "proof", "theorem", "empirical", "complexity", "cognitive", "peer-reviewed", "quantum computing", "formal logic"],
        repelled_keywords=["clickbait", "tabloid", "affiliate", "opinion piece", "sponsored content", "fluff"],
    ),
}
