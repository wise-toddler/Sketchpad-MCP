"""
Excalidraw MCP Cloud — FastAPI gateway.

Responsibilities:
  - Emergent-managed Google authentication (session cookie + Bearer fallback)
  - User / project CRUD in MongoDB (per-user isolation)
  - Durable persistence of canvas scenes (Mongo = source of truth, engine = hot cache)
  - Authorized REST proxy to the Node canvas engine (injects shared secret + canvasId)
  - WebSocket proxy for live canvas sync
  - External MCP endpoint: per-project agent token -> engine, gateway enforces isolation
"""
import os
import uuid
import asyncio
import logging
import secrets as pysecrets
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional, List

import httpx
import websockets
from fastapi import FastAPI, APIRouter, Request, Response, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, PlainTextResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
ENGINE_URL = os.environ["ENGINE_URL"].rstrip("/")
ENGINE_WS_URL = os.environ["ENGINE_WS_URL"].rstrip("/")
ENGINE_SECRET = os.environ["ENGINE_SHARED_SECRET"]
EMERGENT_AUTH_URL = os.environ["EMERGENT_AUTH_URL"]

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("gateway")

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

app = FastAPI(title="Excalidraw MCP Cloud Gateway")
api_router = APIRouter(prefix="/api")

http = httpx.AsyncClient(timeout=60.0)
ENGINE_HEADERS = {"x-engine-secret": ENGINE_SECRET}

# project_ids already hydrated (Mongo -> engine) in this process lifetime
_hydrated: set = set()
SESSION_DAYS = 7


# ─────────────────────────── Models ───────────────────────────
class SessionRequest(BaseModel):
    session_id: str


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: Optional[str] = ""


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=120)
    description: Optional[str] = None


class ScenePut(BaseModel):
    elements: List[dict] = []
    files: dict = {}
    client_id: Optional[str] = None


# ─────────────────────────── Auth helpers ───────────────────────────
def _extract_token(request: Request) -> Optional[str]:
    token = request.cookies.get("session_token")
    if token:
        return token
    auth = request.headers.get("Authorization") or request.headers.get("authorization")
    if auth and auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


