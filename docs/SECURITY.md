# Security

## Trust Model

- Local loopback access is trusted for Master operations by default.
- LAN Player clients can list worlds and read only role-filtered public data.
- Remote Master reads and every mutation require
  `X-Worldbuilder-Master-Token`.
- `start_worldbuilder.bat` creates a token for LAN mode and places it in the
  private Master URL fragment, not the HTTP query string.

Set `WORLDBUILDER_TRUST_LOCAL_MASTER=false` behind a reverse proxy. Otherwise
the proxy's loopback connection may be treated as a local Master. Use HTTPS or
a trusted VPN when the LAN itself is not trusted because plain HTTP does not
encrypt world data or the Master token header.

Numeric IP hosts are accepted automatically. Add trusted DNS names, separated
by commas, to `WORLDBUILDER_ALLOWED_HOSTS` when using a reverse proxy.

## Implemented Controls

- Player API allowlist with server-side Master enforcement.
- Host validation blocks DNS rebinding; IP hosts and configured names are allowed.
- 10 MiB default request-body limit, including streamed bodies.
- CSP, `nosniff`, frame denial, referrer, and permissions headers.
- Safe `http/https` rendering for user-provided links and images.
- PNG/JPEG/GIF/WebP signature validation and 5 MiB decoded upload limit.
- Referential validation for world imports and SQLite foreign keys enabled.
- Bounded browser chat history and cancellation of stale fetches.
- Automatic cleanup of unreferenced generated image files.

## Residual Risks

- A persisted third-party LLM API key is stored as plain text in the local
  SQLite database. Protect the database with OS account permissions, or prefer
  `WORLDBUILDER_LLM_API_KEY` for secrets that must not be persisted.
- World name and description are public so Players can select a world. Do not
  put Master-only lore in the world description; use secret cards instead.
- This is a local/LAN application, not a multi-tenant identity system. It has
  one shared Master token, no per-user accounts, revocation list, or audit log.

## Audit Snapshot

Checked on 2026-09-13:

- `pytest`: 116 passed;
- `ruff check src tests`: passed;
- `bandit -r src -q`: no findings;
- `pip-audit --local --skip-editable`: no known dependency vulnerabilities;
- `npm audit`: no known frontend dependency vulnerabilities;
- React/Vite production build: passed with Vite 8.1.4.
