import asyncio
import pytest
from openfieldday.store import QSOStore
from openfieldday.sources.n3fjp import N3FJPSource

LIST_RESPONSE = (
    "<CMD><LISTRECORD><CALL>W1AW</CALL><BAND>20</BAND><MODE>SSB</MODE>"
    "<OPERATOR>AB1CD</OPERATOR><DATE>2026/06/27</DATE><TIMEON>1802</TIMEON>"
    "</LISTRECORD></CMD>\r\n"
)


async def _fake_n3fjp(reader, writer, *, push_enterevent=False, hits=None):
    """Minimal N3FJP API server: answers any command with LIST_RESPONSE."""
    if push_enterevent:
        writer.write(b"<CMD><ENTEREVENT><CALL>W1AW</CALL></CMD>\r\n")
        await writer.drain()
    while True:
        line = await reader.readline()
        if not line:
            break
        if hits is not None:
            hits.append(line)
        writer.write(LIST_RESPONSE.encode())
        await writer.drain()


async def test_connect_backfills_store():
    server = await asyncio.start_server(_fake_n3fjp, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    store = QSOStore()
    src = N3FJPSource("127.0.0.1", port, store, poll_interval=999)
    task = asyncio.create_task(src.run())
    try:
        async with server:
            await _wait_until(lambda: len(store.qsos) == 1, timeout=2)
        assert store.connected is True
        assert store.qsos[0].call == "W1AW"
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_enterevent_triggers_refresh():
    hits = []

    async def handler(r, w):
        await _fake_n3fjp(r, w, push_enterevent=True, hits=hits)

    server = await asyncio.start_server(handler, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    store = QSOStore()
    src = N3FJPSource("127.0.0.1", port, store, poll_interval=999)
    task = asyncio.create_task(src.run())
    try:
        async with server:
            # The initial backfill sends one LIST; the ENTEREVENT push must cause a
            # SECOND LIST command. Asserting >= 2 is what proves the refresh fired
            # (>= 1 would pass on the backfill alone and prove nothing).
            await _wait_until(lambda: len(hits) >= 2, timeout=2)
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_sets_disconnected_when_server_absent():
    store = QSOStore()
    # Port 1 is unused; connection refused.
    src = N3FJPSource("127.0.0.1", 1, store, poll_interval=999, backoff_base=0.05)
    task = asyncio.create_task(src.run())
    try:
        await asyncio.sleep(0.3)
        assert store.connected is False
        assert store.qsos == []
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def _wait_until(predicate, timeout):
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        if predicate():
            return
        await asyncio.sleep(0.02)
    raise AssertionError("condition not met before timeout")
