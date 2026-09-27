from __future__ import annotations

import os
import time
from typing import Protocol, Any
from datetime import datetime, timezone
from src.domain.knowledge_crystal import KnowledgeCrystal
from src.domain.organism import Organism
from src.domain.species import SpeciesType

CORE_ORGANISM_IDS = ["theos-core", "gaia-core", "cosmo-core", "info-core"]
SPECIES_MAP = {
    "theos-core": SpeciesType.THEOS,
    "gaia-core": SpeciesType.GAIA,
    "cosmo-core": SpeciesType.COSMO,
    "info-core": SpeciesType.INFO,
}


RECENT_CRYSTALS_KEY = "crystals#recent"
RECENT_CRYSTALS_LIMIT = 25


class VitalRepository(Protocol):
    """Protocol for storing and retrieving organism state and knowledge crystals."""

    async def get_all_organisms(self) -> list[Organism]: ...
    async def get_organism(self, organism_id: str) -> Organism | None: ...
    async def save_organism(self, organism: Organism) -> None: ...
    async def save_organisms(self, organisms: list[Organism], removals: list[Organism] | None = None) -> None: ...
    async def save_crystal(self, crystal: KnowledgeCrystal) -> None: ...
    async def save_crystals(self, crystals: list[KnowledgeCrystal]) -> None: ...
    async def get_crystals(self, limit: int = 50) -> list[KnowledgeCrystal]: ...


def calculate_reaper_score(org: Organism) -> float:
    """Ray's 1990 Reaper Queue Priority: Highest score gets reaped first.
    
    Penalizes organisms with execution/protection errors and advanced age,
    while rewarding high metabolic energy.
    """
    err_count = org.tierra_vm.error_count if org.tierra_vm else 0
    return (err_count * 10.0) + (org.age_pulses * 1.0) - ((org.energy / 100.0) * 5.0)


MAX_ORGANISMS_PER_WORLD = 4  # Ecological carrying capacity per world (Ray 1990)


class InMemoryVitalRepository:
    """Thread-safe in-memory repository for local development and demonstration."""

    def __init__(self) -> None:
        self._organisms: dict[str, Organism] = {}
        self._crystals: list[KnowledgeCrystal] = []
        self._initialize_default_organisms()

    def _initialize_default_organisms(self) -> None:
        for s in [SpeciesType.THEOS, SpeciesType.GAIA, SpeciesType.COSMO, SpeciesType.INFO]:
            org = Organism.spawn(species=s, custom_id=f"{s.value}-core")
            self._organisms[org.id] = org

    async def get_all_organisms(self) -> list[Organism]:
        return list(self._organisms.values())

    async def get_organism(self, organism_id: str) -> Organism | None:
        return self._organisms.get(organism_id)

    async def save_organism(self, organism: Organism) -> None:
        self._organisms[organism.id] = organism
        # Reaper check per world (carrying capacity)
        same_species = [o for o in self._organisms.values() if o.species == organism.species]
        if len(same_species) > MAX_ORGANISMS_PER_WORLD:
            non_cores = [o for o in same_species if not o.id.endswith("-core")]
            if non_cores:
                reaped = max(non_cores, key=calculate_reaper_score)
                self._organisms.pop(reaped.id, None)

    async def save_organisms(self, organisms: list[Organism], removals: list[Organism] | None = None) -> None:
        for organism in organisms:
            await self.save_organism(organism)
        for dead in (removals or []):
            self._organisms.pop(dead.id, None)

    async def save_crystal(self, crystal: KnowledgeCrystal) -> None:
        self._crystals.insert(0, crystal)
        if len(self._crystals) > 200:
            self._crystals.pop()

    async def save_crystals(self, crystals: list[KnowledgeCrystal]) -> None:
        for crystal in crystals:
            await self.save_crystal(crystal)

    async def get_crystals(self, limit: int = 50) -> list[KnowledgeCrystal]:
        return self._crystals[:limit]


