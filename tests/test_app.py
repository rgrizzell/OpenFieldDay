import asyncio
import json
import threading
import time
from fastapi.testclient import TestClient
from openfieldday.app import create_app, _sse_stream
from openfieldday.config import Config
from openfieldday.events import Broadcaster
from openfieldday.models import QSO


def make_client(tmp_path):
    app = create_app(config_path=tmp_path / "config.yaml", start_source=False)
    return app, TestClient(app)


class _FakeN3FJP:
    """A throwaway N3FJP server that answers every command with one LIST record
    naming `call`. Runs in its own thread/event loop; the source reaches it over
    real localhost TCP, so it needs no shared loop with the app under test."""

    def __init__(self, call: str):
        self._response = (
            f"<CMD><LISTRESPONSE><CALL>{call}</CALL><BAND>20</BAND><MODE>SSB</MODE>"
            f"<FLDOPERATOR>OP</FLDOPERATOR><FLDPRIMARYKEY>1</FLDPRIMARYKEY></CMD>\r\n"
        ).encode()
        self._loop = asyncio.new_event_loop()
        self._ready = threading.Event()
        self.port = None
        self._thread = threading.Thread(target=self._run, daemon=True)

    async def _handler(self, reader, writer):
        try:
            while await reader.readline():
                writer.write(self._response)
                await writer.drain()
        except Exception:
            pass

    def _run(self):
        asyncio.set_event_loop(self._loop)

        async def main():
            server = await asyncio.start_server(self._handler, "127.0.0.1", 0)
            self.port = server.sockets[0].getsockname()[1]
            self._ready.set()
            async with server:
                await server.serve_forever()

        try:
            self._loop.run_until_complete(main())
        except (asyncio.CancelledError, RuntimeError):
            pass

    def __enter__(self):
        self._thread.start()
        assert self._ready.wait(timeout=2), "fake N3FJP did not start"
        return self

    def __exit__(self, *exc):
        self._loop.call_soon_threadsafe(self._loop.stop)


def _wait_for_call(client, call, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        calls = [e["call"] for e in client.get("/api/stats").json()["recent_qsos"]]
        if call in calls:
            return
        time.sleep(0.05)
    raise AssertionError(f"{call} not present within {timeout}s")


def test_changing_target_repoints_live_source(tmp_path):
    # Two servers on different ports, each emitting a distinct callsign. Pointing
    # the config at the second one must move the live connection — proving a DHCP
    # address change takes effect without an app restart.
    with _FakeN3FJP("AAAA") as server_a, _FakeN3FJP("BBBB") as server_b:
        cfg_path = tmp_path / "config.yaml"
        Config(n3fjp_host="127.0.0.1", n3fjp_port=server_a.port).save(cfg_path)
        app = create_app(config_path=cfg_path, start_source=True)
        with TestClient(app) as client:
            _wait_for_call(client, "AAAA")  # connected to A
            r = client.post("/api/config", json={
                "power_multiplier": 2, "bonuses": {},
                "n3fjp_host": "127.0.0.1", "n3fjp_port": server_b.port,
            })
            assert r.status_code == 200
            _wait_for_call(client, "BBBB")  # live-repointed to B


def test_stats_endpoint_initial(tmp_path):
    app, client = make_client(tmp_path)
    r = client.get("/api/stats")
    assert r.status_code == 200
    body = r.json()
    assert body["total_qsos"] == 0
    assert body["connected"] is False
    assert "band_mode" in body and "top_operators" in body and "recent_qsos" in body


def test_stats_reflects_store_and_config(tmp_path):
    app, client = make_client(tmp_path)
    app.state.store.replace([QSO(call="W1AW", band="20", mode="CW")])
    r = client.get("/api/stats").json()
    assert r["total_qsos"] == 1
    assert r["qso_points"] == 2
    assert r["score"] == 2 * 2  # default multiplier 2, no bonus


def test_get_and_post_config(tmp_path):
    app, client = make_client(tmp_path)
    r = client.post("/api/config", json={
        "power_multiplier": 5,
        "bonuses": {"Emergency power": 100},
    })
    assert r.status_code == 200
    cfg = client.get("/api/config").json()
    assert cfg["power_multiplier"] == 5
    assert cfg["bonus_points"] == 100
    # config change is persisted
    assert (tmp_path / "config.yaml").exists()


def test_post_config_rejects_bad_multiplier(tmp_path):
    app, client = make_client(tmp_path)
    r = client.post("/api/config", json={"power_multiplier": 3, "bonuses": {}})
    assert r.status_code == 422


def test_post_config_updates_n3fjp_target(tmp_path):
    app, client = make_client(tmp_path)
    r = client.post("/api/config", json={
        "power_multiplier": 2, "bonuses": {},
        "n3fjp_host": "192.168.1.50", "n3fjp_port": 1200,
    })
    assert r.status_code == 200
    cfg = client.get("/api/config").json()
    assert cfg["n3fjp_host"] == "192.168.1.50"
    assert cfg["n3fjp_port"] == 1200
    # persisted to disk so a restart keeps the new target
    from openfieldday.config import Config
    saved = Config.load(tmp_path / "config.yaml")
    assert saved.n3fjp_host == "192.168.1.50"
    assert saved.n3fjp_port == 1200


def test_post_config_rejects_bad_port(tmp_path):
    app, client = make_client(tmp_path)
    r = client.post("/api/config", json={
        "power_multiplier": 2, "bonuses": {}, "n3fjp_port": 70000,
    })
    assert r.status_code == 422


def test_post_config_omitting_target_keeps_existing(tmp_path):
    app, client = make_client(tmp_path)
    client.post("/api/config", json={"power_multiplier": 5, "bonuses": {}})
    cfg = client.get("/api/config").json()
    assert cfg["n3fjp_host"] == "127.0.0.1"
    assert cfg["n3fjp_port"] == 1100


async def test_sse_stream_emits_data_frames():
    # Drive the SSE frame generator directly. Streaming an infinite SSE response
    # over httpx ASGITransport buffers forever and hangs, so we test the actual
    # frame-producing generator instead.
    b = Broadcaster()
    b.publish(json.dumps({"total_qsos": 0}))
    gen = _sse_stream(b)
    frame = await asyncio.wait_for(gen.__anext__(), timeout=1)
    assert frame.startswith("data:")
    assert frame.endswith("\n\n")
    payload = json.loads(frame[len("data:"):].strip())
    assert "total_qsos" in payload


def test_bonus_catalog_endpoint(tmp_path):
    app, client = make_client(tmp_path)
    r = client.get("/api/bonus-catalog")
    assert r.status_code == 200
    assert "Emergency power" in r.json()


def test_config_endpoint_includes_theme_data(tmp_path):
    app, client = make_client(tmp_path)
    cfg = client.get("/api/config").json()
    assert set(cfg["colors"]) == {"light", "dark"}   # per-theme override buckets
    assert cfg["theme"]["auto_light_start"] == 5
    assert cfg["has_logo"] is False


def test_logo_404_when_not_configured(tmp_path):
    app, client = make_client(tmp_path)
    assert client.get("/logo").status_code == 404


def test_logo_served_when_configured(tmp_path):
    from openfieldday.config import Config
    logo = tmp_path / "logo.png"
    logo.write_bytes(b"\x89PNG-fake-bytes")
    cfg_path = tmp_path / "config.yaml"
    Config(logo_path=str(logo)).save(cfg_path)
    app = create_app(config_path=cfg_path, start_source=False)
    client = TestClient(app)
    r = client.get("/logo")
    assert r.status_code == 200
    assert r.content == b"\x89PNG-fake-bytes"