async def _user_from_token(token: str) -> Optional[dict]:
    if not token:
        return None
    sess = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not sess:
        return None
    expires_at = sess["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        return None
    return await db.users.find_one({"user_id": sess["user_id"]}, {"_id": 0})


async def get_current_user(request: Request) -> dict:
    user = await _user_from_token(_extract_token(request))
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


async def _owned_project(project_id: str, user: dict) -> dict:
    proj = await db.projects.find_one({"project_id": project_id, "user_id": user["user_id"]}, {"_id": 0})
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    return proj


# ─────────────────────────── Access / sharing model ───────────────────────────
PUBLIC_EMAIL_DOMAINS = {
    "gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "live.com",
    "yahoo.com", "yahoo.co.in", "icloud.com", "me.com", "mac.com", "proton.me",
    "protonmail.com", "pm.me", "aol.com", "msn.com", "gmx.com", "mail.com",
    "zoho.com", "yandex.com", "hey.com", "fastmail.com",
}
ROLE_RANK = {"viewer": 1, "commenter": 2, "editor": 3, "owner": 4}
VALID_SHARE_ROLES = {"viewer", "commenter", "editor"}


def _domain(email):
    if not email or "@" not in email:
        return None
    return email.split("@", 1)[1].lower()


def _is_public_domain(dom):
    return (dom is None) or (dom in PUBLIC_EMAIL_DOMAINS)


async def get_current_user_optional(request: Request):
    return await _user_from_token(_extract_token(request))


def _share_token(request: Request):
    return (request.query_params.get("share")
            or request.headers.get("x-share-token")
            or request.headers.get("X-Share-Token"))


async def resolve_access(project: dict, user: Optional[dict], share_token: Optional[str] = None):
    """Highest role the caller has on this project, or None."""
    if user and user.get("user_id") == project.get("user_id"):
        return "owner"
    roles = []
    email = (user.get("email") or "").lower() if user else None
    if email:
        m = await db.project_members.find_one(
            {"project_id": project["project_id"], "email": email}, {"_id": 0})
        if m:
            roles.append(m.get("role", "viewer"))
    wa = project.get("workspace_access", "none")
    if user and wa != "none":
        pdom = project.get("workspace_domain")
        if pdom and not _is_public_domain(pdom) and _domain(email) == pdom:
            roles.append(wa)
    la = project.get("link_access", "none")
    if share_token and la != "none" and share_token == project.get("share_token"):
        roles.append(la if user else "viewer")  # anonymous link = view only
    if not roles:
        return None
    return max(roles, key=lambda r: ROLE_RANK.get(r, 0))


async def require_access(project_id: str, request: Request, min_role: str = "viewer"):
    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Canvas not found")
    user = await get_current_user_optional(request)
    role = await resolve_access(project, user, _share_token(request))
    if role is None or ROLE_RANK[role] < ROLE_RANK[min_role]:
        if user is None:
            raise HTTPException(status_code=401, detail="Sign in required to access this canvas")
        raise HTTPException(status_code=403, detail="You don't have access to this canvas")
    return project, role, user


def _new_project(user: dict, name: str, description: str = "") -> dict:
    now = datetime.now(timezone.utc).isoformat()
    dom = _domain(user.get("email"))
    return {
        "project_id": f"proj_{uuid.uuid4().hex[:16]}",
        "user_id": user["user_id"],
        "name": name,
        "description": description or "",
        "agent_token": f"agt_{uuid.uuid4().hex}",
        "element_count": 0,
        "link_access": "none",
        "workspace_access": "none",
        "workspace_domain": (None if _is_public_domain(dom) else dom),
        "share_token": f"shr_{uuid.uuid4().hex}",
        "created_at": now,
        "updated_at": now,
    }


async def _persist_new_project(project: dict):
    await db.projects.insert_one(dict(project))
    await db.scenes.insert_one({"project_id": project["project_id"], "elements": [],
                                "updated_at": project["created_at"]})


def _project_view(p: dict, role: str) -> dict:
    out = {
        "project_id": p["project_id"],
        "name": p.get("name"),
        "description": p.get("description", ""),
        "element_count": p.get("element_count", 0),
        "created_at": p.get("created_at"),
        "updated_at": p.get("updated_at"),
        "role": role,
        "is_owner": role == "owner",
        "link_access": p.get("link_access", "none"),
        "workspace_access": p.get("workspace_access", "none"),
    }
    if role == "owner":
        out["agent_token"] = p.get("agent_token")
        out["share_token"] = p.get("share_token")
        out["workspace_domain"] = p.get("workspace_domain")
    return out


# ─────────────────────────── Engine helpers ───────────────────────────
async def ensure_hydrated(project_id: str):
    """Load a project's persisted scene from Mongo into the engine's hot cache once."""
    if project_id in _hydrated:
        return
    scene = await db.scenes.find_one({"project_id": project_id}, {"_id": 0})
    elements = (scene or {}).get("elements") or []
    try:
        await http.post(
            f"{ENGINE_URL}/api/elements/sync",
            params={"canvasId": project_id},
            json={"elements": elements, "timestamp": datetime.now(timezone.utc).isoformat()},
            headers=ENGINE_HEADERS,
        )
        _hydrated.add(project_id)
    except Exception as exc:
        logger.warning("Hydrate failed for %s: %s", project_id, exc)


async def persist_project_scene(project_id: str):
    """Snapshot the engine canvas back into Mongo (durable store)."""
    try:
        r = await http.get(f"{ENGINE_URL}/api/elements", params={"canvasId": project_id}, headers=ENGINE_HEADERS)
        data = r.json()
        elements = data.get("elements", [])
        await db.scenes.update_one(
            {"project_id": project_id},
            {"$set": {"project_id": project_id, "elements": elements,
                      "updated_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )
        await db.projects.update_one(
            {"project_id": project_id},
            {"$set": {"element_count": len(elements), "updated_at": datetime.now(timezone.utc).isoformat()}},
        )
    except Exception as exc:
        logger.warning("Persist failed for %s: %s", project_id, exc)


# ─────────────────────────── Auth routes ───────────────────────────
@api_router.post("/auth/session")
async def create_session(body: SessionRequest, response: Response):
    try:
        r = await http.get(EMERGENT_AUTH_URL, headers={"X-Session-ID": body.session_id})
    except Exception:
        raise HTTPException(status_code=502, detail="Auth provider unreachable")
    if r.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid session")
    data = r.json()
    email = data["email"]

    existing = await db.users.find_one({"email": email}, {"_id": 0})
    if existing:
        user_id = existing["user_id"]
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {"name": data.get("name"), "picture": data.get("picture")}},
        )
    else:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        await db.users.insert_one({
            "user_id": user_id,
            "email": email,
            "name": data.get("name"),
            "picture": data.get("picture"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    session_token = data.get("session_token") or pysecrets.token_urlsafe(32)
    await db.user_sessions.insert_one({
        "user_id": user_id,
        "session_token": session_token,
        "expires_at": datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS),
        "created_at": datetime.now(timezone.utc),
    })

    response.set_cookie(
        key="session_token", value=session_token, httponly=True, secure=True,
        samesite="none", path="/", max_age=SESSION_DAYS * 24 * 60 * 60,
    )
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    return {"user": user, "session_token": session_token}


@api_router.get("/auth/me")
async def auth_me(user: dict = Depends(get_current_user)):
    return user


@api_router.post("/auth/logout")
async def logout(request: Request, response: Response):
    token = _extract_token(request)
    if token:
        await db.user_sessions.delete_one({"session_token": token})
    response.delete_cookie("session_token", path="/")
    return {"success": True}


@api_router.get("/auth/mcp-token")
async def get_mcp_token(user: dict = Depends(get_current_user)):
    """User-level MCP token: lets an AI agent manage & draw on ALL of this user's canvases."""
    token = user.get("mcp_token")
    if not token:
        token = f"usr_{uuid.uuid4().hex}"
        await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"mcp_token": token}})
    return {"mcp_token": token}


@api_router.post("/auth/mcp-token/rotate")
async def rotate_mcp_token(user: dict = Depends(get_current_user)):
    token = f"usr_{uuid.uuid4().hex}"
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"mcp_token": token}})
    return {"mcp_token": token}


