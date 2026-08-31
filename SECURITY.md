# Security Policy

## Reporting a vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities.

Instead, report privately via GitHub's
[private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
(Security → Report a vulnerability) or by contacting the maintainers directly.

We aim to acknowledge reports within a few days and will keep you updated on the fix.

## Scope & hardening notes

- The **Node engine has no authentication of its own** and must only be reachable on a private
  network. All external access goes through the FastAPI gateway, which enforces auth and injects
  the `ENGINE_SHARED_SECRET`. Never expose the engine port publicly.
- Use a strong, unique `ENGINE_SHARED_SECRET` shared between the gateway and the engine.
- Set `CORS_ORIGINS` to your real frontend origin in production (avoid `*`).
- Real `.env` files must never be committed — only `.env.example` templates are tracked.
- Share links use unguessable tokens and can be rotated from the Share dialog; rotating a link
  immediately invalidates the old one.
