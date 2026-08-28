"""Phase 2 co-editing tests: WebSocket relay, scene sync, presence, viewer read-only.

Uses two seeded users (owner tester@ + editor invitee tester2@) and verifies:
  - PUT /scene as editor broadcasts elements_synced to the OTHER client
  - clientId is passed through so the sender can suppress its own echo
  - Pointer messages relay to peer only (not self)
  - presence_leave relays to peer
  - Viewer role cannot PUT scene (403)
  - Persistence: after PUT, GET /scene returns elements (durable via Mongo)
"""
import os
import json
import uuid
import asyncio
from urllib.parse import urlparse, urlunparse

import pytest
import requests
import websockets

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
_p = urlparse(BASE)
WS_BASE = urlunparse(("wss" if _p.scheme == "https" else "ws", _p.netloc, "/api/ws/canvas", "", "", ""))

TOK_A = "test_session_token_123"
TOK_B = "test_session_token_other_456"
EMAIL_B = "tester2@example.com"
hA = {"Authorization": f"Bearer {TOK_A}"}
hB = {"Authorization": f"Bearer {TOK_B}"}


# ---- Fixtures -----------------------------------------------------------------
@pytest.fixture()
def project_editor():
    """Fresh project owned by A with B invited as editor."""
    r = requests.post(f"{BASE}/api/projects", headers=hA,
                      json={"name": f"TEST_coedit_{uuid.uuid4().hex[:6]}"})
    assert r.status_code == 200, r.text
    p = r.json()
    r2 = requests.post(f"{BASE}/api/projects/{p['project_id']}/members",
                       headers=hA, json={"email": EMAIL_B, "role": "editor"})
    assert r2.status_code == 200, r2.text
    yield p
    requests.delete(f"{BASE}/api/projects/{p['project_id']}", headers=hA)


@pytest.fixture()
def project_viewer():
    r = requests.post(f"{BASE}/api/projects", headers=hA,
                      json={"name": f"TEST_view_{uuid.uuid4().hex[:6]}"})
    assert r.status_code == 200, r.text
    p = r.json()
    r2 = requests.post(f"{BASE}/api/projects/{p['project_id']}/members",
                       headers=hA, json={"email": EMAIL_B, "role": "viewer"})
    assert r2.status_code == 200, r2.text
    yield p
    requests.delete(f"{BASE}/api/projects/{p['project_id']}", headers=hA)


async def _connect(pid, token):
    ws = await websockets.connect(f"{WS_BASE}/{pid}?token={token}", max_size=None)
    # drain initial_elements + sync_status
    for _ in range(2):
        try:
            await asyncio.wait_for(ws.recv(), timeout=3)
        except asyncio.TimeoutError:
            break
    return ws


async def _recv_until(ws, msg_type, timeout=5, predicate=None):
    """Recv until a message with a given type (and optional predicate) arrives."""
    end = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < end:
        remaining = end - asyncio.get_event_loop().time()
        if remaining <= 0:
            break
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
        except asyncio.TimeoutError:
            break
        try:
            msg = json.loads(raw)
        except Exception:
            continue
        if msg.get("type") == msg_type and (predicate is None or predicate(msg)):
            return msg
    return None


# ---- Tests --------------------------------------------------------------------
def test_editor_scene_put_broadcasts_to_peer(project_editor):
    """User A PUTs a shape -> user B's WS receives elements_synced with it."""
    pid = project_editor["project_id"]

    async def run():
        ws_a = await _connect(pid, TOK_A)
        ws_b = await _connect(pid, TOK_B)
        try:
            elements = [{
                "id": "rect_coedit_1", "type": "rectangle",
                "x": 100, "y": 100, "width": 120, "height": 80,
            }]
            client_id = "clientA"
            # Trigger sync via editor A
            r = requests.put(f"{BASE}/api/projects/{pid}/scene",
                             headers=hA,
                             json={"elements": elements, "files": {}, "client_id": client_id})
            assert r.status_code == 200, r.text

            # B must receive the elements_synced broadcast
            msg = await _recv_until(ws_b, "elements_synced", timeout=6)
            assert msg is not None, "B did not receive elements_synced"
            assert msg.get("clientId") == client_id, f"clientId not relayed: {msg}"
            ids = [e.get("id") for e in msg.get("elements", [])]
            assert "rect_coedit_1" in ids, f"element not in broadcast: {ids}"

            # A also receives its own broadcast (with matching clientId so it can suppress locally)
            msg_a = await _recv_until(ws_a, "elements_synced", timeout=6)
            assert msg_a is not None, "A did not receive its own elements_synced"
            assert msg_a.get("clientId") == client_id
        finally:
            await ws_a.close()
            await ws_b.close()

    asyncio.run(run())


