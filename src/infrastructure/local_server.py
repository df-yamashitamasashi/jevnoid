from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.adapters.jev_brain import JevBrain
from src.adapters.vital_repo import InMemoryVitalRepository
from src.adapters.web_forager import WebForager
from src.usecases.heartbeat import HeartbeatUsecase
from src.usecases.vitals_snapshot import build_vitals_snapshot

WEB_ROOT = Path(__file__).resolve().parents[2] / "web" / "public"

# Global singletons for local runtime
vital_repo = InMemoryVitalRepository()
jev_brain = JevBrain()
web_forager = WebForager()
heartbeat_uc = HeartbeatUsecase(repo=vital_repo, brain=jev_brain, forager=web_forager)


HEARTBEAT_INTERVAL_SECONDS = 3 * 60 * 60  # matches the EventBridge schedule in the cloud


async def life_cycle_daemon():
    """Heartbeat on the same cadence as production, so local growth/hazard behavior matches it."""
    while True:
        try:
            await heartbeat_uc.pulse_all()
        except Exception as e:
            print(f"[Daemon Heartbeat Error]: {e}")
        await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(life_cycle_daemon())
    yield
    task.cancel()


app = FastAPI(title="Jevnoid Autonomous 3D Terrarium", lifespan=lifespan)


@app.get("/api/v1/vitals")
async def get_vitals() -> dict[str, Any]:
    return build_vitals_snapshot(
        await vital_repo.get_all_organisms(),
        await vital_repo.get_crystals(limit=25),
        jev_connected=jev_brain.is_connected,
    )


app.mount("/", StaticFiles(directory=WEB_ROOT, html=True), name="web")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.infrastructure.local_server:app", host="127.0.0.1", port=8000, reload=True)
