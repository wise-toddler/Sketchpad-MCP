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

## Implemented — Notion-style sharing + real-time co-editing (2026-08)
- **Phase 1 — Notion-style sharing (tested: 16/16 backend + 12/12 UI, iteration_4):**
  - Backend `resolve_access()` composes highest role across owner | member (email invite) |
    workspace-domain | link, with anonymous link capped to viewer.
  - Share endpoints: GET/PUT `/projects/{id}/share`, POST/PATCH/DELETE `/projects/{id}/members`,
    POST `/projects/{id}/share/rotate-link`. Owner-only; `_project_view` hides owner-only fields
    (agent_token/share_token/workspace_domain) from shared users.
  - `GET /projects` returns owned + members-by-email + same-workspace-domain projects with `role`/`is_owner`.
  - Frontend: `Dashboard.js` split into "owned" grid + "Shared with me" section with `ProjectCard`
    + `RoleBadge` (KISS: Viewer/Editor only — Commenter removed from ShareDialog).
  - `ShareDialog.js`: invite by email, general access (link viewer/editor + copy/rotate),
    workspace-domain access (non-public domains only). `CanvasPage` wires ShareDialog + share button.
  - Anonymous `/canvas/{id}?share={token}` viewer link → read-only view; `link_access='none'` denied.
- **Phase 2 — Real-time co-editing (tested: 7/7 backend co-edit + 2-context E2E, iteration_5):**
  - Editor `PUT /projects/{id}/scene` (editor role required) → engine `/api/elements/sync` →
    broadcasts `elements_synced {elements, clientId}` to same-canvas peers. Last-writer-wins
    (full-scene replace on the 500ms debounce window — accepted KISS trade-off).
  - Live presence: engine WS relays `pointer`/`presence_leave` to other same-canvas clients →
    Excalidraw collaborator cursors. Own echo suppressed via per-mount `clientIdRef`.
  - Viewer/anonymous = `viewModeEnabled` (read-only) but still receive live updates.
  - Fixes: per-mount CLIENT_ID (two-tab collision), `_hydrated.add` moved after successful sync.

## Post-login redirect to shared canvas (2026-08)
- Bug: opening an editor share link while signed out and logging in always dumped the user on
  `/dashboard`, losing the invited canvas. Also no sign-in CTA existed on shared canvases.
- Fix: `lib/authRedirect.js` (`startLogin(returnTo)` stores intended path in localStorage;
  `consumePostLoginRedirect()` reads+clears it). `Login.js` + new `CanvasPage` "Sign in to edit"
  button (anon only, data-testid=`canvas-signin-btn`) use it; `AuthCallback` redirects to the
  remembered path after establishing the session. Signed-in users via an editor link get editor
  role (resolve_access), anonymous capped to viewer.
- Verified: sign-in CTA renders for anon on shared canvas, anon role = "View only", click fires
  OAuth redirect. Full OAuth completion not automatable (no scriptable password).

## Notes / accepted trade-offs
- Co-editing is full-scene last-writer-wins (no CRDT). Simultaneous edits within the 500ms debounce
  window can clobber; fine for turn-taking multiplayer, documented as KISS scope.
- `GET /projects/{id}` now returns 403 for authenticated non-members (was 404) to support sharing.


- P1: In-app AI Assistant (LLM-driven drawing chat) — user deferred, LLM TBD.
- P1: excalidraw.com export button in UI (currently MCP-tool only) + optional object storage for
  thumbnails/shareable image links.
- P2: Live multi-user co-editing within one project (presence, cursors).
- P2: Debounce per-project persistence + audit log when a client supplies a differing canvasId.
- P2: Dockerized deploy docs + headless screenshot/mermaid export path; harden launch.sh.

## Next tasks
- Confirm real Google login end-to-end with the user (backend now healthy).
- Decide LLM for the in-app assistant when the user is ready.
