from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator

from .config import Config, POWER_MULTIPLIERS
from .events import Broadcaster
from .scoring import compute_stats
from .store import QSOStore
from .sources.n3fjp import N3FJPSource

STATIC_DIR = Path(__file__).parent / "static"


class ConfigUpdate(BaseModel):
    power_multiplier: int
    bonuses: dict[str, int]

    @field_validator("power_multiplier")
    @classmethod
    def _check_multiplier(cls, v: int) -> int:
        if v not in POWER_MULTIPLIERS:
            raise ValueError(f"power_multiplier must be one of {sorted(POWER_MULTIPLIERS)}")
        return v


def create_app(config_path: str | Path = "config.yaml", start_source: bool = True) -> FastAPI:
    config_path = Path(config_path)
    store = QSOStore()
    broadcaster = Broadcaster()
    state = {"config": Config.load(config_path)}

    def recompute() -> None:
        stats = compute_stats(store.qsos, state["config"], store.connected)
        broadcaster.publish(json.dumps(_stats_to_dict(stats)))

    store.on_change(recompute)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        recompute()  # publish initial snapshot
        task = None
        if start_source:
            cfg = state["config"]
            source = N3FJPSource(cfg.n3fjp_host, cfg.n3fjp_port, store)
            task = asyncio.create_task(source.run())
        yield
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    app = FastAPI(lifespan=lifespan)
    app.state.store = store
    app.state.broadcaster = broadcaster

    @app.get("/api/stats")
    def get_stats() -> dict:
        return _stats_to_dict(compute_stats(store.qsos, state["config"], store.connected))

    @app.get("/api/config")
    def get_config() -> dict:
        return state["config"].to_public_dict()

    @app.post("/api/config")
    def post_config(update: ConfigUpdate) -> dict:
        cfg = state["config"]
        cfg.power_multiplier = update.power_multiplier
        cfg.bonuses = update.bonuses
        cfg.save(config_path)
        recompute()
        return cfg.to_public_dict()

    @app.get("/api/bonus-catalog")
    def bonus_catalog() -> dict:
        from .config import BONUS_CATALOG
        return BONUS_CATALOG

    @app.get("/events")
    async def events() -> StreamingResponse:
        return StreamingResponse(_sse_stream(broadcaster), media_type="text/event-stream")

    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    return app


async def _sse_stream(broadcaster):
    async for data in broadcaster.subscribe():
        yield f"data: {data}\n\n"


def _stats_to_dict(stats) -> dict:
    return asdict(stats)
