"""Backend regression: user-level MCP proxy /api/mcp/{user_token}/api/...
Focus: deleted-active-canvas edge case + ownership + happy path + no-hang regression.
"""
import time
import pytest
import requests

BASE = "http://localhost:8001"
TOK_A = "test_session_token_123"
TOK_B = "test_session_token_other_456"
hA = {"Authorization": f"Bearer {TOK_A}"}
hB = {"Authorization": f"Bearer {TOK_B}"}


@pytest.fixture(scope="module")
def mcp_token_a():
    r = requests.get(f"{BASE}/api/auth/mcp-token", headers=hA, timeout=5)
    assert r.status_code == 200, r.text
    tok = r.json()["mcp_token"]
    assert tok.startswith("usr_"), tok
    return tok


@pytest.fixture(scope="module")
def mcp_token_b():
    r = requests.get(f"{BASE}/api/auth/mcp-token", headers=hB, timeout=5)
    assert r.status_code == 200, r.text
    tok = r.json()["mcp_token"]
    assert tok.startswith("usr_"), tok
    return tok


# ── Happy path ──
def test_happy_path_create_and_draw(mcp_token_a):
    r = requests.post(f"{BASE}/api/mcp/{mcp_token_a}/api/canvases",
                      json={"name": "TEST_happy"}, timeout=10)
    assert r.status_code == 200, r.text
    canvas = r.json()["canvas"]
    cid = canvas["id"]
    assert cid.startswith("proj_")

    r = requests.post(
        f"{BASE}/api/mcp/{mcp_token_a}/api/elements",
        params={"canvasId": cid},
        json={"type": "rectangle", "x": 10, "y": 20, "width": 100, "height": 50},
        timeout=10,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("success") is True, body

    # cleanup
    requests.delete(f"{BASE}/api/mcp/{mcp_token_a}/api/canvases/{cid}", timeout=5)


# ── MAIN EDGE CASE: deleted canvas ──
@pytest.fixture(scope="module")
def deleted_canvas_id(mcp_token_a):
    r = requests.post(f"{BASE}/api/mcp/{mcp_token_a}/api/canvases",
                      json={"name": "TEST_to_be_deleted"}, timeout=10)
    assert r.status_code == 200, r.text
    cid = r.json()["canvas"]["id"]
    d = requests.delete(f"{BASE}/api/mcp/{mcp_token_a}/api/canvases/{cid}", timeout=10)
    assert d.status_code == 200, d.text
    return cid


def _assert_actionable_404(resp):
    assert resp.status_code == 404, f"expected 404, got {resp.status_code}: {resp.text}"
    detail = (resp.json().get("detail") or "").lower()
    # must mention canvas not-found / deleted, and suggest at least one recovery tool
    assert ("not found" in detail) or ("deleted" in detail), detail
    assert any(k in detail for k in ("list_canvases", "set_active_canvas", "create_canvas")), detail


def test_element_op_on_deleted_canvas_404(mcp_token_a, deleted_canvas_id):
    t0 = time.time()
    r = requests.post(
        f"{BASE}/api/mcp/{mcp_token_a}/api/elements",
        params={"canvasId": deleted_canvas_id},
        json={"type": "rectangle", "x": 1, "y": 2, "width": 3, "height": 4},
        timeout=5,
    )
    assert time.time() - t0 < 3.0, "must not hang"
    _assert_actionable_404(r)


def test_elements_get_on_deleted_canvas_404(mcp_token_a, deleted_canvas_id):
    r = requests.get(
        f"{BASE}/api/mcp/{mcp_token_a}/api/elements",
        params={"canvasId": deleted_canvas_id},
        timeout=5,
    )
    _assert_actionable_404(r)


def test_scene_get_on_deleted_canvas_404(mcp_token_a, deleted_canvas_id):
    r = requests.get(
        f"{BASE}/api/mcp/{mcp_token_a}/api/scene",
        params={"canvasId": deleted_canvas_id},
        timeout=5,
    )
    _assert_actionable_404(r)


def test_batch_create_on_deleted_canvas_404(mcp_token_a, deleted_canvas_id):
    r = requests.post(
        f"{BASE}/api/mcp/{mcp_token_a}/api/elements/batch",
        params={"canvasId": deleted_canvas_id},
        json={"elements": [
            {"type": "rectangle", "x": 1, "y": 2, "width": 3, "height": 4},
        ]},
        timeout=5,
    )
    _assert_actionable_404(r)


# ── Ownership: exists but not owned -> 403 ──
def test_ownership_exists_but_not_owned_403(mcp_token_a, mcp_token_b):
    # user B creates their own canvas (via user-level MCP for simplicity)
    r = requests.post(f"{BASE}/api/mcp/{mcp_token_b}/api/canvases",
                      json={"name": "TEST_B_owned"}, timeout=10)
    assert r.status_code == 200, r.text
    b_cid = r.json()["canvas"]["id"]
    try:
        # user A tries to draw on B's canvas
        r = requests.post(
            f"{BASE}/api/mcp/{mcp_token_a}/api/elements",
            params={"canvasId": b_cid},
            json={"type": "rectangle", "x": 1, "y": 2, "width": 3, "height": 4},
            timeout=5,
        )
        assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text}"
        detail = (r.json().get("detail") or "").lower()
        assert "not own" in detail or "own" in detail, detail
    finally:
        requests.delete(f"{BASE}/api/mcp/{mcp_token_b}/api/canvases/{b_cid}", timeout=5)


