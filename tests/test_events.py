import asyncio
import pytest
from openfieldday.events import Broadcaster


async def test_subscriber_receives_published_message():
    b = Broadcaster()
    gen = b.subscribe()
    b.publish("hello")
    msg = await asyncio.wait_for(gen.__anext__(), timeout=1)
    assert msg == "hello"


async def test_new_subscriber_gets_latest_immediately():
    b = Broadcaster()
    b.publish("state-1")
    gen = b.subscribe()
    first = await asyncio.wait_for(gen.__anext__(), timeout=1)
    assert first == "state-1"


async def test_multiple_subscribers_all_receive():
    b = Broadcaster()
    g1, g2 = b.subscribe(), b.subscribe()
    b.publish("x")
    a = await asyncio.wait_for(g1.__anext__(), timeout=1)
    c = await asyncio.wait_for(g2.__anext__(), timeout=1)
    assert a == c == "x"