def test_scene_persists_after_put(project_editor):
    """After PUT, GET /scene returns the persisted element (durable in Mongo)."""
    pid = project_editor["project_id"]
    elements = [{
        "id": "rect_persist_1", "type": "rectangle",
        "x": 50, "y": 60, "width": 200, "height": 100,
    }]
    r = requests.put(f"{BASE}/api/projects/{pid}/scene", headers=hB,
                     json={"elements": elements, "files": {}, "client_id": "cB"})
    assert r.status_code == 200, r.text  # editor B allowed

    r2 = requests.get(f"{BASE}/api/projects/{pid}/scene", headers=hA)
    assert r2.status_code == 200
    got = r2.json()
    assert any(el.get("id") == "rect_persist_1" for el in got.get("elements", [])), got


def test_viewer_cannot_put_scene(project_viewer):
    """Viewer role: PUT /scene must return 403 (writes are editor+)."""
    pid = project_viewer["project_id"]
    r = requests.put(f"{BASE}/api/projects/{pid}/scene", headers=hB,
                     json={"elements": [{"id": "x", "type": "rectangle",
                                         "x": 0, "y": 0, "width": 10, "height": 10}],
                           "files": {}, "client_id": "cvB"})
    assert r.status_code == 403, r.text


def test_pointer_relayed_to_peer_only(project_editor):
    """Pointer from A goes to B (not to A itself)."""
    pid = project_editor["project_id"]

    async def run():
        ws_a = await _connect(pid, TOK_A)
        ws_b = await _connect(pid, TOK_B)
        try:
            payload = {"type": "pointer", "clientId": "A1", "name": "A",
                       "color": "#ff0000", "x": 42, "y": 24}
            await ws_a.send(json.dumps(payload))

            msg_b = await _recv_until(ws_b, "pointer", timeout=4,
                                      predicate=lambda m: m.get("clientId") == "A1")
            assert msg_b is not None, "B did not receive pointer from A"
            assert msg_b["x"] == 42 and msg_b["y"] == 24

            # A must NOT receive its own pointer back
            echo = await _recv_until(ws_a, "pointer", timeout=1.5,
                                     predicate=lambda m: m.get("clientId") == "A1")
            assert echo is None, f"A received its own pointer echo: {echo}"
        finally:
            await ws_a.close()
            await ws_b.close()

    asyncio.run(run())


def test_presence_leave_relayed(project_editor):
    """presence_leave from A reaches B."""
    pid = project_editor["project_id"]

    async def run():
        ws_a = await _connect(pid, TOK_A)
        ws_b = await _connect(pid, TOK_B)
        try:
            await ws_a.send(json.dumps({"type": "presence_leave", "clientId": "A_leave"}))
            msg = await _recv_until(ws_b, "presence_leave", timeout=4,
                                    predicate=lambda m: m.get("clientId") == "A_leave")
            assert msg is not None, "B did not receive presence_leave"
        finally:
            await ws_a.close()
            await ws_b.close()

    asyncio.run(run())


def test_anonymous_viewer_ws_receives_updates(project_editor):
    """Anonymous ?share= viewer link: cannot write via PUT, but WS receives sync."""
    pid = project_editor["project_id"]
    # Enable link_access=viewer as owner
    r = requests.put(f"{BASE}/api/projects/{pid}/share", headers=hA,
                     json={"link_access": "viewer"})
    assert r.status_code == 200
    share_token = r.json()["share_token"]

    async def run():
        ws_view = await websockets.connect(f"{WS_BASE}/{pid}?share={share_token}",
                                           max_size=None)
        # drain initial
        for _ in range(2):
            try:
                await asyncio.wait_for(ws_view.recv(), timeout=3)
            except asyncio.TimeoutError:
                break
        try:
            elements = [{"id": "rect_anon_1", "type": "rectangle",
                         "x": 10, "y": 20, "width": 40, "height": 50}]
            r2 = requests.put(f"{BASE}/api/projects/{pid}/scene", headers=hA,
                              json={"elements": elements, "files": {}, "client_id": "cA"})
            assert r2.status_code == 200

            msg = await _recv_until(ws_view, "elements_synced", timeout=6)
            assert msg is not None, "anonymous viewer did not receive elements_synced"
            assert any(e.get("id") == "rect_anon_1" for e in msg.get("elements", []))
        finally:
            await ws_view.close()

    asyncio.run(run())


def test_anonymous_writes_denied_via_rest(project_editor):
    """Anonymous share=viewer must NOT be able to PUT scene."""
    pid = project_editor["project_id"]
    r = requests.put(f"{BASE}/api/projects/{pid}/share", headers=hA,
                     json={"link_access": "viewer"})
    share_token = r.json()["share_token"]
    r2 = requests.put(f"{BASE}/api/projects/{pid}/scene?share={share_token}",
                      json={"elements": [], "files": {}, "client_id": "anon"})
    assert r2.status_code in (401, 403), r2.text
