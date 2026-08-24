# Excalidraw MCP — Hardened & Self-Hostable

## Original problem statement
Production-leaning version of `wise-toddler/mcp_excalidraw`: keep the AI-controllable Node/TS
canvas+MCP engine, fix its real bugs, and wrap it in an authenticated, persistent app layer
(FastAPI gateway + MongoDB + React UI). Web-based, multi-user-capable, self-hostable.

## User choices (iteration 1)
- Auth: Emergent-managed Google social login.
- Keep + patch the real Node/TS engine (cloned, not rewritten).
- External MCP endpoint via per-project agent token (in-app AI assistant + LLM deferred).
- Exports on-the-fly (no object storage yet).
- Build visible app first, then Phase-1 engine bug fixes + tests.

## Architecture
```
React UI ─┐
AI Agent ──┤─► FastAPI gateway (auth, projects, persistence, proxy) ─► MongoDB
          └─► Node canvas+MCP engine (:3100, internal) ─► WebSocket ─► browser (via gateway proxy)
```
- Gateway proxies ALL engine REST + WebSocket (pod-internal engine, one external URL).
- Engine hardened: x-engine-secret required on /api/*, CORS closed.

## Personas
- Developer using an AI agent (Claude Code/Cursor) to draw diagrams programmatically.
- Team member logging in to view/edit their own persistent canvases in the browser.

## Core requirements (static)
- Google login, per-user isolated projects, durable scenes, live canvas sync, external MCP endpoint.

## Implemented (2026-06)
- **Phase 1 engine fixes (patched + regression-tested, vitest 105/105):**
  - False-success on create/batch fixed (`sync.ts` returns null on sync failure like update).
  - Ungroup / `get_resource:'scene'` now read from the canvas server (groups derived from
    element.groupIds via new `GET /api/scene`); ephemeral `sceneState` removed.
  - `labelPosition` logic de-duplicated into `helpers.expandLabelPosition` (used by
    create_element + batch_create_elements).
- **FastAPI gateway:** Emergent Google auth (session cookie + Bearer), projects CRUD,
  scene GET/PUT persistence, `/simulate`, authorized REST + WebSocket proxy, external MCP
  endpoint `/api/engine/{agent_token}/api/...` (server-side canvasId forcing = isolation).
- **MongoDB persistence:** users, user_sessions, projects, scenes (durable; engine = hot cache,
  hydrated on open, snapshotted on writes).
- **Engine hardening:** shared-secret middleware, closed CORS; unauth clear now blocked.
- **React UI:** Google login, project dashboard (create/rename/delete/search), embedded live
  Excalidraw canvas (@excalidraw/excalidraw 0.18), MCP connect panel (token/config/rotate),
  Simulate AI Draw, PNG/SVG/.excalidraw export.
- **Fix:** WebSocket proxy teardown (FIRST_COMPLETED + cancel) so uvicorn --reload no longer
  wedges the backend when a canvas is open (root cause of the login-hang report).

## Verification
- Backend: testing agent 16/16 pass (auth, isolation, MCP proxy, persistence, engine hardening).
- Engine: vitest 105/105 (96 original + 9 new Phase-1 regression tests).
- Frontend: screenshots confirm login, dashboard, and live canvas with agent-drawn shapes.

## Backlog (prioritized)
- P1: In-app AI Assistant (LLM-driven drawing chat) — user deferred, LLM TBD.
- P1: excalidraw.com export button in UI (currently MCP-tool only) + optional object storage for
  thumbnails/shareable image links.
- P2: Live multi-user co-editing within one project (presence, cursors).
- P2: Debounce per-project persistence + audit log when a client supplies a differing canvasId.
- P2: Dockerized deploy docs + headless screenshot/mermaid export path; harden launch.sh.

## Next tasks
- Confirm real Google login end-to-end with the user (backend now healthy).
- Decide LLM for the in-app assistant when the user is ready.
