# Exness live routing - MT5 bridge runbook

Exness has no public REST/FIX API. Orders can only be placed by a MetaTrader 5
terminal, and the `MetaTrader5` Python package only works on Windows next to a
running terminal. The backend on Railway cannot run that, so live Exness orders
go through a small bridge service on an always-on Windows VPS:

```
Railway backend (exness adapter)
        |  HTTPS + X-Bridge-Token
        v
Cloudflare Tunnel -> 127.0.0.1:8100 (bridge/mt5_bridge.py)
        |  MetaTrader5 Python API
        v
Exness MT5 terminal -> Exness servers
```

The bridge holds no credentials: each request carries the user's MT5 login,
server and password, which the backend stores encrypted in
`exchange_connections` like every other venue.

## 1. Windows VPS prerequisites

- Windows Server 2019+ or Windows 10/11 VPS that stays on 24/7.
- Exness MetaTrader 5 terminal installed and logged into the account once.
- In MT5: **Tools -> Options -> Expert Advisors -> Allow algorithmic trading**
  enabled. Keep the terminal running (you may minimise it, but do not log out).
- Python 3.11 **64-bit** (the MT5 package ships 64-bit wheels only).

## 2. Install the bridge

```bat
cd C:\orqeva
python -m venv .venv
.venv\Scripts\activate
pip install -r bridge\requirements.txt
```

Set the environment (Machine-level or in the shell that runs the bridge):

| Variable | Required | Meaning |
|---|---|---|
| `MT5_BRIDGE_TOKEN` | yes | Shared secret; must match Railway's `EXNESS_BRIDGE_TOKEN`. |
| `MT5_TERMINAL_PATH` | no | `terminal64.exe` path when MT5 is not found automatically. |
| `MT5_SYMBOL_SUFFIX` | no | Broker suffix, default `m` (`EURUSD` -> `EURUSDm`). |
| `MT5_DEFAULT_SERVER` | no | Fallback server when a connection is stored as a bare login. |
| `MT5_MAGIC` | no | Magic number on ORQEVA orders, default `20261021`. |
| `MT5_DEVIATION` | no | Max slippage in points, default `20`. |
| `MT5_INIT_TIMEOUT_MS` | no | Login timeout, default `30000`. |

Start it:

```bat
set MT5_BRIDGE_TOKEN=<long-random-secret>
bridge\run_bridge.bat
```

Check locally: `curl http://127.0.0.1:8100/health` ->
`{"status":"ok","mt5_available":true}`.

## 3. Expose it to Railway

The bridge must not listen on a public interface. Use a Cloudflare Tunnel (the
same pattern as `LOCAL-RUN.md`), preferably a **named** tunnel so the URL does
not change on restart:

```bat
cloudflared tunnel --url http://127.0.0.1:8100
```

Then set these on the Railway backend service and redeploy:

```
EXNESS_BRIDGE_URL=https://<tunnel-hostname>
EXNESS_BRIDGE_TOKEN=<same secret as MT5_BRIDGE_TOKEN>
```

Optional: `EXNESS_MT5_SERVER` if you want bare-login credentials to default to
one server.

## 4. Connect an account

Dashboard -> **Exchanges** -> **Exness**:

- **MT5 account**: the numeric Exness account, e.g. `12345678`
- **MT5 server**: from the MT5 login window, e.g. `Exness-MT5Real8`
- **MT5 password**: the trading password (not the investor password)
- **Paper trading mode**: ON for a demo MT5 account; OFF for a real account.
  The adapter refuses to activate a REAL account while paper mode is on.

The dashboard sends the account as `ACCOUNT|SERVER`; API clients may do the
same and leave the server field empty.

## 5. Auto-trade behaviour

- Route **live** + Exness connection => orders are sent to the MT5 account.
- Route **paper** (or a plan below the live-routing tier) => orders stay in the
  ORQEVA paper ledger; Exness is never contacted.
- Order size is converted from ORQEVA base-asset units into MT5 lots using the
  symbol's `trade_contract_size`, floored to `volume_step`. If the result is
  below the broker minimum the order is rejected with a clear message instead of
  silently over-risking.
- Stop-loss and take-profit are attached in the same `order_send` request, so
  protection exists at the broker even if the backend goes down.
- Closing a live trade closes the MT5 position **by ticket** (magic number
  filtered). On hedging accounts this avoids leaving an offsetting duplicate
  position behind.

## 6. Troubleshooting

| Bridge message | Meaning / fix |
|---|---|
| `MT5 login failed [10004]` | Wrong account, password or server, or the terminal is logged out. |
| `MT5 is not installed` | Install `bridge/requirements.txt` with 64-bit Python on Windows. |
| `<SYMBOL> is not available` | Wrong suffix: check the exact name in MT5 Market Watch, set `MT5_SYMBOL_SUFFIX`. |
| `no live quote ... market open` | Market closed / no tick yet; retry during the session. |
| `calculated volume ... below the broker minimum` | Risk per trade or stop distance too small for the account size. |
| `MT5 rejected order [10030]` | Filling-mode mismatch; the bridge retries IOC/FOK/RETURN automatically. |
| `invalid bridge token` | `MT5_BRIDGE_TOKEN` and Railway `EXNESS_BRIDGE_TOKEN` differ. |
| `stop-loss is inside the broker's minimum stop distance` | Widen the signal stop; Exness requires a minimum distance. |

## Operational notes

- One MT5 terminal can be logged into one account at a time. The bridge
  serialises requests and logs in per call, so concurrent users queue behind a
  single lock; expect 1-3 s per order while the market is open.
- The VPS must stay online. If the bridge is down, auto-trade logs
  `broker rejected order` / `network` failures and no position is opened.
- Investor (read-only) passwords validate but cannot trade: use the trading
  password.
- The bridge is intentionally not part of the Docker/Railway image: it needs
  Windows, a GUI-less but running MT5 terminal, and broker network access.