class DynamoDBVitalRepository:
    """Production DynamoDB repository with world-level colony encapsulation.
    
    Cost & Traffic Defenses:
      1. Aggressive In-Memory Cache (TTL 30s): 99.9% of user HTTP requests read from Lambda memory (0 RCU).
      2. Point Query by 4 World Keys: Reads only "theos-core", "gaia-core", "cosmo-core", "info-core" (4 queries).
      3. Controlled Write Rate: Exactly 1 write occurs ONLY during the 10-minute EventBridge pulse.
      4. Ecological Carrying Capacity: Max 4 organisms per world (Ray Reaper algorithm).
    """

    def __init__(self, table_name: str | None = None, region_name: str = "ap-northeast-1") -> None:
        self.table_name = table_name or os.environ.get("VITALS_TABLE", "JevnoidVitals")
        self.region_name = region_name
        self._table = None
        self._cache_organisms: dict[str, Organism] = {}
        self._cache_time: float = 0.0
        self._cache_crystals: list[KnowledgeCrystal] = []
        self._crystals_loaded = False
        self.cache_ttl: float = 30.0  # 30 seconds memory cache

    @property
    def table(self) -> Any:
        if self._table is None:
            import boto3
            dynamodb = boto3.resource("dynamodb", region_name=self.region_name)
            self._table = dynamodb.Table(self.table_name)
        return self._table

    async def get_all_organisms(self) -> list[Organism]:
        now = time.time()
        # 1. In-memory cache hit
        if self._cache_organisms and (now - self._cache_time < self.cache_ttl):
            return list(self._cache_organisms.values())

        # 2. Fetch the 4 world colonies by primary key
        all_living: list[Organism] = []
        self._cache_organisms.clear()

        for oid in CORE_ORGANISM_IDS:
            species = SPECIES_MAP[oid]
            try:
                res = self.table.get_item(Key={"id": oid})
                item = res.get("Item")
                world_orgs: list[Organism] = []
                if item and "colony" in item and item["colony"]:
                    world_orgs = [Organism.model_validate_json(raw) for raw in item["colony"] if raw]
                elif item and "payload" in item:
                    world_orgs = [Organism.model_validate_json(item["payload"])]

                if not world_orgs:
                    # Spawn original Ancestor for this world
                    ancestor = Organism.spawn(species=species, custom_id=oid)
                    world_orgs = [ancestor]
                    await self.save_world_colony(species, world_orgs)

                for org in world_orgs:
                    all_living.append(org)
                    self._cache_organisms[org.id] = org

            except Exception as e:
                print(f"[DynamoDBVitalRepository] get_all_organisms error for {oid}: {e}")

        self._cache_time = now
        return all_living

    async def get_organism(self, organism_id: str) -> Organism | None:
        now = time.time()
        if organism_id in self._cache_organisms and (now - self._cache_time < self.cache_ttl):
            return self._cache_organisms[organism_id]

        all_orgs = await self.get_all_organisms()
        for org in all_orgs:
            if org.id == organism_id:
                return org
        return None

    async def save_organism(self, organism: Organism) -> None:
        await self.save_organisms([organism])

    async def save_organisms(self, organisms: list[Organism], removals: list[Organism] | None = None) -> None:
        """Upsert/remove organisms with one read and one write per affected world, applying the Reaper once.

        Order matters: organisms listed later (e.g. newborns) are appended after earlier updates.
        """
        by_species: dict[SpeciesType, list[Organism]] = {}
        remove_ids_by_species: dict[SpeciesType, set[str]] = {}
        for organism in organisms:
            by_species.setdefault(organism.species, []).append(organism)
            self._cache_organisms[organism.id] = organism
        for dead in (removals or []):
            remove_ids_by_species.setdefault(dead.species, set()).add(dead.id)
            self._cache_organisms.pop(dead.id, None)
        self._cache_time = time.time()

        for species in set(by_species) | set(remove_ids_by_species):
            updates = by_species.get(species, [])
            remove_ids = remove_ids_by_species.get(species, set())
            world_key = f"{species.value}-core"
            try:
                item = self.table.get_item(Key={"id": world_key}).get("Item")
                world_orgs: list[Organism] = []
                if item and "colony" in item and item["colony"]:
                    world_orgs = [Organism.model_validate_json(raw) for raw in item["colony"] if raw]
                elif item and "payload" in item:
                    world_orgs = [Organism.model_validate_json(item["payload"])]

                world_orgs = [o for o in world_orgs if o.id not in remove_ids]

                position = {o.id: i for i, o in enumerate(world_orgs)}
                for organism in updates:
                    if organism.id in position:
                        world_orgs[position[organism.id]] = organism
                    else:
                        position[organism.id] = len(world_orgs)
                        world_orgs.append(organism)

                # Tierra Reaper: over carrying capacity, reap the worst-scoring offspring (never the core ancestor)
                while len(world_orgs) > MAX_ORGANISMS_PER_WORLD:
                    non_cores = [o for o in world_orgs if o.id != world_key]
                    if not non_cores:
                        break
                    reaped = max(non_cores, key=calculate_reaper_score)
                    world_orgs = [o for o in world_orgs if o.id != reaped.id]
                    self._cache_organisms.pop(reaped.id, None)

                await self.save_world_colony(species, world_orgs)
            except Exception as e:
                print(f"[DynamoDBVitalRepository] save_organisms error for {world_key}: {e}")

    async def save_world_colony(self, species: SpeciesType, colony: list[Organism]) -> None:
        """Atomic write of the world's population into its single key in DynamoDB."""
        world_key = f"{species.value}-core"
        try:
            self.table.put_item(
                Item={
                    "id": world_key,
                    "type": "world_colony",
                    "species": species.value,
                    "colony": [o.model_dump_json() for o in colony],
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            for o in colony:
                self._cache_organisms[o.id] = o
        except Exception as e:
            print(f"[DynamoDBVitalRepository] save_world_colony error for {world_key}: {e}")

    async def save_crystal(self, crystal: KnowledgeCrystal) -> None:
        await self.save_crystals([crystal])

    async def save_crystals(self, crystals: list[KnowledgeCrystal]) -> None:
        """Archive each crystal and rewrite the recent-crystals list once, however many crystals formed."""
        if not crystals:
            return
        # Load the persisted list first, or a cold start would overwrite it with only these crystals.
        self._ensure_recent_crystals_loaded()
        self._cache_crystals[:0] = list(reversed(crystals))
        del self._cache_crystals[RECENT_CRYSTALS_LIMIT:]

        try:
            for crystal in crystals:
                self.table.put_item(
                    Item={
                        "id": f"crystal#{crystal.crystal_id}",
                        "type": "crystal",
                        "species": crystal.species,
                        "payload": crystal.model_dump_json(),
                        "timestamp": crystal.created_at,
                    }
                )
            self.table.put_item(
                Item={
                    "id": RECENT_CRYSTALS_KEY,
                    "type": "crystal_index",
                    "crystals": [c.model_dump_json() for c in self._cache_crystals],
                }
            )
        except Exception as e:
            print(f"[DynamoDBVitalRepository] save_crystal error: {e}")

    async def get_crystals(self, limit: int = 50) -> list[KnowledgeCrystal]:
        self._ensure_recent_crystals_loaded()
        return self._cache_crystals[:limit]

    def _ensure_recent_crystals_loaded(self) -> None:
        """One point read per container: recent crystals survive Lambda cold starts without scanning the table."""
        if self._crystals_loaded:
            return
        self._crystals_loaded = True
        try:
            item = self.table.get_item(Key={"id": RECENT_CRYSTALS_KEY}).get("Item")
        except Exception as e:
            print(f"[DynamoDBVitalRepository] load recent crystals error: {e}")
            return
        if item:
            persisted = [KnowledgeCrystal.model_validate_json(raw) for raw in item.get("crystals", []) if raw]
            known = {c.crystal_id for c in self._cache_crystals}
            self._cache_crystals.extend(c for c in persisted if c.crystal_id not in known)
            del self._cache_crystals[RECENT_CRYSTALS_LIMIT:]
