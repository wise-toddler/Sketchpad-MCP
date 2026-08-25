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
from fastapi.responses import JSONResponse
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
    cur = db.projects.find({"user_id": user["user_id"]}, {"_id": 0}).sort("updated_at", -1)
    return [_public_project(p) async for p in cur]


@api_router.post("/projects")
async def create_project(body: ProjectCreate, user: dict = Depends(get_current_user)):
    now = datetime.now(timezone.utc).isoformat()
    project = {
        "project_id": f"proj_{uuid.uuid4().hex[:16]}",
        "user_id": user["user_id"],
        "name": body.name,
        "description": body.description or "",
        "agent_token": f"agt_{uuid.uuid4().hex}",
        "element_count": 0,
        "created_at": now,
        "updated_at": now,
    }
    await db.projects.insert_one(dict(project))
    await db.scenes.insert_one({"project_id": project["project_id"], "elements": [], "updated_at": now})
    return _public_project(project)


@api_router.get("/projects/{project_id}")
async def get_project(project_id: str, user: dict = Depends(get_current_user)):
    return _public_project(await _owned_project(project_id, user))


@api_router.patch("/projects/{project_id}")
async def update_project(project_id: str, body: ProjectUpdate, user: dict = Depends(get_current_user)):
    await _owned_project(project_id, user)
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.projects.update_one({"project_id": project_id}, {"$set": updates})
    return _public_project(await db.projects.find_one({"project_id": project_id}, {"_id": 0}))


@api_router.delete("/projects/{project_id}")
async def delete_project(project_id: str, user: dict = Depends(get_current_user)):
    await _owned_project(project_id, user)
    await db.projects.delete_one({"project_id": project_id})
    await db.scenes.delete_one({"project_id": project_id})
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


# ─────────────────────────── Scene routes ───────────────────────────
@api_router.get("/projects/{project_id}/scene")
async def get_scene(project_id: str, user: dict = Depends(get_current_user)):
    await _owned_project(project_id, user)
    await ensure_hydrated(project_id)
    r = await http.get(f"{ENGINE_URL}/api/elements", params={"canvasId": project_id}, headers=ENGINE_HEADERS)
    return r.json()


@api_router.put("/projects/{project_id}/scene")
async def put_scene(project_id: str, body: ScenePut, user: dict = Depends(get_current_user)):
    await _owned_project(project_id, user)
    _hydrated.add(project_id)
    await http.post(
        f"{ENGINE_URL}/api/elements/sync",
        params={"canvasId": project_id},
        json={"elements": body.elements, "timestamp": datetime.now(timezone.utc).isoformat()},
        headers=ENGINE_HEADERS,
    )
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
async def simulate_ai_draw(project_id: str, user: dict = Depends(get_current_user)):
    """Draw a small demo diagram on the canvas (lets users see live sync without an external agent)."""
    await _owned_project(project_id, user)
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

    # ---- Canvas management, mapped onto the user's projects ----
    if path == "canvases":
        if method == "GET":
            cur = db.projects.find({"user_id": uid}, {"_id": 0}).sort("updated_at", -1)
            items = [_canvas_shape(p) async for p in cur]
            return {"success": True, "canvases": items, "count": len(items)}
        if method == "POST":
            try:
                body = await request.json()
            except Exception:
                body = {}
            name = (body or {}).get("name") or "Untitled canvas"
            now = datetime.now(timezone.utc).isoformat()
            project = {
                "project_id": f"proj_{uuid.uuid4().hex[:16]}",
                "user_id": uid, "name": name, "description": "",
                "agent_token": f"agt_{uuid.uuid4().hex}", "element_count": 0,
                "created_at": now, "updated_at": now,
            }
            await db.projects.insert_one(dict(project))
            await db.scenes.insert_one({"project_id": project["project_id"], "elements": [], "updated_at": now})
            return {"success": True, "canvas": _canvas_shape(project)}
        raise HTTPException(status_code=405, detail="Method not allowed")

    if path.startswith("canvases/"):
        cid = path.split("/", 1)[1]
        proj = await db.projects.find_one({"project_id": cid, "user_id": uid}, {"_id": 0})
        if not proj:
            raise HTTPException(status_code=404, detail="Canvas not found")
        if method == "GET":
            return {"success": True, "canvas": _canvas_shape(proj)}
        if method == "DELETE":
            await db.projects.delete_one({"project_id": cid})
            await db.scenes.delete_one({"project_id": cid})
            _hydrated.discard(cid)
            try:
                await http.delete(f"{ENGINE_URL}/api/canvases/{cid}", headers=ENGINE_HEADERS)
            except Exception:
                pass
            return {"success": True, "message": f"Canvas {cid} deleted"}
        raise HTTPException(status_code=405, detail="Method not allowed")

    # ---- Element / scene / export ops: require an owned canvasId ----
    params = dict(request.query_params)
    canvas_id = params.pop("canvasId", None)
    if not canvas_id or canvas_id == "default":
        raise HTTPException(
            status_code=400,
            detail="No active canvas. Call create_canvas or set_active_canvas (to a canvas id from list_canvases) first.",
        )
    proj = await db.projects.find_one({"project_id": canvas_id, "user_id": uid}, {"_id": 0})
    if not proj:
        exists = await db.projects.find_one({"project_id": canvas_id}, {"_id": 0})
        if exists:
            raise HTTPException(status_code=403, detail="You do not own this canvas")
        raise HTTPException(
            status_code=404,
            detail=(f"Canvas '{canvas_id}' not found — it may have been deleted. "
                    "Call list_canvases and set_active_canvas to pick a valid canvas, or create_canvas."),
        )

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
    # Auth: browser sends session_token cookie; external clients may pass ?token=
    token = websocket.cookies.get("session_token") or websocket.query_params.get("token")
    authorized = False
    if token:
        user = await _user_from_token(token)
        if user:
            proj = await db.projects.find_one(
                {"project_id": project_id, "user_id": user["user_id"]}, {"_id": 0})
            authorized = proj is not None
        if not authorized:
            proj = await db.projects.find_one({"agent_token": token, "project_id": project_id}, {"_id": 0})
            authorized = proj is not None
    if not authorized:
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