# ─────────────────────────── Project routes ───────────────────────────
def _canvas_shape(p: dict) -> dict:
    """A user's project presented to the MCP agent as a 'canvas'."""
    return {
        "id": p["project_id"],
        "name": p.get("name"),
        "elementCount": p.get("element_count", 0),
        "createdAt": p.get("created_at"),
        "lastAccessedAt": p.get("updated_at"),
    }


def _public_project(p: dict) -> dict:
    return {
        "project_id": p["project_id"],
        "name": p.get("name"),
        "description": p.get("description", ""),
        "agent_token": p.get("agent_token"),
        "element_count": p.get("element_count", 0),
        "created_at": p.get("created_at"),
        "updated_at": p.get("updated_at"),
    }


@api_router.get("/projects")
async def list_projects(user: dict = Depends(get_current_user)):
    uid = user["user_id"]
    email = (user.get("email") or "").lower()
    dom = _domain(email)
    seen = {}
    async for p in db.projects.find({"user_id": uid}, {"_id": 0}).sort("updated_at", -1).limit(200):
        seen[p["project_id"]] = _project_view(p, "owner")
    member_ids = [m["project_id"] async for m in db.project_members.find({"email": email}, {"_id": 0}).limit(500)]
    missing_ids = [pid for pid in member_ids if pid not in seen]
    if missing_ids:
        async for p in db.projects.find({"project_id": {"$in": missing_ids}}, {"_id": 0}):
            role = await resolve_access(p, user)
            if role:
                seen[p["project_id"]] = _project_view(p, role)
    if dom and not _is_public_domain(dom):
        async for p in db.projects.find(
            {"workspace_access": {"$ne": "none"}, "workspace_domain": dom, "user_id": {"$ne": uid}}, {"_id": 0}).limit(500):
            pid = p["project_id"]
            if pid in seen:
                continue
            role = await resolve_access(p, user)
            if role:
                seen[pid] = _project_view(p, role)
    items = list(seen.values())
    items.sort(key=lambda x: (x["is_owner"], x.get("updated_at") or ""), reverse=True)
    return items


