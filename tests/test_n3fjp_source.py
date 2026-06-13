import asyncio
import pytest
from openfieldday.store import QSOStore
from openfieldday.sources.n3fjp import N3FJPSource

# One LISTRESPONSE record, real N3FJP framing (CMD command-id, FLDOPERATOR, CRLF).
LIST_RESPONSE = (
    "<CMD><LISTRESPONSE><CALL>W1AW</CALL><DATE>2026/06/27</DATE><TIMEON>18:02:00</TIMEON>"
    "<BAND>20</BAND><MODE>SSB</MODE><FLDOPERATOR>AB1CD</FLDOPERATOR>"
    "<FLDPRIMARYKEY>1</FLDPRIMARYKEY></CMD>\r\n"
)

# Two records concatenated on a single CRLF line — how N3FJP packs a multi-QSO log.
LIST_RESPONSE_TWO = (
    "<CMD><LISTRESPONSE><CALL>W1AW</CALL><BAND>20</BAND><MODE>SSB</MODE>"
    "<FLDOPERATOR>AB1CD</FLDOPERATOR><FLDPRIMARYKEY>1</FLDPRIMARYKEY></CMD>"
    "<CMD><LISTRESPONSE><CALL>K1ABC</CALL><BAND>40</BAND><MODE>CW</MODE>"
    "<FLDOPERATOR>EF2GH</FLDOPERATOR><FLDPRIMARYKEY>2</FLDPRIMARYKEY></CMD>\r\n"
)


def _make_server_handler(response, *, push_first=None, hits=None):
    async def handler(reader, writer):
        if push_first is not None:
            writer.write(push_first.encode())
            await writer.drain()
        while True:
            line = await reader.readline()
            if not line:
                break
            if hits is not None:
                hits.append(line)
            writer.write(response.encode())
            await writer.drain()
    return handler


async def test_connect_backfills_store():
    server = await asyncio.start_server(
        _make_server_handler(LIST_RESPONSE), "127.0.0.1", 0
    )
    port = server.sockets[0].getsockname()[1]
    store = QSOStore()
    src = N3FJPSource("127.0.0.1", port, store, poll_interval=999)
    task = asyncio.create_task(src.run())
    try:
        async with server:
            await _wait_until(lambda: len(store.qsos) == 1, timeout=2)
        assert store.connected is True
        assert store.qsos[0].call == "W1AW"
        assert store.qsos[0].operator == "AB1CD"
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_replaces_with_full_multirecord_list():
    # A LIST response carries the complete log as concatenated records on one line;
    # the store must hold all of them, not just the last.
    server = await asyncio.start_server(
        _make_server_handler(LIST_RESPONSE_TWO), "127.0.0.1", 0
    )
    port = server.sockets[0].getsockname()[1]
    store = QSOStore()
    src = N3FJPSource("127.0.0.1", port, store, poll_interval=999)
    task = asyncio.create_task(src.run())
    try:
        async with server:
            await _wait_until(lambda: len(store.qsos) == 2, timeout=2)
        assert {q.call for q in store.qsos} == {"W1AW", "K1ABC"}
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_calltabevent_is_ignored():
    # A pushed call-entry preview must not create a phantom QSO; the only QSO comes
    # from the LIST response to our backfill command.
    push = "<CMD><CALLTABEVENT><CALL>GHOST</CALL><BAND>20</BAND><MODE>SSB</MODE></CMD>\r\n"
    server = await asyncio.start_server(
        _make_server_handler(LIST_RESPONSE, push_first=push), "127.0.0.1", 0
    )
    port = server.sockets[0].getsockname()[1]
    store = QSOStore()
    src = N3FJPSource("127.0.0.1", port, store, poll_interval=999)
    task = asyncio.create_task(src.run())
    try:
        async with server:
            await _wait_until(lambda: len(store.qsos) == 1, timeout=2)
        assert [q.call for q in store.qsos] == ["W1AW"]
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_handles_large_log_exceeding_default_readline_limit():
    # The whole log arrives as one CRLF line; asyncio's default 64 KB readline limit
    # would *raise* on a real Field Day log. Feed >64 KB of concatenated records and
    # assert they all land (proves _READ_LIMIT is in effect).
    n = 600  # ~600 records * ~140 bytes ~= 84 KB, comfortably over the 64 KB default
    records = "".join(
        f"<CMD><LISTRESPONSE><CALL>TEST{i:04d}</CALL><BAND>20</BAND><MODE>CW</MODE>"
        f"<FLDOPERATOR>OP{i % 5}</FLDOPERATOR><FLDPRIMARYKEY>{i}</FLDPRIMARYKEY></CMD>"
        for i in range(n)
    )
    big = records + "\r\n"
    assert len(big.encode()) > 64 * 1024

    server = await asyncio.start_server(
        _make_server_handler(big), "127.0.0.1", 0
    )
    port = server.sockets[0].getsockname()[1]
    store = QSOStore()
    src = N3FJPSource("127.0.0.1", port, store, poll_interval=999)
    task = asyncio.create_task(src.run())
    try:
        async with server:
            await _wait_until(lambda: len(store.qsos) == n, timeout=3)
        assert len(store.qsos) == n
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_enterevent_triggers_refresh():
    hits = []
    server = await asyncio.start_server(
        _make_server_handler(
            LIST_RESPONSE,
            push_first="<CMD><ENTEREVENT><CALL>W1AW</CALL></CMD>\r\n",
            hits=hits,
        ),
        "127.0.0.1",
        0,
    )
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
