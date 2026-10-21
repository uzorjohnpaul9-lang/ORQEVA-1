# Running ORQEVA live from this PC (local backend)

The site frontend is served by Cloudflare (`https://orqeva.pages.dev`). The
backend API runs on THIS computer and is exposed publicly through a free
Cloudflare quick tunnel.

## Start the site

Double-click `start-local.bat`. It will:

1. Disable Windows sleep while running (re-enabled on exit).
2. Start the backend: `python -m uvicorn backend.main:app` on `127.0.0.1:8001`.
3. Start the tunnel: `cloudflared tunnel --url http://127.0.0.1:8001`.
4. Print a URL like `https://xxxx.trycloudflare.com`.

Press `Ctrl+C` (or close the window) to stop both and re-enable sleep.

## Requirements already on this machine

- Python 3.11.9 + all deps in `requirements.backend.txt`
- `cloudflared` at `C:\Program Files (x86)\cloudflared\cloudflared.exe`
- `.env` in repo root with real keys
- `frontend/.env.production` with the public build-time values (Supabase
  publishable key + the Railway API URL). `frontend/.env.local` overrides it
  locally.

## Deploying the frontend

The dashboard is served by Cloudflare Pages. `wrangler` is pinned in
`frontend/package.json` and the project is described by `frontend/wrangler.toml`,
so the deploy is just:

```bat
cd frontend
set CLOUDFLARE_API_TOKEN=<token with "Cloudflare Pages - Edit">
set CLOUDFLARE_ACCOUNT_ID=75afd35520b239e8dbafaf9c85a2c837
npm run deploy
```

That builds the static export and publishes it. `npm run deploy:pages` skips
the build and publishes the existing `out/`.

`.github/workflows/deploy-frontend.yml` does the same on every push to `main`
that touches `frontend/`, and on demand via **Run workflow**. It needs one
repo secret, `CLOUDFLARE_API_TOKEN`.

Note: Pages configs reject `account_id` in `wrangler.toml`, so the account
comes from `CLOUDFLARE_ACCOUNT_ID` instead.

## IMPORTANT — the tunnel URL can change

Only relevant to the legacy local-backend setup below, where the backend runs
on this PC behind a Cloudflare quick tunnel instead of Railway.

Quick tunnels hand out a NEW random URL every time `cloudflared` starts.
That URL is baked into the frontend at build time. If the URL changes:

```bat
cd frontend
set NEXT_PUBLIC_API_URL=https://<new-tunnel-url>
npm run build
npm run deploy:pages
```

Then the live site works again.

## Health checks

- Backend local: `http://127.0.0.1:8001/api/health`
- Backend public: `https://<tunnel-url>/api/health`
- Admin login works on the tunnel URL; Admin > System shows scheduler.

## Limitations (accepted for now)

- Site is live only while this PC is on, uvicorn runs, and cloudflared runs.
- No permanent URL until a domain + named tunnel (or a VPS) is added.
- Telegram/scanning behave as normal — the scheduler runs in the backend.