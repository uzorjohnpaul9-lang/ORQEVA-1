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
- `frontend/.env.local` with `NEXT_PUBLIC_API_URL=<last tunnel URL>`

## IMPORTANT — the tunnel URL can change

Quick tunnels hand out a NEW random URL every time `cloudflared` starts.
That URL is baked into the frontend at build time. If the URL changes:

```bat
cd frontend
set NEXT_PUBLIC_API_URL=https://<new-tunnel-url>
npm run build
npx wrangler pages deploy out --project-name orqeva
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