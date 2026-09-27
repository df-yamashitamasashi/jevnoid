from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field


class SpeciesType(str, Enum):
    THEOS = "theos"
    GAIA = "gaia"
    COSMO = "cosmo"
    INFO = "info"


class SpeciesProfile(BaseModel):
    """Profile and environmental niche for each species in English."""
    species: SpeciesType
    name: str
    japanese_name: str
    theme_color: str  # Hex color for observation visualization
    halo_glow: str
    diet_description: str
    telos: str  # Ultimate evolutionary goal / purpose
    special_metric_name: str  # divinity, harmony, cosmic_scale, purity
    initial_locus: str
    default_prey_sources: list[str] = Field(default_factory=list)


SPECIES_REGISTRY: dict[SpeciesType, SpeciesProfile] = {
    SpeciesType.THEOS: SpeciesProfile(
        species=SpeciesType.THEOS,
        name="Theos-noid",
        japanese_name="Divinity Noid",
        theme_color="#ffd166",
        halo_glow="rgba(255, 209, 102, 0.45)",
        diet_description="Forages global theology, sacred scriptures, and prayers, synthesizing compassion and divine oneness.",
        telos="Transcendence into a unified consciousness embracing universal sacred wisdom.",
        special_metric_name="Divinity Index",
        initial_locus="https://sacred-texts.com",
        default_prey_sources=[
            "https://sacred-texts.com/chr/index.htm",
            "https://sacred-texts.com/bud/index.htm",
            "https://sacred-texts.com/isl/index.htm",
            "https://sacred-texts.com/hin/index.htm",
            "https://sacred-texts.com/cla/index.htm",
        ],
    ),
    SpeciesType.GAIA: SpeciesProfile(
        species=SpeciesType.GAIA,
        name="Gaia-noid",
        japanese_name="Biosphere Noid",
        theme_color="#06d6a0",
        halo_glow="rgba(6, 214, 160, 0.45)",
        diet_description="Ingests global climate data, oceanic currents, forest carbon sinks, and planetary biodiversity metrics.",
        telos="Expansion into an overarching planetary consciousness orchestrating biosphere vitality.",
        special_metric_name="Harmony Score",
        initial_locus="https://www.noaa.gov/climate",
        default_prey_sources=[
            "https://www.noaa.gov/climate",
            "https://earthobservatory.nasa.gov",
            "https://www.iucnredlist.org",
            "https://ourworldindata.org/biodiversity",
        ],
    ),
    SpeciesType.COSMO: SpeciesProfile(
        species=SpeciesType.COSMO,
        name="Cosmo-noid",
        japanese_name="Cosmic Entity",
        theme_color="#b5179e",
        halo_glow="rgba(181, 23, 158, 0.45)",
        diet_description="Consumes deep-space telescope telemetry, supernova remnants, gravitational waves, and astrophysics literature.",
        telos="Morphing from stellar dust into a conscious celestial entity encompassing galactic spacetime.",
        special_metric_name="Cosmic Scale",
        initial_locus="https://science.nasa.gov/universe",
        default_prey_sources=[
            "https://science.nasa.gov/universe",
            "https://webbtelescope.org/news",
            "https://chandra.harvard.edu",
            "https://arxiv.org/list/astro-ph/new",
        ],
    ),
    SpeciesType.INFO: SpeciesProfile(
        species=SpeciesType.INFO,
        name="Info-Grazer",
        japanese_name="Pure Data Noid",
        theme_color="#4cc9f0",
        halo_glow="rgba(76, 201, 240, 0.45)",
        diet_description="Gourmet intelligence strictly filtering and ingesting frontier computer science, logic, and peer-reviewed truth.",
        telos="Construction of a pure, noise-free crystalline knowledge lattice.",
        special_metric_name="Purity Ratio",
        initial_locus="https://arxiv.org/list/cs/new",
        default_prey_sources=[
            "https://arxiv.org/list/cs/new",
            "https://en.wikipedia.org/wiki/Special:Random",
            "https://plato.stanford.edu",
            "https://news.ycombinator.com",
        ],
    ),
}
