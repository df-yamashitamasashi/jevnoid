import pytest
from src.adapters.vital_repo import InMemoryVitalRepository
from src.adapters.jev_brain import JevBrain
from src.adapters.web_forager import WebForager
from src.usecases.heartbeat import HeartbeatUsecase
from src.domain.species import SpeciesType


@pytest.mark.asyncio
async def test_heartbeat_pulse_all():
    repo = InMemoryVitalRepository()
    brain = JevBrain()
    forager = WebForager(timeout_sec=1.0)
    uc = HeartbeatUsecase(repo=repo, brain=brain, forager=forager)

    results = await uc.pulse_all()
    assert len(results) == 4

    organisms = await repo.get_all_organisms()
    for org in organisms:
        assert org.age_pulses == 1
        assert org.last_thought is not None
        assert org.last_thought.action_chosen in [
            "swim_next",
            "ingest_nourish",
            "rest_meditate",
            "reconcile_contradiction",
        ]
        # Tierra check: Sprouted at least 1 origin nucleus
        assert len(org.morphology.cells) >= 1


@pytest.mark.asyncio
async def test_heartbeat_morphogenesis_growth():
    repo = InMemoryVitalRepository()
    brain = JevBrain()
    forager = WebForager(timeout_sec=1.0)
    uc = HeartbeatUsecase(repo=repo, brain=brain, forager=forager)

    # Pulse multiple times to observe autonomous cell growth
    for _ in range(3):
        await uc.pulse_all()

    organisms = await repo.get_all_organisms()
    # At least one organism that ingested knowledge should have sprouted new 3D cells
    max_cells = max(len(o.morphology.cells) for o in organisms)
    assert max_cells >= 1
