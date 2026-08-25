---
name: excalidraw-cloud-skill
description: Draw, edit and refine Excalidraw diagrams on a hosted, authenticated, multi-canvas Excalidraw MCP Cloud account. Use when the agent needs to (1) create or lay out diagrams on a live canvas the human is watching in their browser, (2) manage the user's canvases (list/create/switch/delete), (3) iteratively refine using describe_scene and get_canvas_screenshot, (4) export to .excalidraw / PNG / SVG or a shareable excalidraw.com URL, or (5) convert Mermaid to Excalidraw. This is the USER-LEVEL hosted deployment — one token spans all of the user's canvases and you must pick an active canvas before drawing.
---

# Excalidraw MCP Cloud — Agent Skill (user-level, hosted)

You are connected to a **hosted, per-user** Excalidraw MCP server through a gateway.
One MCP token gives you access to **all of that user's canvases**, but element
operations always act on the **currently active canvas**, so you must choose one first.

## Step 0 — Connection (already done by config)

The user configured their MCP client with:

```json
{
  "mcpServers": {
    "excalidraw": {
      "command": "npx",
      "args": ["-y", "mcp-excalidraw-server"],
      "env": {
        "EXPRESS_SERVER_URL": "https://<host>/api/mcp/<your-user-token>",
        "ENABLE_CANVAS_SYNC": "true"
      }
    }
  }
}
```

If `excalidraw/*` tools appear in your tool list, use them directly. Do **not** try to
`git clone` or run `launch.sh` — this is a hosted deployment, not a local server.

## Step 1 — ALWAYS pick an active canvas first (critical for this deployment)

Element tools (`create_element`, `batch_create_elements`, `update_element`, `delete_element`,
`query_elements`, `get_resource`, exports, etc.) act on the **active canvas**. On a fresh
connection there is **no** active canvas, so drawing will fail until you set one.

```
1. list_canvases                      # discover the user's canvases (id + name + elementCount)
2a. set_active_canvas(canvasId="…")   # to draw on an EXISTING canvas, OR
2b. create_canvas(name="My Diagram")  # to start a NEW canvas (it becomes active automatically)
3. get_active_canvas                  # (optional) confirm what you're targeting
```

**Rule of thumb:** if the user says "draw X here / on this canvas", ask for or use the
canvas id they gave you and call `set_active_canvas`. If they say "make a new diagram",
call `create_canvas`.

## Step 2 — Learn the design conventions before drawing

Call **`read_diagram_guide`** once. It returns the color palette, sizing rules, layout
patterns, arrow-binding best practices, templates, and anti-patterns. Follow it to produce
clean, professional diagrams instead of overlapping boxes.

## Step 3 — Draw (prefer batch)

Use **`batch_create_elements`** to create a whole diagram in one call.

- **Labels:** put `"text": "Login Service"` directly on a shape (auto-centered). Use
  `labelPosition` (`top-left`, `bottom-center`, …) for a free-standing label instead.
- **Arrows:** give shapes custom `id`s, then bind arrows with `startElementId` /
  `endElementId` — Excalidraw auto-routes to the element edges. Don't hand-compute points.
- **Mermaid:** for flowcharts/sequence diagrams, `create_from_mermaid` is fastest.

Example:
```
batch_create_elements(elements=[
  { "id":"a", "type":"rectangle", "x":100, "y":100, "width":200, "height":90, "text":"Client" },
  { "id":"b", "type":"rectangle", "x":460, "y":100, "width":200, "height":90, "text":"API" },
  { "type":"arrow", "startElementId":"a", "endElementId":"b", "text":"HTTP" }
])
```

## Step 4 — See your own work and refine

- **`describe_scene`** → AI-readable summary: element types, positions, connections, labels,
  bounding box. Call this before editing an existing diagram.
- **`get_canvas_screenshot`** → a PNG of the current canvas so you can visually verify.
- Then `update_element` / `batch_update_elements` / `align_elements` / `distribute_elements`
  / `group_elements` to tidy up. Iterate: draw → screenshot → adjust.

## Step 5 — Export / share

- `export_to_excalidraw_url` → an encrypted, shareable excalidraw.com link.
- `export_scene` → `.excalidraw` JSON. `export_to_image` → PNG/SVG.

## Recovery — "canvas not found / may have been deleted" (404)

The active canvas can be deleted by the user (in the web UI) or by you (`delete_canvas`).
If any action returns a message like *"Canvas '…' not found — it may have been deleted"*:

```
1. list_canvases                         # see what still exists
2. set_active_canvas(canvasId="…")       # pick a valid one, OR
   create_canvas(name="…")               # start a new one
3. retry the failed action
```

Other guardrails you may hit:
- **No active canvas / no canvasId** → set or create a canvas first (Step 1).
- **403 (not yours)** → that canvas belongs to another user; you can only touch this
  account's canvases. Use `list_canvases`.

## Canvas-management tools (this deployment adds these)

| Tool | Purpose |
|------|---------|
| `list_canvases` | List the user's canvases (id, name, elementCount) |
| `create_canvas` | Create a canvas and make it active |
| `set_active_canvas` | Switch which canvas element ops target |
| `get_active_canvas` | Show the current active canvas id |
| `delete_canvas` | Delete a canvas (active resets to none if it was active) |

## Full tool list

Elements: `create_element`, `batch_create_elements`, `update_element`, `batch_update_elements`,
`delete_element`, `query_elements`, `get_element`, `duplicate_elements`.
Structure: `group_elements`, `ungroup_elements`, `align_elements`, `distribute_elements`,
`lock_elements`, `unlock_elements`.
Scene/insight: `get_resource`, `describe_scene`, `read_diagram_guide`, `snapshot_scene`,
`restore_snapshot`.
Generate: `create_from_mermaid`.
View/export: `set_viewport`, `get_canvas_screenshot`, `export_to_image`, `export_scene`,
`import_scene`, `export_to_excalidraw_url`, `get_canvas_url`, `undo`, `redo`.

## Golden path (copyable)

> list_canvases → (set_active_canvas OR create_canvas) → read_diagram_guide →
> batch_create_elements → describe_scene / get_canvas_screenshot → refine → export_to_excalidraw_url
