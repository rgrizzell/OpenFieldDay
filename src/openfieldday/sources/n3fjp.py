from __future__ import annotations

import asyncio
import logging

from .base import Source
from .n3fjp_parser import parse_list, is_enterevent, message_type
from ..store import QSOStore

log = logging.getLogger(__name__)

LIST_COMMAND = b"<CMD><LIST><INCLUDEALL></CMD>\r\n"


class N3FJPSource(Source):
    def __init__(
        self,
        host: str,
        port: int,
        store: QSOStore,
        poll_interval: float = 10.0,
        backoff_base: float = 1.0,
        backoff_max: float = 30.0,
    ) -> None:
        self._host = host
        self._port = port
        self._store = store
        self._poll_interval = poll_interval
        self._backoff_base = backoff_base
        self._backoff_max = backoff_max
        self._writer: asyncio.StreamWriter | None = None
        self._write_lock = asyncio.Lock()

    async def run(self) -> None:
        backoff = self._backoff_base
        while True:
            try:
                await self._connect_and_serve()
                backoff = self._backoff_base
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - resilience is the point
                log.warning("N3FJP connection error: %s", exc)
            finally:
                self._store.set_connected(False)
                self._writer = None
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, self._backoff_max)

    async def _connect_and_serve(self) -> None:
        reader, writer = await asyncio.open_connection(self._host, self._port)
        self._writer = writer
        self._store.set_connected(True)
        await self._send(LIST_COMMAND)  # initial backfill

        poller = asyncio.create_task(self._poll_loop())
        try:
            await self._read_loop(reader)
        finally:
            poller.cancel()
            await asyncio.gather(poller, return_exceptions=True)
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:  # noqa: BLE001
                pass

    async def _read_loop(self, reader: asyncio.StreamReader) -> None:
        while True:
            line = await reader.readline()
            if not line:  # EOF
                raise ConnectionError("N3FJP closed the connection")
            payload = line.decode(errors="replace").strip()
            if not payload:
                continue
            if is_enterevent(payload):
                await self._send(LIST_COMMAND)  # refresh now
            elif message_type(payload) is None or "LISTRECORD" in payload.upper() or payload.upper().endswith("</CMD>"):
                qsos = parse_list(payload)
                if qsos or payload.upper() == "<CMD></CMD>":
                    self._store.replace(qsos)

    async def _poll_loop(self) -> None:
        while True:
            await asyncio.sleep(self._poll_interval)
            await self._send(LIST_COMMAND)

    async def _send(self, data: bytes) -> None:
        if self._writer is None:
            return
        async with self._write_lock:
            self._writer.write(data)
            await self._writer.drain()