@api_router.post("/projects")
async def create_project(body: ProjectCreate, user: dict = Depends(get_current_user)):
    project = _new_project(user, body.name, body.description or "")
    await _persist_new_project(project)
    return _project_view(project, "owner")


@api_router.get("/projects/{project_id}")
async def get_project(project_id: str, request: Request):
    project, role, _ = await require_access(project_id, request, "viewer")
    return _project_view(project, role)


@api_router.patch("/projects/{project_id}")
async def update_project(project_id: str, body: ProjectUpdate, user: dict = Depends(get_current_user)):
    await _owned_project(project_id, user)
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.projects.update_one({"project_id": project_id}, {"$set": updates})
    return _project_view(await db.projects.find_one({"project_id": project_id}, {"_id": 0}), "owner")


@api_router.delete("/projects/{project_id}")
async def delete_project(project_id: str, user: dict = Depends(get_current_user)):
    await _owned_project(project_id, user)
    await db.projects.delete_one({"project_id": project_id})
    await db.scenes.delete_one({"project_id": project_id})
    await db.project_members.delete_many({"project_id": project_id})
    _hydrated.discard(project_id)
    try:
        await http.delete(f"{ENGINE_URL}/api/canvases/{project_id}", headers=ENGINE_HEADERS)
    except Exception:
        pass
    return {"success": True}


@api_router.post("/projects/{project_id}/rotate-token")
async def rotate_token(project_id: str, user: dict = Depends(get_current_user)):
    await _owned_project(project_id, user)
    new_token = f"agt_{uuid.uuid4().hex}"
    await db.projects.update_one({"project_id": project_id}, {"$set": {"agent_token": new_token}})
    return {"agent_token": new_token}


# ─────────────────────────── Sharing (owner only) ───────────────────────────
async def _share_state(project_id: str):
    p = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    members = [{"email": m["email"], "role": m["role"]}
               async for m in db.project_members.find({"project_id": project_id}, {"_id": 0})]
    dom = p.get("workspace_domain")
    return {
        "link_access": p.get("link_access", "none"),
        "workspace_access": p.get("workspace_access", "none"),
        "workspace_domain": dom,
        "workspace_available": bool(dom),
        "share_token": p.get("share_token"),
        "members": members,
    }


@api_router.get("/projects/{project_id}/share")
async def get_share(project_id: str, user: dict = Depends(get_current_user)):
    await _owned_project(project_id, user)
    return await _share_state(project_id)


@api_router.put("/projects/{project_id}/share")
async def update_share(project_id: str, body: dict, user: dict = Depends(get_current_user)):
    p = await _owned_project(project_id, user)
    updates = {}
    if body.get("link_access") in ({"none"} | VALID_SHARE_ROLES):
        updates["link_access"] = body["link_access"]
    if body.get("workspace_access") in ({"none"} | VALID_SHARE_ROLES):
        if body["workspace_access"] != "none" and not p.get("workspace_domain"):
            raise HTTPException(status_code=400, detail="Workspace sharing isn't available for personal email domains")
        updates["workspace_access"] = body["workspace_access"]
    if updates:
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.projects.update_one({"project_id": project_id}, {"$set": updates})
    return await _share_state(project_id)


@api_router.post("/projects/{project_id}/share/rotate-link")
async def rotate_link(project_id: str, user: dict = Depends(get_current_user)):
    await _owned_project(project_id, user)
    tok = f"shr_{uuid.uuid4().hex}"
    await db.projects.update_one({"project_id": project_id}, {"$set": {"share_token": tok}})
    return {"share_token": tok}


