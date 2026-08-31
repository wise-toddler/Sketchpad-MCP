<div align="center">

# Sketchpad MCP

**A self-hostable, multi-user Excalidraw canvas that your AI agents can draw on — live.**

Google login · per-user projects · Notion-style sharing · real-time co-editing · an MCP endpoint your coding agent can drive.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](./LICENSE)
![Stack](https://img.shields.io/badge/stack-React%20%C2%B7%20FastAPI%20%C2%B7%20Node%20%C2%B7%20MongoDB-informational)

</div>

---

## What is this?

Sketchpad MCP wraps the excellent [`yctimlin/mcp_excalidraw`](https://github.com/yctimlin/mcp_excalidraw)
canvas + MCP engine in a hardened, authenticated, persistent application layer so a **team** (and their
**AI agents**) can share one live Excalidraw surface.

- 🔐 **Google sign-in** and per-user project isolation
- 💾 **Durable persistence** — canvases live in MongoDB, not just engine memory
- 🤝 **Notion-style sharing** — invite by email, share a link (view/edit), or open to your whole email domain
- 🟢 **Real-time co-editing** — live element sync + collaborator cursors
- 🤖 **AI agent endpoint** — give Claude Code / Cursor / any MCP client a scoped token to list, create, and draw on your canvases
- 🌗 **Light / dark themes**
- 📤 **Exports** — PNG / SVG / `.excalidraw`

## Architecture

```
                 ┌─────────────────────────────────────────┐
  React UI ─────►│                                          │
                 │   FastAPI gateway  (auth, projects,      │────► MongoDB
  AI Agent ─────►│   persistence, authorized proxy)         │
  (MCP token)    │                                          │
                 └───────────────────┬──────────────────────┘
                                     │ x-engine-secret (internal only)
                                     ▼
                 ┌─────────────────────────────────────────┐
                 │  Node / TS canvas + MCP engine (:3100)   │──► WebSocket ──► browsers
                 └─────────────────────────────────────────┘
```

- The **Node engine is internal only.** The browser and agents never talk to it directly — every request
  goes through the FastAPI gateway, which injects auth + a shared secret and forces the correct `canvasId`
  (this is the per-user isolation the raw engine lacks).
- `frontend/` — React + Tailwind + shadcn/ui SPA (embeds `@excalidraw/excalidraw`)
- `backend/`  — FastAPI gateway (Motor / MongoDB), REST + WebSocket proxy, MCP endpoint
- `engine/`   — patched `mcp_excalidraw` Node/TypeScript engine

## Quick start (local)

**Prerequisites:** Node ≥ 20, Python ≥ 3.11, MongoDB, and [Yarn](https://yarnpkg.com/).

```bash
# 1. Engine (internal canvas + MCP)
cd engine
cp .env.example .env          # set a strong ENGINE_SHARED_SECRET
npm ci && npm run build
PORT=3100 npm run canvas      # or: node dist/server.js

# 2. Backend gateway
cd ../backend
cp .env.example .env          # point MONGO_URL at your Mongo; reuse the SAME ENGINE_SHARED_SECRET
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8001

# 3. Frontend
cd ../frontend
cp .env.example .env          # set REACT_APP_BACKEND_URL to your gateway URL
yarn install && yarn start
```

Open the frontend, sign in, create a canvas, and open the **Connect Agent** panel to wire up an MCP client.

## Configuration

Every service is configured through its own `.env` (see the `.env.example` in each folder). Nothing is hardcoded.

| Service    | Key                    | What it is |
|------------|------------------------|------------|
| `backend`  | `MONGO_URL`            | MongoDB connection string |
| `backend`  | `DB_NAME`              | Database name |
| `backend`  | `ENGINE_URL` / `ENGINE_WS_URL` | Internal engine HTTP / WS address |
| `backend`  | `ENGINE_SHARED_SECRET` | Shared secret the gateway sends to the engine (**must match `engine`**) |
| `backend`  | `EMERGENT_AUTH_URL`    | Auth session-exchange endpoint (see note below) |
| `backend`  | `CORS_ORIGINS`         | Allowed origins (`*` for dev) |
| `frontend` | `REACT_APP_BACKEND_URL`| Public URL of the gateway |
| `engine`   | `PORT` / `HOST`        | Engine bind address (keep internal) |
| `engine`   | `ENGINE_SHARED_SECRET` | Same secret as the gateway |

> ### ⚠️ Authentication note (read before self-hosting)
> This project uses **Emergent-managed Google OAuth** (`EMERGENT_AUTH_URL`) for zero-config sign-in on the
> [Emergent](https://emergent.sh) platform. If you self-host **outside** Emergent, this is the one piece that
> won't work as-is — swap the session exchange in `backend/server.py` (`/api/auth/session`) for your own
> Google OAuth (or any OIDC) provider. Everything else is provider-agnostic. Similarly, the
> `@emergentbase/visual-edits` dev-dependency in `frontend/package.json` is Emergent-specific and can be
> removed for a pure self-host.

## Using it with an AI agent (MCP)

Each user gets a scoped **MCP token**. Point your MCP client at:

```
{BACKEND_URL}/api/engine/{agent_token}/api/...
```

The gateway scopes the token to that user's canvases and forces the `canvasId` server-side, so an agent can
`list_canvases`, `create_canvas`, `set_active_canvas`, and draw — without ever touching another user's data.
The in-app **Connect Agent** panel shows the token and a ready-to-paste config; the agent skill lives in
`engine/skills/excalidraw-cloud-skill/SKILL.md` and is served at `GET /api/agent-skill`.

## Deployment

The app runs as three services (frontend, backend, engine) plus MongoDB. Any container platform works — keep
the engine on a private network and expose only the gateway + frontend. See [`CONTRIBUTING.md`](./CONTRIBUTING.md)
for the dev workflow.

## Tests

- Engine: `cd engine && npm test` (vitest)
- Backend: `cd backend && pytest` (see `tests/`)

## Security

Please report vulnerabilities privately — see [`SECURITY.md`](./SECURITY.md). Never commit real `.env` files;
only the `.env.example` templates are tracked.

## Credits & license

Sketchpad MCP is **MIT-licensed** (see [`LICENSE`](./LICENSE)). It builds on other people's great work — full
attribution is in [`NOTICE`](./NOTICE):

- The canvas + MCP engine is derived from [`yctimlin/mcp_excalidraw`](https://github.com/yctimlin/mcp_excalidraw) (MIT).
- The canvas itself is [Excalidraw](https://github.com/excalidraw/excalidraw) (MIT).

**Not affiliated with, sponsored by, or endorsed by Excalidraw.** "Excalidraw" is used only to describe
interoperability with the open-source Excalidraw project.
