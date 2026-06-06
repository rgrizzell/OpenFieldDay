from __future__ import annotations

from abc import ABC, abstractmethod


class Source(ABC):
    """A live QSO source. Implementations push updates into a QSOStore.

    The only contract: run() is an async coroutine that keeps the store
    current until cancelled.
    """

    @abstractmethod
    async def run(self) -> None:
        ...
