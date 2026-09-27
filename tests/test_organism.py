import pytest
from src.domain.species import SpeciesType, SPECIES_REGISTRY
from src.domain.organism import Organism, LifePhase
from src.domain.knowledge_crystal import KnowledgeCrystal
from src.domain.dna import DNA_REGISTRY


def test_organism_spawn():
    org = Organism.spawn(SpeciesType.THEOS, custom_id="theos-test")
    assert org.id == "theos-test"
    assert org.species == SpeciesType.THEOS
    assert org.phase == LifePhase.LARVA
    assert org.energy == 80.0
    assert org.current_locus == SPECIES_REGISTRY[SpeciesType.THEOS].initial_locus
    # Tierra Requirement: Strictly spawns with 1 origin nucleus
    assert len(org.morphology.cells) == 1
    assert org.morphology.cells[0].id == "cell-origin"
    assert org.morphology.cells[0].x == 0.0
    assert org.morphology.cells[0].y == 0.0
    assert org.morphology.cells[0].z == 0.0


def test_morphology_3d_growth():
    org = Organism.spawn(SpeciesType.COSMO, custom_id="cosmo-test")
    assert len(org.morphology.cells) == 1

    # Grow a cell in 3D space
    grown_morph = org.morphology.grow_cell(
        anchor_choice="latest_tip",
        azimuth_deg=90.0,
        elevation_deg=30.0,
        growth_distance=10.0,
        cell_radius=1.5,
        cell_color="#b5179e",
        source_title="ジェイムズ・ウェッブ初期銀河観測",
    )
    assert len(grown_morph.cells) == 2
    assert len(grown_morph.edges) == 1
    new_cell = grown_morph.cells[1]
    assert new_cell.parent_id == "cell-origin"
    assert new_cell.radius == 1.5
    # y should be positive due to elevation
    assert new_cell.y > 0.0


def test_organism_immutable_metabolism():
    org = Organism.spawn(SpeciesType.GAIA, custom_id="gaia-test")
    updated = org.apply_metabolism(
        action="ingest_nourish",
        noul_quality=0.9,
        rationale="テスト同化",
        locus="https://test.example.com",
        energy_gain=15.0,
        growth_gain=10.0,
    )

    # Immutability check: original remains untouched
    assert org.age_pulses == 0
    assert org.energy == 80.0

    # New instance has advanced
    assert updated.age_pulses == 1
    assert updated.growth_score == 20.0
    assert updated.energy > 85.0
    assert updated.last_thought is not None
    assert updated.last_thought.action_chosen == "ingest_nourish"
    assert updated.last_thought.noul_quality == 0.9


def test_knowledge_crystal_creation():
    crystal = KnowledgeCrystal(
        organism_id="cosmo-test",
        species="cosmo",
        source_url="https://nasa.gov",
        concept_title="超新星元素合成",
        core_insight="星の死が炭素と鉄を宇宙に散布する。",
        tags=["supernova", "cosmology"],
        nutritional_value=18.0,
    )
    summary = crystal.to_summary_dict()
    assert summary["organism_id"] == "cosmo-test"
    assert summary["concept_title"] == "超新星元素合成"
    assert summary["nutritional_value"] == 18.0


def test_dna_registry_completeness():
    for species in [SpeciesType.THEOS, SpeciesType.GAIA, SpeciesType.COSMO, SpeciesType.INFO]:
        assert species in DNA_REGISTRY
        dna = DNA_REGISTRY[species]
        assert "swim_next" in dna.action_criteria
        assert "ingest_nourish" in dna.action_criteria
        assert len(dna.preferred_keywords) > 0
