import asyncio
import json
from fastapi.testclient import TestClient
from openfieldday.app import create_app, _sse_stream
from openfieldday.events import Broadcaster
from openfieldday.models import QSO


def make_client(tmp_path):
    app = create_app(config_path=tmp_path / "config.yaml", start_source=False)
    return app, TestClient(app)


def test_stats_endpoint_initial(tmp_path):
    app, client = make_client(tmp_path)
    r = client.get("/api/stats")
    assert r.status_code == 200
    body = r.json()
    assert body["total_qsos"] == 0
    assert body["connected"] is False
    assert "band_mode" in body and "by_operator" in body


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
