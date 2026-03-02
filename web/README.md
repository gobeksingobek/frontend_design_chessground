# ChessGround Web (Phase 1 Shell)

This folder introduces a web-first shell using Next.js + TypeScript.

## Included in Phase 1

- App shell with sidebar + topbar (`/overview`, `/games`, `/sidelines`).
- Phase 2 Games migration: live games list and game details view from backend `/games` APIs.
- Placeholder auth gate + login flow for future real auth.
- Typed API client for backend sideline endpoints.
- React Query provider + first query-driven table on Overview/Sidelines pages.

## Run

```bash
cd web
npm install
npm run dev
```

Set env vars:

- `NEXT_PUBLIC_API_BASE_URL` (default `http://localhost:8000`)
- `NEXT_PUBLIC_API_TOKEN` (default `dev-token`)

For Render deployments, `NEXT_PUBLIC_API_BASE_URL` must point to your deployed API service URL.

## Notes

- This is intentionally a thin shell to unblock feature migration in later phases.
- Phase 2 should migrate Games and Game Details views with real backend data.


## Phase 3 additions

- Games detail page can enqueue sideline jobs directly via `POST /sidelines` using selected move FEN + branch UCI input.
- Login now stores the actual bearer token in browser storage and API client reads it for authenticated requests.
