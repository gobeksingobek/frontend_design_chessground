# ChessGround Web (Phase 1 Shell)

This folder introduces a web-first shell using Next.js + TypeScript.

## Included in Phase 1

- App shell with sidebar + topbar (`/overview`, `/games`, `/sidelines`).
- Placeholder auth gate + login flow for future real auth.
- Typed API client for backend sideline endpoints.
- React Query provider + first query-driven table on Overview/Sidelines pages.

## Run

```bash
cd web
npm install
npm run dev
```

Set optional env vars:

- `NEXT_PUBLIC_API_BASE_URL` (default `http://localhost:8000`)
- `NEXT_PUBLIC_API_TOKEN` (default `dev-token`)

## Notes

- This is intentionally a thin shell to unblock feature migration in later phases.
- Phase 2 should migrate Games and Game Details views with real backend data.
