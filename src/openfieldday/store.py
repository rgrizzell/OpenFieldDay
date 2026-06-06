from __future__ import annotations

from typing import Callable

from .models import QSO


class QSOStore:
    """Holds the current canonical QSO list and connection state in memory.

    The N3FJP LIST response is authoritative, so updates arrive via replace().
    Listeners are notified synchronously on any change.
    """

    def __init__(self) -> None:
        self._qsos: list[QSO] = []
        self._connected: bool = False
        self._listeners: list[Callable[[], None]] = []

    def on_change(self, fn: Callable[[], None]) -> None:
        self._listeners.append(fn)

    def _notify(self) -> None:
        for fn in self._listeners:
            fn()

    @property
    def qsos(self) -> list[QSO]:
        return list(self._qsos)

    @property
    def connected(self) -> bool:
        return self._connected

    def replace(self, qsos: list[QSO]) -> None:
        self._qsos = list(qsos)
        self._notify()

    def set_connected(self, value: bool) -> None:
        if self._connected != value:
            self._connected = value
            self._notify()
