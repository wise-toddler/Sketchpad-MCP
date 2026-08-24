"""
Backend regression tests for Excalidraw MCP Cloud gateway.
Covers: auth, projects CRUD & per-user isolation, scene persistence,
simulate, MCP proxy scoping/isolation, engine hardening, and WS live sync.
"""
import os
import json
import time
import uuid
import asyncio
import pytest
import requests
import websockets
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://excalidraw-pro.preview.emergentagent.com").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")
ENGINE_URL = os.environ.get("ENGINE_URL", "http://localhost:3100")
ENGINE_SECRET = os.environ.get(
    "ENGINE_SHARED_SECRET",
    "406edba732c2eb7cb8fdd653f667f7f52d4a13ce5358b0554c2b4c8eea7c3e34",
)

PRIMARY_UID = "user_testabc123"
PRIMARY_TOKEN = "test_session_token_123"
OTHER_UID = "user_testother456"
OTHER_TOKEN = "test_session_token_other_456"


# ─────────────── Fixtures ───────────────
@pytest.fixture(scope="session")
def mongo():
    c = MongoClient(MONGO_URL)
    yield c[DB_NAME]
    c.close()


@pytest.fixture(scope="session", autouse=True)
def seed_users(mongo):
    """Ensure primary + secondary test users/sessions exist."""
    now = datetime.now(timezone.utc)
    for uid, tok, email in [
        (PRIMARY_UID, PRIMARY_TOKEN, "tester@example.com"),
        (OTHER_UID, OTHER_TOKEN, "other@example.com"),
    ]:
        mongo.users.update_one(
            {"user_id": uid},
            {"$set": {"user_id": uid, "email": email, "name": email,
                      "picture": "", "created_at": now.isoformat()}},
            upsert=True,
        )
        mongo.user_sessions.delete_many({"user_id": uid})
        mongo.user_sessions.insert_one({
            "user_id": uid, "session_token": tok,
            "expires_at": now + timedelta(days=7), "created_at": now,
        })
    yield
    # cleanup other user's projects only
    for p in list(mongo.projects.find({"user_id": OTHER_UID})):
        mongo.scenes.delete_many({"project_id": p["project_id"]})
    mongo.projects.delete_many({"user_id": OTHER_UID})


@pytest.fixture
def client_a():
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {PRIMARY_TOKEN}",
                      "Content-Type": "application/json"})
    return s


@pytest.fixture
def client_b():
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {OTHER_TOKEN}",
                      "Content-Type": "application/json"})
    return s


@pytest.fixture
def project_a(client_a, mongo):
    r = client_a.post(f"{BASE_URL}/api/projects",
                      json={"name": f"TEST_PROJ_{uuid.uuid4().hex[:6]}", "description": "d"})
    assert r.status_code == 200, r.text
    p = r.json()
    yield p
    try:
        client_a.delete(f"{BASE_URL}/api/projects/{p['project_id']}")
    except Exception:
        pass


