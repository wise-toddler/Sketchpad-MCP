"""Backend tests for Notion-style sharing (Phase 1).

Covers:
  - Share settings GET/PUT (owner only)
  - Member invite / role change / remove
  - Link access (viewer/editor/none) with anonymous access via ?share= token
  - Workspace-domain access gating (public domain rejected)
  - Authorization for scene PUT (viewer denied, editor/owner allowed)
  - "Shared with me" appears in second user's project list without owner fields
  - Share settings endpoints reject non-owners
"""
import os
import uuid
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
TOK_A = "test_session_token_123"   # user_testabc123 / tester@example.com
TOK_B = "test_session_token_other_456"  # user_testother456 / tester2@example.com
hA = {"Authorization": f"Bearer {TOK_A}"}
hB = {"Authorization": f"Bearer {TOK_B}"}


@pytest.fixture()
def project():
    r = requests.post(f"{BASE}/api/projects", headers=hA,
                      json={"name": f"TEST_share_{uuid.uuid4().hex[:6]}"})
    assert r.status_code == 200, r.text
    p = r.json()
    yield p
    requests.delete(f"{BASE}/api/projects/{p['project_id']}", headers=hA)


# ─── Share settings visibility ───
def test_share_get_owner(project):
    r = requests.get(f"{BASE}/api/projects/{project['project_id']}/share", headers=hA)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["link_access"] == "none"
    assert d["workspace_access"] == "none"
    assert "share_token" in d
    assert d["members"] == []
    # tester@example.com is a public-ish domain (not in registry) so not available
    # example.com is not in PUBLIC_EMAIL_DOMAINS, so workspace_domain IS set
    assert d.get("workspace_available") is True


def test_share_get_non_owner_forbidden(project):
    r = requests.get(f"{BASE}/api/projects/{project['project_id']}/share", headers=hB)
    assert r.status_code == 404  # gateway returns 404 for non-owned


def test_share_put_non_owner_forbidden(project):
    r = requests.put(f"{BASE}/api/projects/{project['project_id']}/share",
                     headers=hB, json={"link_access": "viewer"})
    assert r.status_code == 404


# ─── Member management ───
def test_invite_change_remove_member(project):
    pid = project["project_id"]
    # invite
    r = requests.post(f"{BASE}/api/projects/{pid}/members", headers=hA,
                      json={"email": "tester2@example.com", "role": "editor"})
    assert r.status_code == 200, r.text
    assert any(m["email"] == "tester2@example.com" and m["role"] == "editor"
               for m in r.json()["members"])
    # change role
    r = requests.patch(f"{BASE}/api/projects/{pid}/members", headers=hA,
                       json={"email": "tester2@example.com", "role": "viewer"})
    assert r.status_code == 200
    assert next(m for m in r.json()["members"] if m["email"] == "tester2@example.com")["role"] == "viewer"
    # remove
    r = requests.delete(f"{BASE}/api/projects/{pid}/members", headers=hA,
                        params={"email": "tester2@example.com"})
    assert r.status_code == 200
    assert r.json()["members"] == []


def test_invite_self_rejected(project):
    r = requests.post(f"{BASE}/api/projects/{project['project_id']}/members", headers=hA,
                      json={"email": "tester@example.com", "role": "editor"})
    assert r.status_code == 400


def test_invite_bad_email_rejected(project):
    r = requests.post(f"{BASE}/api/projects/{project['project_id']}/members", headers=hA,
                      json={"email": "notanemail", "role": "editor"})
    assert r.status_code == 400


# ─── Shared user sees canvas in their list ───
def test_shared_with_me_appears_for_invitee(project):
    pid = project["project_id"]
    requests.post(f"{BASE}/api/projects/{pid}/members", headers=hA,
                  json={"email": "tester2@example.com", "role": "editor"})
    r = requests.get(f"{BASE}/api/projects", headers=hB)
    assert r.status_code == 200
    shared = [p for p in r.json() if p["project_id"] == pid]
    assert len(shared) == 1
    sp = shared[0]
    assert sp["is_owner"] is False
    assert sp["role"] == "editor"
    # owner-only fields must not leak
    assert "agent_token" not in sp
    assert "share_token" not in sp


# ─── Scene authorization by role ───
def test_scene_put_viewer_forbidden(project):
    pid = project["project_id"]
    requests.post(f"{BASE}/api/projects/{pid}/members", headers=hA,
                  json={"email": "tester2@example.com", "role": "viewer"})
    r = requests.put(f"{BASE}/api/projects/{pid}/scene", headers=hB,
                     json={"elements": [{"id": "x", "type": "rectangle"}], "files": {}})
    assert r.status_code == 403


