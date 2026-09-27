import random
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from src.adapters.jev_brain import ActionRequest, GrowthRequest, JevBrain, LocusRequest
from src.adapters.vital_repo import InMemoryVitalRepository
from src.domain.organism import Organism
from src.domain.species import SpeciesType
from src.domain.tierra_vm import ANCESTOR_80_GENOME
from src.usecases.heartbeat import HeartbeatUsecase, _PulsePlan


class OfflineForager:
    async def forage_locus(self, species, locus):
        return {"title": "Sacred compassion", "content": "sacred compassion grace " * 40,
                "url": locus, "candidate_links": ["https://example.org/next"]}


class CountingBrain:
    is_connected = True

    def __init__(self):
        self.action_calls, self.growth_calls = [], []

    def decide_actions(self, requests):
        self.action_calls.append(requests)
        return {r.key: ("ingest_nourish", 0.8, "stub") for r in requests}

    def decide_growth_and_locus(self, growths, loci):
        self.growth_calls.append((growths, loci))
        sprouts = {g.key: [("latest_tip", 50.0, 35.0, 8.0, 1.5, "#ffffff")] * g.sprouts for g in growths}
        return sprouts, {l.key: l.current_locus for l in loci}


async def test_every_organism_advances_with_two_jev_calls_regardless_of_population():
    repo = InMemoryVitalRepository()
    population = await repo.get_all_organisms()
    brain = CountingBrain()

    results = await HeartbeatUsecase(repo, brain, OfflineForager()).pulse_all()

    assert len(results) == len(population)
    assert len(brain.action_calls) == 1 and len(brain.growth_calls) == 1
    assert {r.key for r in brain.action_calls[0]} == {o.id for o in population}
    assert all(o.age_pulses == 1 for o in await repo.get_all_organisms())


def mature(species=SpeciesType.GAIA, energy=95.0):
    org = Organism.spawn(species)
    morph = org.morphology
    for _ in range(3):
        morph = morph.grow_cell(anchor_choice="latest_tip", azimuth_deg=0, elevation_deg=0, growth_distance=5,
                                cell_radius=1, cell_color="#fff", source_title="t")
    return org.model_copy(update={"energy": energy, "morphology": morph})


def plan_for(org):
    return _PulsePlan(org, {"title": "t", "content": "c"}, "rest_meditate", 0.5, "r", 0.0, 0.0,
                      org.current_locus, divide_genomes=[list(map(int, ANCESTOR_80_GENOME))])


class FixedRng(random.Random):
    def __init__(self, value):
        super().__init__()
        self.value = value

    def random(self):
        return self.value


def test_birth_requires_the_probability_roll():
    parent = mature()
    lucky = HeartbeatUsecase(None, None, None, rng=FixedRng(0.0))
    unlucky = HeartbeatUsecase(None, None, None, rng=FixedRng(0.5))
    assert lucky._develop(plan_for(parent), [], None, [parent], set())[1] is not None
    assert unlucky._develop(plan_for(parent), [], None, [parent], set())[1] is None


def test_at_most_one_birth_per_world_per_day():
    parent = mature()
    uc = HeartbeatUsecase(None, None, None, rng=FixedRng(0.0))

    young = Organism.spawn(SpeciesType.GAIA).model_copy(update={
        "generation": 1, "created_at": (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()})
    old = young.model_copy(update={"created_at": (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat()})
    other_world = young.model_copy(update={"species": SpeciesType.COSMO})

    assert uc._develop(plan_for(parent), [], None, [parent, young], set())[1] is None
    assert uc._develop(plan_for(parent), [], None, [parent, old, other_world], set())[1] is not None
    assert uc._develop(plan_for(parent), [], None, [parent], {SpeciesType.GAIA})[1] is None


def answer(**kw):
    return SimpleNamespace(**kw)


class FakeClient:
    def __init__(self, respond):
        self.calls, self.respond = [], respond

    def system_one(self, state, questions):
        self.calls.append((state, questions))
        return SimpleNamespace(answers=self.respond(questions))


def brain_with(client):
    brain = JevBrain.__new__(JevBrain)
    brain.api_key, brain._client = "test", client
    return brain


def test_decide_actions_is_one_call_mapped_back_per_organism():
    def respond(questions):
        out = {}
        for name in questions:
            i = name.split("_")[1]
            out[name] = answer(choice="swim_next" if i == "0" else "ingest_nourish", confidence=0.8) if name.startswith("action") else answer(noul=0.1 * (int(i) + 1))
        return out

    client = FakeClient(respond)
    requests = [ActionRequest(key=f"org-{i}", species=SpeciesType.GAIA, perception="p", energy=50, hunger=0.3) for i in range(3)]
    decisions = brain_with(client).decide_actions(requests)

    assert len(client.calls) == 1
    assert set(client.calls[0][0]) == {"organism_0", "organism_1", "organism_2"}
    assert decisions["org-0"][0] == "swim_next" and decisions["org-2"][0] == "ingest_nourish"
    assert abs(decisions["org-2"][1] - 0.3) < 1e-9


def test_growth_and_locus_share_one_call_and_fall_back_on_errors():
    def respond(questions):
        out = {}
        for name in questions:
            if name.startswith("vector"):
                out[name] = answer(choice="polar_zenith")
            elif name.startswith("anchor"):
                out[name] = answer(choice="nucleus_origin")
            elif name.startswith("scale"):
                out[name] = answer(noul=1.0)
            else:
                out[name] = answer(choice="follow_1")
        return out

    client = FakeClient(respond)
    growth = GrowthRequest(key="g", species=SpeciesType.COSMO, prey_title="t", prey_content="c", cells_count=3, energy=60, sprouts=2)
    locus = LocusRequest(key="g", species=SpeciesType.COSMO, prey_title="t", prey_content="c",
                         candidate_links=["https://a.example/x", "https://b.example/y"], current_locus="https://home.example/")
    sprouts, loci = brain_with(client).decide_growth_and_locus([growth], [locus])

    assert len(client.calls) == 1
    assert [s[:3] for s in sprouts["g"]] == [("nucleus_origin", 20.0, 65.0)] * 2
    assert loci["g"] == "https://b.example/y"

    failing = FakeClient(lambda q: (_ for _ in ()).throw(RuntimeError("boom")))
    sprouts, loci = brain_with(failing).decide_growth_and_locus([growth], [locus])
    assert len(sprouts["g"]) == 2 and loci["g"] in locus.candidate_links + [locus.current_locus]
