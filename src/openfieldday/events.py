from __future__ import annotations

import asyncio
from typing import AsyncIterator


class Broadcaster:
    """Fan-out of the latest stats JSON string to all connected SSE clients.

    publish() is synchronous (safe to call from store listeners). Each
    subscriber gets the latest snapshot immediately on connect, then live
    updates.
    """

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[str]] = set()
        self._latest: str | None = None

    def publish(self, data: str) -> None:
        self._latest = data
        for q in list(self._subscribers):
            q.put_nowait(data)

    async def subscribe(self) -> AsyncIterator[str]:
        q: asyncio.Queue[str] = asyncio.Queue()
        self._subscribers.add(q)
        try:
            if self._latest is not None:
                yield self._latest
            while True:
                yield await q.get()
        finally:
            self._subscribers.discard(q)
