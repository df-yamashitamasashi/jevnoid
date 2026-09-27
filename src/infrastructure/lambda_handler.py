from __future__ import annotations

import asyncio
import os
from typing import Any

from src.adapters.jev_brain import JevBrain
from src.adapters.kv_publisher import CloudflareKVPublisher
from src.adapters.secrets import read_secret
from src.adapters.vital_repo import DynamoDBVitalRepository, InMemoryVitalRepository
from src.adapters.web_forager import WebForager
from src.usecases.heartbeat import HeartbeatUsecase
from src.usecases.vitals_snapshot import build_vitals_snapshot

# Lazy-loaded runtime singletons, reused across warm invocations
_repo = None
_brain = None
_heartbeat_uc = None
_publisher = None


def get_dependencies():
    global _repo, _brain, _heartbeat_uc, _publisher
    if _repo is None:
        table_name = os.environ.get("VITALS_TABLE")
        _repo = DynamoDBVitalRepository(table_name=table_name) if table_name else InMemoryVitalRepository()
        _brain = JevBrain()
        _heartbeat_uc = HeartbeatUsecase(repo=_repo, brain=_brain, forager=WebForager(timeout_sec=3.0))
        _publisher = _build_publisher()
    return _repo, _brain, _heartbeat_uc, _publisher


def _build_publisher() -> CloudflareKVPublisher | None:
    account_id = os.environ.get("CF_ACCOUNT_ID", "").strip()
    namespace_id = os.environ.get("CF_KV_NAMESPACE_ID", "").strip()
    if not (account_id and namespace_id):
        return None
    token = read_secret("CF_API_TOKEN", "CF_API_TOKEN_PARAM")
    return CloudflareKVPublisher(account_id, namespace_id, token) if token else None


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """EventBridge heartbeat: evolve every organism, then publish the public snapshot to Cloudflare KV.

    There is no HTTP entry point: observers read the snapshot from Cloudflare, never from AWS.
    """
    if event.get("source") != "aws.events":
        return {"status": "ignored"}
    return asyncio.run(_pulse_and_publish())


async def _pulse_and_publish() -> dict[str, Any]:
    repo, brain, heartbeat_uc, publisher = get_dependencies()
    results = await heartbeat_uc.pulse_all()

    snapshot = build_vitals_snapshot(
        await repo.get_all_organisms(),
        await repo.get_crystals(limit=25),
        jev_connected=brain.is_connected,
    )
    published = False
    if publisher is None:
        print("[Heartbeat] Cloudflare publisher not configured; snapshot not published.")
    else:
        try:
            publisher.publish(snapshot)
            published = True
        except Exception as e:
            # Not re-raised: an async retry from EventBridge would re-run the pulse (and its Jev calls).
            print(f"[Heartbeat] Snapshot publish failed: {type(e).__name__}: {e}")

    return {
        "status": "pulsed",
        "organisms": len(results),
        "births": [r["daughter_born"] for r in results if r.get("daughter_born")],
        "published": published,
    }