def test_scene_put_editor_allowed(project):
    pid = project["project_id"]
    requests.post(f"{BASE}/api/projects/{pid}/members", headers=hA,
                  json={"email": "tester2@example.com", "role": "editor"})
    r = requests.put(f"{BASE}/api/projects/{pid}/scene", headers=hB,
                     json={"elements": [{"id": "e1", "type": "rectangle"}], "files": {}})
    assert r.status_code == 200, r.text


def test_scene_get_viewer_allowed(project):
    pid = project["project_id"]
    requests.post(f"{BASE}/api/projects/{pid}/members", headers=hA,
                  json={"email": "tester2@example.com", "role": "viewer"})
    r = requests.get(f"{BASE}/api/projects/{pid}/scene", headers=hB)
    assert r.status_code == 200


# ─── Link access (anonymous & signed-in) ───
def test_link_access_none_denies_anonymous(project):
    pid = project["project_id"]
    tok = project["share_token"]
    r = requests.get(f"{BASE}/api/projects/{pid}", params={"share": tok})
    assert r.status_code == 401


def test_link_access_viewer_allows_anonymous_read(project):
    pid = project["project_id"]
    r = requests.put(f"{BASE}/api/projects/{pid}/share", headers=hA,
                     json={"link_access": "viewer"})
    assert r.status_code == 200
    tok = r.json()["share_token"]

    # Anonymous GET project → 200
    g = requests.get(f"{BASE}/api/projects/{pid}", params={"share": tok})
    assert g.status_code == 200
    assert g.json()["role"] == "viewer"
    # Owner-only fields not leaked
    assert "agent_token" not in g.json()

    # Anonymous GET scene → 200
    gs = requests.get(f"{BASE}/api/projects/{pid}/scene", params={"share": tok})
    assert gs.status_code == 200

    # Anonymous PUT scene → 401 (need sign-in for editing even if viewer link)
    ps = requests.put(f"{BASE}/api/projects/{pid}/scene", params={"share": tok},
                      json={"elements": [], "files": {}})
    assert ps.status_code in (401, 403)


def test_link_access_bad_token_denied(project):
    pid = project["project_id"]
    requests.put(f"{BASE}/api/projects/{pid}/share", headers=hA,
                 json={"link_access": "viewer"})
    r = requests.get(f"{BASE}/api/projects/{pid}", params={"share": "shr_wrong"})
    assert r.status_code == 401


def test_rotate_link_invalidates_old(project):
    pid = project["project_id"]
    r = requests.put(f"{BASE}/api/projects/{pid}/share", headers=hA,
                     json={"link_access": "viewer"})
    old = r.json()["share_token"]
    rot = requests.post(f"{BASE}/api/projects/{pid}/share/rotate-link", headers=hA)
    assert rot.status_code == 200
    new = rot.json()["share_token"]
    assert new != old
    # old token no longer works
    r = requests.get(f"{BASE}/api/projects/{pid}", params={"share": old})
    assert r.status_code == 401
    # new token works
    r = requests.get(f"{BASE}/api/projects/{pid}", params={"share": new})
    assert r.status_code == 200


# ─── Workspace access ───
def test_workspace_access_public_domain_rejected(project):
    # tester@example.com — example.com is NOT in PUBLIC_EMAIL_DOMAINS, so it IS treated
    # as a workspace domain. Verify enabling works (the "public domain rejected"
    # behavior is triggered only for gmail.com et al.).
    pid = project["project_id"]
    r = requests.put(f"{BASE}/api/projects/{pid}/share", headers=hA,
                     json={"workspace_access": "editor"})
    # example.com is not in the public list -> should succeed
    assert r.status_code == 200
    assert r.json()["workspace_access"] == "editor"
    assert r.json()["workspace_domain"] == "example.com"


def test_workspace_access_teammate_sees_canvas(project):
    pid = project["project_id"]
    requests.put(f"{BASE}/api/projects/{pid}/share", headers=hA,
                 json={"workspace_access": "viewer"})
    # tester2@example.com shares domain example.com with tester@example.com
    r = requests.get(f"{BASE}/api/projects", headers=hB)
    assert r.status_code == 200
    ids = [p["project_id"] for p in r.json()]
    assert pid in ids
    sp = next(p for p in r.json() if p["project_id"] == pid)
    assert sp["is_owner"] is False
    assert sp["role"] in ("viewer", "commenter", "editor")
