from collections import Counter

from src.adapters.vital_repo import MAX_ORGANISMS_PER_WORLD, RECENT_CRYSTALS_KEY, DynamoDBVitalRepository
from src.domain.knowledge_crystal import KnowledgeCrystal
from src.domain.organism import Organism
from src.domain.species import SpeciesType


class CountingTable:
    def __init__(self):
        self.items, self.gets, self.puts = {}, Counter(), Counter()

    def put_item(self, Item):
        self.puts[Item["id"]] += 1
        self.items[Item["id"]] = Item

    def get_item(self, Key):
        self.gets[Key["id"]] += 1
        item = self.items.get(Key["id"])
        return {"Item": item} if item else {}


def repo_on(table):
    repo = DynamoDBVitalRepository(table_name="test")
    repo._table = table
    return repo


def child(species, n):
    return Organism.spawn(species).model_copy(update={"id": f"{species.value}-child-{n}", "generation": 1, "age_pulses": 10 + n})


async def test_one_read_and_one_write_per_world_with_reaper_applied_once():
    table = CountingTable()
    repo = repo_on(table)
    core = Organism.spawn(SpeciesType.GAIA, custom_id="gaia-core")
    await repo.save_world_colony(SpeciesType.GAIA, [core] + [child(SpeciesType.GAIA, n) for n in range(3)])
    table.gets.clear(), table.puts.clear()

    newborn = Organism.spawn(SpeciesType.GAIA).model_copy(update={"id": "gaia-newborn", "generation": 2})
    cosmo = Organism.spawn(SpeciesType.COSMO, custom_id="cosmo-core")
    await repo.save_organisms([core.model_copy(update={"age_pulses": 1}), cosmo, newborn])

    assert table.gets == Counter({"gaia-core": 1, "cosmo-core": 1})
    assert table.puts == Counter({"gaia-core": 1, "cosmo-core": 1})
    colony = [Organism.model_validate_json(raw) for raw in table.items["gaia-core"]["colony"]]
    assert len(colony) == MAX_ORGANISMS_PER_WORLD
    assert "gaia-core" in {o.id for o in colony} and "gaia-newborn" in {o.id for o in colony}
    assert "gaia-child-2" not in {o.id for o in colony}  # oldest offspring reaped


async def test_recent_crystal_list_written_once_per_batch():
    table = CountingTable()
    crystals = [KnowledgeCrystal(organism_id="x", species="gaia", source_url="https://e.org", concept_title=f"c{i}",
                                 core_insight="i", nutritional_value=1.0) for i in range(3)]
    await repo_on(table).save_crystals(crystals)
    assert table.puts[RECENT_CRYSTALS_KEY] == 1
    assert sum(1 for k in table.puts if k.startswith("crystal#")) == 3