# ─────────────── Auth ───────────────
class TestAuth:
    def test_me_401_without_auth(self):
        r = requests.get(f"{BASE_URL}/api/auth/me")
        assert r.status_code == 401

    def test_me_200_with_bearer(self, client_a):
        r = client_a.get(f"{BASE_URL}/api/auth/me")
        assert r.status_code == 200
        data = r.json()
        assert data["user_id"] == PRIMARY_UID
        assert data["email"] == "tester@example.com"

    def test_me_200_with_cookie(self):
        r = requests.get(f"{BASE_URL}/api/auth/me",
                         cookies={"session_token": PRIMARY_TOKEN})
        assert r.status_code == 200
        assert r.json()["user_id"] == PRIMARY_UID

    def test_logout_deletes_session(self, mongo):
        # create disposable session
        tok = f"tmp_{uuid.uuid4().hex}"
        mongo.user_sessions.insert_one({
            "user_id": PRIMARY_UID, "session_token": tok,
            "expires_at": datetime.now(timezone.utc) + timedelta(days=1),
            "created_at": datetime.now(timezone.utc),
        })
        r = requests.post(f"{BASE_URL}/api/auth/logout",
                          headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 200
        assert mongo.user_sessions.find_one({"session_token": tok}) is None
        # subsequent /me fails
        r2 = requests.get(f"{BASE_URL}/api/auth/me",
                          headers={"Authorization": f"Bearer {tok}"})
        assert r2.status_code == 401


# ─────────────── Projects CRUD & isolation ───────────────
class TestProjects:
    def test_create_list_get(self, client_a, project_a):
        pid = project_a["project_id"]
        assert pid.startswith("proj_")
        assert project_a["agent_token"].startswith("agt_")
        r = client_a.get(f"{BASE_URL}/api/projects")
        assert r.status_code == 200
        assert any(p["project_id"] == pid for p in r.json())
        r2 = client_a.get(f"{BASE_URL}/api/projects/{pid}")
        assert r2.status_code == 200
        assert r2.json()["project_id"] == pid

    def test_rename(self, client_a, project_a):
        pid = project_a["project_id"]
        r = client_a.patch(f"{BASE_URL}/api/projects/{pid}",
                           json={"name": "TEST_renamed"})
        assert r.status_code == 200
        assert r.json()["name"] == "TEST_renamed"
        r2 = client_a.get(f"{BASE_URL}/api/projects/{pid}")
        assert r2.json()["name"] == "TEST_renamed"

    def test_delete(self, client_a):
        r = client_a.post(f"{BASE_URL}/api/projects", json={"name": "TEST_del"})
        pid = r.json()["project_id"]
        d = client_a.delete(f"{BASE_URL}/api/projects/{pid}")
        assert d.status_code == 200
        g = client_a.get(f"{BASE_URL}/api/projects/{pid}")
        assert g.status_code == 404

    def test_per_user_isolation(self, client_a, client_b, project_a):
        pid = project_a["project_id"]
        # B cannot GET
        assert client_b.get(f"{BASE_URL}/api/projects/{pid}").status_code == 404
        # B cannot PATCH
        assert client_b.patch(f"{BASE_URL}/api/projects/{pid}", json={"name": "hack"}).status_code == 404
        # B cannot DELETE
        assert client_b.delete(f"{BASE_URL}/api/projects/{pid}").status_code == 404
        # B does not see it in list
        blist = client_b.get(f"{BASE_URL}/api/projects").json()
        assert not any(p["project_id"] == pid for p in blist)


# ─────────────── Scene persistence ───────────────
class TestScene:
    def test_put_get_scene(self, client_a, project_a, mongo):
        pid = project_a["project_id"]
        elements = [{"id": "e1", "type": "rectangle", "x": 10, "y": 10,
                     "width": 100, "height": 50}]
        r = client_a.put(f"{BASE_URL}/api/projects/{pid}/scene",
                         json={"elements": elements, "files": {}})
        assert r.status_code == 200
        assert r.json()["count"] == 1
        # Read back
        r2 = client_a.get(f"{BASE_URL}/api/projects/{pid}/scene")
        assert r2.status_code == 200
        got = r2.json().get("elements", [])
        assert any(e.get("id") == "e1" for e in got)
        # Durable in Mongo
        scene = mongo.scenes.find_one({"project_id": pid})
        assert scene is not None
        assert any(e.get("id") == "e1" for e in scene["elements"])


# ─────────────── Simulate AI draw ───────────────
class TestSimulate:
    def test_simulate_creates_elements(self, client_a, project_a):
        pid = project_a["project_id"]
        r = client_a.post(f"{BASE_URL}/api/projects/{pid}/simulate")
        assert r.status_code == 200
        # engine batch response includes elements
        data = r.json()
        assert data.get("success") is True or "elements" in data or "count" in data
        time.sleep(0.5)
        r2 = client_a.get(f"{BASE_URL}/api/projects/{pid}/scene")
        assert r2.status_code == 200
        els = r2.json().get("elements", [])
        assert len(els) >= 2


# ─────────────── MCP proxy (external agent token) ───────────────
class TestMcpProxy:
    def test_invalid_agent_token_401(self):
        r = requests.get(f"{BASE_URL}/api/engine/agt_invalid_xyz/api/elements")
        assert r.status_code == 401

    def test_proxy_scoped_and_forced_canvas(self, client_a, project_a, mongo):
        pid = project_a["project_id"]
        tok = project_a["agent_token"]
        # Try to inject a different canvasId - server must ignore it
        payload = {"id": "mcp1", "type": "ellipse",
                   "x": 5, "y": 5, "width": 40, "height": 40}
        r = requests.post(
            f"{BASE_URL}/api/engine/{tok}/api/elements",
            params={"canvasId": "not_this_canvas"},
            json=payload,
        )
        assert r.status_code in (200, 201), r.text
        time.sleep(0.5)
        # Now GET via the proxy: must return this element for THIS project
        g = requests.get(f"{BASE_URL}/api/engine/{tok}/api/elements",
                         params={"canvasId": "not_this_canvas"})
        assert g.status_code == 200
        els = g.json().get("elements", [])
        assert any(e.get("id") == "mcp1" for e in els), \
            f"expected mcp1 in proj canvas, got {[e.get('id') for e in els]}"
        # And nothing landed on "not_this_canvas" via engine (directly check with secret)
        direct = requests.get(f"{ENGINE_URL}/api/elements",
                              params={"canvasId": "not_this_canvas"},
                              headers={"x-engine-secret": ENGINE_SECRET})
        assert direct.status_code == 200
        assert not any(e.get("id") == "mcp1" for e in direct.json().get("elements", []))


# ─────────────── Engine hardening ───────────────
class TestEngineHardening:
    def test_no_secret_returns_401(self):
        r = requests.get(f"{ENGINE_URL}/api/elements")
        assert r.status_code == 401
        r2 = requests.delete(f"{ENGINE_URL}/api/elements/clear")
        assert r2.status_code == 401

    def test_with_secret_returns_200(self):
        r = requests.get(f"{ENGINE_URL}/api/elements",
                         headers={"x-engine-secret": ENGINE_SECRET})
        assert r.status_code == 200

    def test_health_open(self):
        r = requests.get(f"{ENGINE_URL}/health")
        assert r.status_code == 200


# ─────────────── WebSocket live sync ───────────────
class TestWebSocket:
    def test_ws_receives_live_broadcast(self, client_a, project_a):
        pid = project_a["project_id"]
        ws_url = BASE_URL.replace("https://", "wss://").replace("http://", "ws://")
        url = f"{ws_url}/api/ws/canvas/{pid}?token={PRIMARY_TOKEN}"

        async def run():
            async with websockets.connect(url, open_timeout=10) as ws:
                # Expect initial_elements soon
                got_initial = False
                got_live = False
                try:
                    first = await asyncio.wait_for(ws.recv(), timeout=5)
                    msg = json.loads(first)
                    if msg.get("type") in ("initial_elements", "canvas_state", "sync"):
                        got_initial = True
                except asyncio.TimeoutError:
                    pass

                # Trigger a simulate over HTTP
                r = client_a.post(f"{BASE_URL}/api/projects/{pid}/simulate")
                assert r.status_code == 200

                # Now try to receive live broadcast messages
                end = time.time() + 6
                while time.time() < end:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=2)
                    except asyncio.TimeoutError:
                        continue
                    try:
                        msg = json.loads(raw)
                    except Exception:
                        continue
                    if msg.get("type") in ("element_created", "elements_batch_created",
                                           "batch_created", "elements_updated"):
                        got_live = True
                        break
                return got_initial, got_live

        got_initial, got_live = asyncio.run(run())
        # initial handshake message OR live broadcast — at minimum live must arrive
        assert got_live, "Did not receive live WS broadcast after simulate"

    def test_ws_rejects_unauthed(self, project_a):
        pid = project_a["project_id"]
        ws_url = BASE_URL.replace("https://", "wss://").replace("http://", "ws://")
        url = f"{ws_url}/api/ws/canvas/{pid}"

        async def run():
            try:
                async with websockets.connect(url, open_timeout=5) as ws:
                    await asyncio.wait_for(ws.recv(), timeout=3)
                return False  # should have been rejected
            except Exception:
                return True

        assert asyncio.run(run()) is True