# ── No canvasId supplied -> 400 with "No active canvas" ──
def test_no_canvas_id_400(mcp_token_a):
    r = requests.post(
        f"{BASE}/api/mcp/{mcp_token_a}/api/elements",
        json={"type": "rectangle", "x": 1, "y": 2, "width": 3, "height": 4},
        timeout=5,
    )
    assert r.status_code == 400, r.text
    detail = (r.json().get("detail") or "").lower()
    assert "no active canvas" in detail, detail
    # actionable hint suggesting recovery tools
    assert any(k in detail for k in ("create_canvas", "set_active_canvas", "list_canvases")), detail


def test_canvas_id_default_400(mcp_token_a):
    r = requests.post(
        f"{BASE}/api/mcp/{mcp_token_a}/api/elements",
        params={"canvasId": "default"},
        json={"type": "rectangle", "x": 1, "y": 2, "width": 3, "height": 4},
        timeout=5,
    )
    assert r.status_code == 400, r.text


# ── Invalid MCP token -> 401 ──
def test_invalid_mcp_token_401():
    r = requests.get(
        f"{BASE}/api/mcp/usr_totally_bogus_token/api/elements",
        params={"canvasId": "proj_xxx"},
        timeout=5,
    )
    assert r.status_code == 401, r.text


# ── Regression: server stays responsive after a delete + failed op ──
def test_server_responsive_after_delete(mcp_token_a):
    """Create canvas #1, delete it, hit deleted (should 404), then create #2 and draw ok."""
    # create #1
    r = requests.post(f"{BASE}/api/mcp/{mcp_token_a}/api/canvases",
                      json={"name": "TEST_reg_1"}, timeout=10)
    cid1 = r.json()["canvas"]["id"]
    requests.delete(f"{BASE}/api/mcp/{mcp_token_a}/api/canvases/{cid1}", timeout=5)

    # deleted -> 404
    r = requests.post(
        f"{BASE}/api/mcp/{mcp_token_a}/api/elements",
        params={"canvasId": cid1},
        json={"type": "rectangle", "x": 0, "y": 0, "width": 1, "height": 1},
        timeout=5,
    )
    assert r.status_code == 404

    # create #2 + draw -> success
    r = requests.post(f"{BASE}/api/mcp/{mcp_token_a}/api/canvases",
                      json={"name": "TEST_reg_2"}, timeout=10)
    assert r.status_code == 200
    cid2 = r.json()["canvas"]["id"]
    try:
        r = requests.post(
            f"{BASE}/api/mcp/{mcp_token_a}/api/elements",
            params={"canvasId": cid2},
            json={"type": "ellipse", "x": 5, "y": 6, "width": 7, "height": 8},
            timeout=10,
        )
        assert r.status_code == 200, r.text
        assert r.json().get("success") is True
    finally:
        requests.delete(f"{BASE}/api/mcp/{mcp_token_a}/api/canvases/{cid2}", timeout=5)
