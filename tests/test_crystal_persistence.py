from src.adapters.vital_repo import RECENT_CRYSTALS_KEY, RECENT_CRYSTALS_LIMIT, DynamoDBVitalRepository
from src.domain.knowledge_crystal import KnowledgeCrystal


class FakeTable:
    def __init__(self):
        self.items = {}

    def put_item(self, Item):
        self.items[Item["id"]] = Item

    def get_item(self, Key):
        item = self.items.get(Key["id"])
        return {"Item": item} if item else {}


def crystal(title):
    return KnowledgeCrystal(organism_id="gaia-core", species="gaia", source_url="https://example.org",
                            concept_title=title, core_insight="insight", nutritional_value=10.0)


def repo_on(table):
    repo = DynamoDBVitalRepository(table_name="test")
    repo._table = table
    return repo


async def test_cold_start_save_keeps_previously_persisted_crystals():
    table = FakeTable()
    first = repo_on(table)
    await first.save_crystal(crystal("old-1"))
    await first.save_crystal(crystal("old-2"))

    restarted = repo_on(table)
    new = crystal("new")
    await restarted.save_crystal(new)

    assert [c.concept_title for c in await restarted.get_crystals()] == ["new", "old-2", "old-1"]
    assert f"crystal#{new.crystal_id}" in table.items
    assert table.items[f"crystal#{new.crystal_id}"]["timestamp"] == new.created_at


async def test_restarted_reader_sees_recent_crystals():
    table = FakeTable()
    await repo_on(table).save_crystal(crystal("persisted"))
    assert [c.concept_title for c in await repo_on(table).get_crystals()] == ["persisted"]


async def test_recent_list_is_capped():
    table = FakeTable()
    repo = repo_on(table)
    for i in range(RECENT_CRYSTALS_LIMIT + 5):
        await repo.save_crystal(crystal(f"c{i}"))
    assert len(table.items[RECENT_CRYSTALS_KEY]["crystals"]) == RECENT_CRYSTALS_LIMIT
    assert (await repo_on(table).get_crystals())[0].concept_title == f"c{RECENT_CRYSTALS_LIMIT + 4}"
