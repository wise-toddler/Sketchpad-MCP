# Contributing to Sketchpad MCP

Thanks for your interest in improving Sketchpad MCP! This guide covers the dev setup and conventions.

## Project layout

```
frontend/   React + Tailwind + shadcn/ui SPA
backend/    FastAPI gateway (auth, projects, persistence, proxy, MCP endpoint)
engine/     Node/TypeScript Excalidraw canvas + MCP engine (internal only)
tests/      Backend (pytest) integration tests
```

## Local development

See the **Quick start** in [`README.md`](./README.md). In short: run the engine (`:3100`), the
backend gateway (`:8001`), and the frontend, each with its own `.env` copied from `.env.example`.
Use the **same** `ENGINE_SHARED_SECRET` in `backend/.env` and `engine/.env`.

## Ground rules

- **Never expose the engine directly.** All browser/agent traffic must go through the FastAPI
  gateway so auth and the shared secret are enforced and `canvasId` is forced server-side.
- **No secrets in the repo.** Only `*.env.example` files are tracked; real `.env` files are gitignored.
- **Config via env vars only** — no hardcoded URLs, ports, or credentials.
- **MongoDB:** never return raw Mongo documents from an API (`ObjectId` isn't JSON-serializable);
  map through the model layer.

## Making changes

1. Fork and create a feature branch.
2. Keep changes focused; match the existing code style.
3. Add/adjust tests where it makes sense.
4. Run the test suites before opening a PR:
   ```bash
   cd engine  && npm test     # vitest
   cd backend && pytest       # gateway integration tests
   ```
5. Open a PR with a clear description of the change and why.

## Reporting bugs & requesting features

Please use GitHub Issues. For security issues, follow [`SECURITY.md`](./SECURITY.md) instead of
filing a public issue.

By contributing, you agree that your contributions will be licensed under the MIT License.