@api_router.post("/projects/{project_id}/members")
async def add_member(project_id: str, body: dict, user: dict = Depends(get_current_user)):
    await _owned_project(project_id, user)
    email = (body.get("email") or "").strip().lower()
    role = body.get("role", "viewer")
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="A valid email is required")
    if role not in VALID_SHARE_ROLES:
        role = "viewer"
    if email == (user.get("email") or "").lower():
        raise HTTPException(status_code=400, detail="You already own this canvas")
    await db.project_members.update_one(
        {"project_id": project_id, "email": email},
        {"$set": {"project_id": project_id, "email": email, "role": role,
                  "invited_by": user["user_id"], "created_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True)
    return await _share_state(project_id)


@api_router.patch("/projects/{project_id}/members")
async def update_member(project_id: str, body: dict, user: dict = Depends(get_current_user)):
    await _owned_project(project_id, user)
    email = (body.get("email") or "").strip().lower()
    role = body.get("role", "viewer")
    if role not in VALID_SHARE_ROLES:
        role = "viewer"
    await db.project_members.update_one({"project_id": project_id, "email": email}, {"$set": {"role": role}})
    return await _share_state(project_id)


@api_router.delete("/projects/{project_id}/members")
async def remove_member(project_id: str, email: str, user: dict = Depends(get_current_user)):
    await _owned_project(project_id, user)
    await db.project_members.delete_one({"project_id": project_id, "email": email.strip().lower()})
    return await _share_state(project_id)


# ─────────────────────────── Scene routes ───────────────────────────
@api_router.get("/projects/{project_id}/scene")
async def get_scene(project_id: str, request: Request):
    await require_access(project_id, request, "viewer")
    await ensure_hydrated(project_id)
    r = await http.get(f"{ENGINE_URL}/api/elements", params={"canvasId": project_id}, headers=ENGINE_HEADERS)
    return r.json()


@api_router.put("/projects/{project_id}/scene")
async def put_scene(project_id: str, body: ScenePut, request: Request):
    await require_access(project_id, request, "editor")
    await http.post(
        f"{ENGINE_URL}/api/elements/sync",
        params={"canvasId": project_id},
        json={"elements": body.elements, "timestamp": datetime.now(timezone.utc).isoformat(),
              "clientId": body.client_id},
        headers=ENGINE_HEADERS,
    )
    _hydrated.add(project_id)
    await db.scenes.update_one(
        {"project_id": project_id},
        {"$set": {"project_id": project_id, "elements": body.elements,
                  "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    await db.projects.update_one(
        {"project_id": project_id},
        {"$set": {"element_count": len(body.elements), "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {"success": True, "count": len(body.elements)}


@api_router.post("/projects/{project_id}/simulate")
async def simulate_ai_draw(project_id: str, request: Request):
    """Draw a small demo diagram on the canvas (lets users see live sync without an external agent)."""
    await require_access(project_id, request, "editor")
    await ensure_hydrated(project_id)
    demo = [
        {"type": "rectangle", "x": 120, "y": 120, "width": 200, "height": 90,
         "backgroundColor": "#6366f1", "strokeColor": "#c7d2fe", "text": "AI Agent", "fontSize": 20},
        {"type": "rectangle", "x": 480, "y": 120, "width": 200, "height": 90,
         "backgroundColor": "#10b981", "strokeColor": "#a7f3d0", "text": "Live Canvas", "fontSize": 20},
        {"type": "arrow", "x": 0, "y": 0, "startElementId": "n1", "endElementId": "n2",
         "strokeColor": "#f59e0b"},
    ]
    demo[0]["id"] = "n1"
    demo[1]["id"] = "n2"
    r = await http.post(f"{ENGINE_URL}/api/elements/batch", params={"canvasId": project_id},
                        json={"elements": demo}, headers=ENGINE_HEADERS)
    await persist_project_scene(project_id)
    return r.json()


# ─────────────── External MCP endpoint (per-project agent token) ───────────────
async def _project_from_agent_token(agent_token: str) -> dict:
    proj = await db.projects.find_one({"agent_token": agent_token}, {"_id": 0})
    if not proj:
        raise HTTPException(status_code=401, detail="Invalid agent token")
    return proj


@api_router.api_route("/engine/{agent_token}/api/{path:path}",
                      methods=["GET", "POST", "PUT", "DELETE"])
async def mcp_proxy(agent_token: str, path: str, request: Request):
    """Proxy an external MCP agent's engine calls, scoped to the token's project.

    canvasId is forced server-side (never trusted from the client) — this is the
    per-user isolation guarantee the original engine lacked.
    """
    proj = await _project_from_agent_token(agent_token)
    project_id = proj["project_id"]
    await ensure_hydrated(project_id)

    params = dict(request.query_params)
    params.pop("canvasId", None)
    params["canvasId"] = project_id

    body = await request.body()
    fwd_headers = {"x-engine-secret": ENGINE_SECRET}
    if request.headers.get("content-type"):
        fwd_headers["content-type"] = request.headers["content-type"]

    try:
        resp = await http.request(
            request.method, f"{ENGINE_URL}/api/{path}",
            params=params, content=body, headers=fwd_headers,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Engine error: {exc}")

    if request.method in ("POST", "PUT", "DELETE"):
        asyncio.create_task(persist_project_scene(project_id))

    return Response(content=resp.content, status_code=resp.status_code,
                    media_type=resp.headers.get("content-type", "application/json"))


# ───────── User-level MCP endpoint (one token manages ALL the user's canvases) ─────────
async def _user_from_mcp_token(user_token: str) -> dict:
    user = await db.users.find_one({"mcp_token": user_token}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid MCP token")
    return user


@api_router.api_route("/mcp/{user_token}/api/{path:path}",
                      methods=["GET", "POST", "PUT", "DELETE"])
async def user_mcp_proxy(user_token: str, path: str, request: Request):
    """User-scoped MCP proxy.

    - /api/canvases            -> the user's projects (list / create)
    - /api/canvases/{id}       -> get / delete an owned project
    - everything else          -> element/scene/export ops on ?canvasId=<owned project>
    Ownership is verified on every call, so one token safely spans all the
    user's canvases without leaking into anyone else's.
    """
    user = await _user_from_mcp_token(user_token)
    uid = user["user_id"]
    method = request.method

    # ---- Canvas management, mapped onto the user's projects (owned + shared) ----
    if path == "canvases":
        if method == "GET":
            email = (user.get("email") or "").lower()
            seen = {}
            async for p in db.projects.find({"user_id": uid}, {"_id": 0}).sort("updated_at", -1).limit(200):
                seen[p["project_id"]] = _canvas_shape(p)
            member_ids = [m["project_id"] async for m in db.project_members.find({"email": email, "role": "editor"}, {"_id": 0}).limit(500)]
            missing_ids = [pid for pid in member_ids if pid not in seen]
            if missing_ids:
                async for p in db.projects.find({"project_id": {"$in": missing_ids}}, {"_id": 0}):
                    seen[p["project_id"]] = _canvas_shape(p)
            dom = _domain(email)
            if dom and not _is_public_domain(dom):
                async for p in db.projects.find(
                    {"workspace_access": "editor", "workspace_domain": dom, "user_id": {"$ne": uid}}, {"_id": 0}).limit(500):
                    if p["project_id"] not in seen:
                        seen[p["project_id"]] = _canvas_shape(p)
            items = list(seen.values())
            return {"success": True, "canvases": items, "count": len(items)}
        if method == "POST":
            try:
                body = await request.json()
            except Exception:
                body = {}
            project = _new_project(user, (body or {}).get("name") or "Untitled canvas")
            await _persist_new_project(project)
            return {"success": True, "canvas": _canvas_shape(project)}
        raise HTTPException(status_code=405, detail="Method not allowed")

    if path.startswith("canvases/"):
        cid = path.split("/", 1)[1]
        proj = await db.projects.find_one({"project_id": cid}, {"_id": 0})
        if not proj:
            raise HTTPException(status_code=404, detail="Canvas not found")
        role = await resolve_access(proj, user)
        if not role:
            raise HTTPException(status_code=403, detail="You don't have access to this canvas")
        if method == "GET":
            return {"success": True, "canvas": _canvas_shape(proj)}
        if method == "DELETE":
            if role != "owner":
                raise HTTPException(status_code=403, detail="Only the owner can delete this canvas")
            await db.projects.delete_one({"project_id": cid})
            await db.scenes.delete_one({"project_id": cid})
            await db.project_members.delete_many({"project_id": cid})
            _hydrated.discard(cid)
            try:
                await http.delete(f"{ENGINE_URL}/api/canvases/{cid}", headers=ENGINE_HEADERS)
            except Exception:
                pass
            return {"success": True, "message": f"Canvas {cid} deleted"}
        raise HTTPException(status_code=405, detail="Method not allowed")

    # ---- Element / scene / export ops: require editor access to the canvasId ----
    params = dict(request.query_params)
    canvas_id = params.pop("canvasId", None)
    if not canvas_id or canvas_id == "default":
        raise HTTPException(
            status_code=400,
            detail="No active canvas. Call create_canvas or set_active_canvas (to a canvas id from list_canvases) first.",
        )
    proj = await db.projects.find_one({"project_id": canvas_id}, {"_id": 0})
    if not proj:
        raise HTTPException(
            status_code=404,
            detail=(f"Canvas '{canvas_id}' not found — it may have been deleted. "
                    "Call list_canvases and set_active_canvas to pick a valid canvas, or create_canvas."),
        )
    role = await resolve_access(proj, user)
    if not role:
        raise HTTPException(status_code=403, detail="You do not have access to this canvas")
    if method in ("POST", "PUT", "DELETE") and ROLE_RANK[role] < ROLE_RANK["editor"]:
        raise HTTPException(status_code=403, detail="You have view-only access to this canvas")

    await ensure_hydrated(canvas_id)
    params["canvasId"] = canvas_id
    body = await request.body()
    fwd_headers = {"x-engine-secret": ENGINE_SECRET}
    if request.headers.get("content-type"):
        fwd_headers["content-type"] = request.headers["content-type"]

    try:
        resp = await http.request(method, f"{ENGINE_URL}/api/{path}",
                                  params=params, content=body, headers=fwd_headers)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Engine error: {exc}")

    if method in ("POST", "PUT", "DELETE"):
        asyncio.create_task(persist_project_scene(canvas_id))

    return Response(content=resp.content, status_code=resp.status_code,
                    media_type=resp.headers.get("content-type", "application/json"))


# ─────────────────────────── WebSocket proxy ───────────────────────────
@app.websocket("/api/ws/canvas/{project_id}")
async def ws_canvas(websocket: WebSocket, project_id: str):
    # Auth: session cookie / ?token= (session or agent), and ?share= link token.
    token = websocket.cookies.get("session_token") or websocket.query_params.get("token")
    share = websocket.query_params.get("share")
    project = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if not project:
        await websocket.close(code=4404)
        return
    user = await _user_from_token(token) if token else None
    role = await resolve_access(project, user, share)
    if role is None and token:
        atproj = await db.projects.find_one({"agent_token": token, "project_id": project_id}, {"_id": 0})
        if atproj:
            role = "editor"
    if role is None:
        await websocket.close(code=4401)
        return

    await websocket.accept()
    await ensure_hydrated(project_id)

    upstream_url = f"{ENGINE_WS_URL}/?canvasId={project_id}"
    try:
        async with websockets.connect(upstream_url, max_size=None) as upstream:
            async def client_to_engine():
                try:
                    while True:
                        msg = await websocket.receive_text()
                        await upstream.send(msg)
                except Exception:
                    return

            async def engine_to_client():
                try:
                    async for msg in upstream:
                        await websocket.send_text(msg if isinstance(msg, str) else msg.decode())
                except Exception:
                    return

            t1 = asyncio.create_task(client_to_engine())
            t2 = asyncio.create_task(engine_to_client())
            # When either side ends (client disconnect OR server shutdown), tear the
            # other down immediately so the connection can't wedge graceful shutdown.
            _, pending = await asyncio.wait({t1, t2}, return_when=asyncio.FIRST_COMPLETED)
            for t in pending:
                t.cancel()
    except Exception as exc:
        logger.warning("WS proxy error for %s: %s", project_id, exc)
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


@api_router.get("/")
async def root():
    return {"service": "excalidraw-mcp-cloud-gateway", "status": "ok"}


SKILL_PATH = Path("/app/engine/skills/excalidraw-cloud-skill/SKILL.md")


@api_router.get("/agent-skill")
async def agent_skill():
    """The Agent Skill (SKILL.md) that teaches an AI agent how to use this hosted MCP."""
    try:
        text = SKILL_PATH.read_text(encoding="utf-8")
    except Exception:
        text = "# Excalidraw MCP Cloud — Agent Skill\n\nSkill file not found."
    return PlainTextResponse(text, media_type="text/markdown; charset=utf-8")


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def _shutdown():
    await http.aclose()
    client.close()
