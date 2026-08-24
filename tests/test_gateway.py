"""Backend regression tests for Excalidraw MCP gateway."""
import os
import time
import pytest
import requests

BASE = "http://localhost:8001"
ENGINE = "http://localhost:3100"
TOK_A = "test_session_token_123"
TOK_B = "test_session_token_other_456"
ENGINE_SECRET = "406edba732c2eb7cb8fdd653f667f7f52d4a13ce5358b0554c2b4c8eea7c3e34"

hA = {"Authorization": f"Bearer {TOK_A}"}
hB = {"Authorization": f"Bearer {TOK_B}"}


# ─── Auth ───
def test_me_no_creds():
    r = requests.get(f"{BASE}/api/auth/me")
    assert r.status_code == 401


def test_me_with_bearer():
    r = requests.get(f"{BASE}/api/auth/me", headers=hA)
    assert r.status_code == 200
    assert r.json()["user_id"] == "user_testabc123"


def test_session_bogus_fast_401():
    """Regression: bogus session_id must 401 fast, not hang."""
    t0 = time.time()
    r = requests.post(f"{BASE}/api/auth/session",
                      json={"session_id": "bogus_" + os.urandom(6).hex()},
                      timeout=5)
    elapsed = time.time() - t0
    assert r.status_code == 401, r.text
    assert elapsed < 2.0, f"took {elapsed:.2f}s"


# ─── Projects CRUD + isolation ───
@pytest.fixture(scope="module")
def created():
    """Create one project for user A; delete at teardown."""
    r = requests.post(f"{BASE}/api/projects", headers=hA,
                      json={"name": "TEST_proj_iso", "description": "d"})
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["project_id"].startswith("proj_")
    assert p["agent_token"].startswith("agt_")
    yield p
    requests.delete(f"{BASE}/api/projects/{p['project_id']}", headers=hA)


def test_project_get(created):
    r = requests.get(f"{BASE}/api/projects/{created['project_id']}", headers=hA)
    assert r.status_code == 200
    assert r.json()["project_id"] == created["project_id"]


def test_project_list_contains(created):
    r = requests.get(f"{BASE}/api/projects", headers=hA)
    assert r.status_code == 200
    ids = [p["project_id"] for p in r.json()]
    assert created["project_id"] in ids


def test_project_patch_rename(created):
    r = requests.patch(f"{BASE}/api/projects/{created['project_id']}", headers=hA,
                       json={"name": "TEST_renamed"})
    assert r.status_code == 200
    assert r.json()["name"] == "TEST_renamed"
    # verify via GET
    g = requests.get(f"{BASE}/api/projects/{created['project_id']}", headers=hA)
    assert g.json()["name"] == "TEST_renamed"


def test_isolation_user_b_cannot_see(created):
    # B's list must not include A's project
    r = requests.get(f"{BASE}/api/projects", headers=hB)
    assert r.status_code == 200
    ids = [p["project_id"] for p in r.json()]
    assert created["project_id"] not in ids
    # Direct GET → 404
    g = requests.get(f"{BASE}/api/projects/{created['project_id']}", headers=hB)
    assert g.status_code == 404
    # PATCH → 404
    p = requests.patch(f"{BASE}/api/projects/{created['project_id']}", headers=hB,
                       json={"name": "hijack"})
    assert p.status_code == 404
    # DELETE → 404
    d = requests.delete(f"{BASE}/api/projects/{created['project_id']}", headers=hB)
    assert d.status_code == 404


# ─── Scene persistence ───
def test_scene_put_then_get(created):
    els = [
        {"id": "e1", "type": "rectangle", "x": 10, "y": 20, "width": 100, "height": 50},
        {"id": "e2", "type": "ellipse", "x": 50, "y": 60, "width": 80, "height": 40},
    ]
    r = requests.put(f"{BASE}/api/projects/{created['project_id']}/scene",
                     headers=hA, json={"elements": els, "files": {}})
    assert r.status_code == 200
    assert r.json()["count"] == 2

    g = requests.get(f"{BASE}/api/projects/{created['project_id']}/scene", headers=hA)
    assert g.status_code == 200
    got = g.json().get("elements", [])
    assert len(got) == 2


# ─── Simulate ───
def test_simulate_increases_count(created):
    # get baseline
    g0 = requests.get(f"{BASE}/api/projects/{created['project_id']}/scene", headers=hA)
    n0 = len(g0.json().get("elements", []))
    r = requests.post(f"{BASE}/api/projects/{created['project_id']}/simulate", headers=hA)
    assert r.status_code == 200
    time.sleep(0.5)
    g1 = requests.get(f"{BASE}/api/projects/{created['project_id']}/scene", headers=hA)
    n1 = len(g1.json().get("elements", []))
    assert n1 > n0, f"expected element count to increase, {n0} -> {n1}"


# ─── MCP proxy ───
def test_mcp_proxy_invalid_token():
    r = requests.get(f"{BASE}/api/engine/agt_invalid_xxx/api/elements")
    assert r.status_code == 401


def test_mcp_proxy_get_elements(created):
    r = requests.get(f"{BASE}/api/engine/{created['agent_token']}/api/elements")
    assert r.status_code == 200
    assert "elements" in r.json()


def test_mcp_proxy_canvasid_forced(created):
    """Client-supplied canvasId must be ignored; elements go to token's project."""
    other = "someothercanvas"
    payload = {"elements": [{"id": "mcpX", "type": "rectangle",
                             "x": 1, "y": 2, "width": 3, "height": 4}]}
    r = requests.post(
        f"{BASE}/api/engine/{created['agent_token']}/api/elements/batch",
        params={"canvasId": other}, json=payload)
    assert r.status_code == 200
    time.sleep(0.6)  # persist_project_scene is a background task

    # Element should be on the token's project, NOT under `someothercanvas`
    g = requests.get(f"{BASE}/api/projects/{created['project_id']}/scene", headers=hA)
    ids = [e.get("id") for e in g.json().get("elements", [])]
    assert "mcpX" in ids, f"element not on token's project: {ids}"

    # Directly query the engine for the bogus canvasId; must not contain mcpX
    er = requests.get(f"{ENGINE}/api/elements", params={"canvasId": other},
                      headers={"x-engine-secret": ENGINE_SECRET})
    assert er.status_code == 200
    bogus_ids = [e.get("id") for e in er.json().get("elements", [])]
    assert "mcpX" not in bogus_ids


# ─── Engine hardening (direct) ───
def test_engine_direct_no_secret_401():
    r = requests.get(f"{ENGINE}/api/elements", params={"canvasId": "x"})
    assert r.status_code == 401


def test_engine_direct_with_secret_200():
    r = requests.get(f"{ENGINE}/api/elements", params={"canvasId": "x"},
                     headers={"x-engine-secret": ENGINE_SECRET})
    assert r.status_code == 200


def test_engine_health_open():
    r = requests.get(f"{ENGINE}/health")
    assert r.status_code == 200


# ─── Cleanup verification: delete then GET → 404 ───
def test_delete_project_verified():
    # create a throwaway
    c = requests.post(f"{BASE}/api/projects", headers=hA,
                      json={"name": "TEST_throwaway"}).json()
    pid = c["project_id"]
    d = requests.delete(f"{BASE}/api/projects/{pid}", headers=hA)
    assert d.status_code == 200
    g = requests.get(f"{BASE}/api/projects/{pid}", headers=hA)
    assert g.status_code == 404
