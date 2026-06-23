from __future__ import annotations

import asyncio
import json
import re
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator

from .config import Config, POWER_MULTIPLIERS
from .events import Broadcaster
from .scoring import compute_stats
from .store import QSOStore
from .sources.n3fjp import N3FJPSource

STATIC_DIR = Path(__file__).parent / "static"


_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

_ALLOWED_COLOR_KEYS = {
    "bg", "panel", "fg", "accent", "good", "bad",
    "line", "dim", "tile-bg", "on-accent", "on-good", "on-bad",
}


class ConfigUpdate(BaseModel):
    # All optional so a caller can update just one concern (e.g. the theme builder
    # posts only `colors`); post_config applies whichever fields are present.
    power_multiplier: int | None = None
    bonuses: dict[str, int] | None = None
    n3fjp_host: str | None = None
    n3fjp_port: int | None = None
    colors: dict | None = None

    @field_validator("power_multiplier")
    @classmethod
    def _check_multiplier(cls, v: int | None) -> int | None:
        if v is not None and v not in POWER_MULTIPLIERS:
            raise ValueError(f"power_multiplier must be one of {sorted(POWER_MULTIPLIERS)}")
        return v

    @field_validator("n3fjp_host")
    @classmethod
    def _check_host(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("n3fjp_host must not be empty")
        return v

    @field_validator("n3fjp_port")
    @classmethod
    def _check_port(cls, v: int | None) -> int | None:
        if v is not None and not (1 <= v <= 65535):
            raise ValueError("n3fjp_port must be between 1 and 65535")
        return v

    @field_validator("colors")
    @classmethod
    def _check_colors(cls, v: dict | None) -> dict | None:
        if v is None:
            return v
        for mode, mode_colors in v.items():
            if mode not in ("light", "dark"):
                raise ValueError("colors keys must be 'light' or 'dark'")
            if not isinstance(mode_colors, dict):
                raise ValueError(f"colors.{mode} must be a mapping")
            for key, val in mode_colors.items():
                if key not in _ALLOWED_COLOR_KEYS:
                    raise ValueError(f"colors.{mode}.{key} is not a recognized color key")
                if not isinstance(val, str) or not _HEX_RE.match(val):
                    raise ValueError(f"colors.{mode}.{key} must be a #rrggbb hex string")
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

    # Holds the running N3FJP source task so a host/port change can restart it.
    runtime: dict = {"source_task": None}

    async def start_source_task() -> None:
        cfg = state["config"]
        source = N3FJPSource(cfg.n3fjp_host, cfg.n3fjp_port, store)
        runtime["source_task"] = asyncio.create_task(source.run())

    async def stop_source_task() -> None:
        task = runtime.get("source_task")
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            runtime["source_task"] = None
        store.set_connected(False)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        recompute()  # publish initial snapshot
        if start_source:
            await start_source_task()
        yield
        await stop_source_task()

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
    async def post_config(update: ConfigUpdate) -> dict:
        cfg = state["config"]
        if update.power_multiplier is not None:
            cfg.power_multiplier = update.power_multiplier
        if update.bonuses is not None:
            cfg.bonuses = update.bonuses
        if update.colors is not None:
            cfg.colors = update.colors
        target_changed = False
        if update.n3fjp_host is not None and update.n3fjp_host != cfg.n3fjp_host:
            cfg.n3fjp_host = update.n3fjp_host
            target_changed = True
        if update.n3fjp_port is not None and update.n3fjp_port != cfg.n3fjp_port:
            cfg.n3fjp_port = update.n3fjp_port
            target_changed = True
        cfg.save(config_path)
        recompute()
        if start_source and target_changed:
            await stop_source_task()
            await start_source_task()
        return cfg.to_public_dict()

    @app.get("/api/bonus-catalog")
    def bonus_catalog() -> dict:
        from .config import BONUS_CATALOG
        return BONUS_CATALOG

    @app.get("/logo")
    def logo() -> FileResponse:
        cfg = state["config"]
        if not cfg.has_logo:
            raise HTTPException(status_code=404, detail="no logo configured")
        return FileResponse(cfg.logo_path)

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
