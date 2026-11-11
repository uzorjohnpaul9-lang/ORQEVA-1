# Broker Spike Scorecard

Use this scorecard for the standalone demo bake-off between **cTrader via Pepperstone** and **Capital.com**. Do not connect either demo account to the trading dashboard during the bake-off.

## Rules

- Demo accounts only.
- Do not commit credentials or paste them into chat.
- Do not change the live Exness connection, auto-trade settings, or open live trades.
- Run the scripts from the repository root.
- Run order checks while forex is open; weekend market orders may be rejected or delayed.
- Keep only one active forex connection for auto-trade after the winner is chosen.

## Setup

Use a dedicated virtual environment for the spikes. Do **not** install the cTrader SDK into the main app environment: it pins an older `pyOpenSSL`/`cryptography` stack and will break `ccxt`.

```powershell
python -m venv scripts\broker_spikes\.venv
& scripts\broker_spikes\.venv\Scripts\python.exe -m pip install -r scripts\broker_spikes\requirements.txt
```

Use that venv Python for all spike commands below:

```powershell
$spikePy = "scripts\broker_spikes\.venv\Scripts\python.exe"
```

### Pepperstone cTrader

1. Open a Pepperstone cTrader demo account.
2. Register an app at `openapi.ctrader.com`.
3. Use redirect URI `http://localhost:8080/callback`.
4. Set:

```powershell
$env:CTRADER_ENV="demo"
$env:CTRADER_CLIENT_ID="..."
$env:CTRADER_CLIENT_SECRET="..."
$env:CTRADER_ACCOUNT_ID="..."
```

5. Generate an auth URL:

```powershell
& $spikePy scripts\broker_spike_ctrader.py --auth-url
```

6. After approving the app, exchange the returned code:

```powershell
& $spikePy scripts\broker_spike_ctrader.py --auth-code "<code>"
```

Tokens are written to `temp/ctrader_tokens.json`. The script reads them automatically. You can also set `CTRADER_ACCESS_TOKEN` and `CTRADER_REFRESH_TOKEN` directly.

### Capital.com

1. Open a Capital.com demo account.
2. Generate an API key under **Settings -> API integrations**.
3. Set:

```powershell
$env:CAPITAL_ENV="demo"
$env:CAPITAL_API_KEY="..."
$env:CAPITAL_IDENTIFIER="you@example.com"
$env:CAPITAL_PASSWORD="..."  # the custom password you set for the API key
$env:CAPITAL_ACCOUNT_ID="..."  # optional
```

`CAPITAL_PASSWORD` is the API key's custom password from the key-generation screen, not your normal Capital.com login password.

## Mock tests

Run these before using real demo credentials. They do not contact either broker.

```powershell
& $spikePy scripts\broker_spikes\test_spikes.py -v
```

## Run order

Read-only checks first:

```powershell
& $spikePy scripts\broker_spike_ctrader.py
& $spikePy scripts\broker_spike_capital.py
```

Then demo orders, one at a time:

```powershell
& $spikePy scripts\broker_spike_ctrader.py --execute --round-trips 5 --limit-order
& $spikePy scripts\broker_spike_capital.py --execute --round-trips 5
```

Reports:

- `temp/broker_spike_ctrader.json`
- `temp/broker_spike_capital.json`

The scripts redact credentials. They do record account IDs, symbol IDs, order IDs, deal IDs, and prices.

## Results

Fill in after both spikes complete.

| Criterion | Weight | cTrader / Pepperstone | Capital.com | Notes |
|---|---:|---|---|---|
| Demo API access without live funding | Gate | | | |
| Login/auth reliability | High | | | |
| Account equity readable | High | | | |
| Symbol coverage for EURUSD/GBPUSD/USDCHF/NZDUSD/USDCAD/XAUUSD | High | | | |
| Min/max/step volume captured | High | | | |
| Sizing correctness | High | | | |
| Market order accepted and filled | High | | | |
| SL/TP accepted and visible | High | | | |
| Close by broker position/deal ID | High | | | |
| No orphan/naked position after close | Gate | | | |
| Token/session refresh | High | | | |
| Reconnect/restart behavior | Medium | | | |
| Spread/commission/swap | Medium | | | |
| Broker entity and client-fund protection | High | | | |
| Integration effort | Medium | | | |

## Evidence to record

For each broker:

- Auth success and account environment.
- Account balance/equity.
- Symbol IDs and exact broker symbol names.
- Min volume, step volume, max volume, lot size.
- Exact order payload used.
- Fill price and position/deal ID.
- SL/TP values before and after any repair.
- Close response and confirmation that the position is gone.
- Any rejection codes and raw error messages.
- Session/token expiry behavior.

## Decision rules

Choose cTrader if:

- Demo API access works through Pepperstone.
- Orders fill and close by `positionId`.
- SL/TP amendment works.
- Volume conversion is understood.
- Reconnect and token refresh are acceptable.

Choose Capital.com if:

- cTrader demo API is blocked or too fragile.
- Capital.com create -> confirm works reliably.
- SL/TP are visible (or a repair step works).
- Close by `dealId` is clean.
- Session re-login is reliable.

Do not implement both production adapters. Only the winner gets an adapter.

## Important technical notes

### cTrader volume

cTrader protocol volume is in **0.01 units**:

```text
volume = base_units * 100
1 standard lot = 100,000 base units = 10,000,000 protocol volume
0.01 lot = 1,000 base units = 100,000 protocol volume
```

Use the symbol's `lotSize`, `minVolume`, and `stepVolume` from `ProtoOASymbol`. Do not confuse this with the old OANDA `*100` bug.

### cTrader market orders

Market orders do not accept SL/TP directly. The spike:

1. Places the market order.
2. Gets the `positionId` from reconcile/execution.
3. Sends `ProtoOAAmendPositionSLTPReq`.
4. Closes with `ProtoOAClosePositionReq`.

### Capital.com two-phase flow

Capital.com does not have a separate preview endpoint. The flow is:

1. `POST /api/v1/positions` returns `dealReference`.
2. `GET /api/v1/confirms/{dealReference}` returns the final status and `dealId`.
3. `GET /api/v1/positions/{dealId}` checks SL/TP.
4. `DELETE /api/v1/positions/{dealId}` closes.
5. The spike confirms the close and re-checks the position.

Capital.com demo may accept `stopLevel`/`profitLevel` but silently ignore them. The spike checks visibility and optionally repairs via `PUT /api/v1/positions/{dealId}`.

## Sign-off

| | cTrader | Capital.com |
|---|---|---|
| Spike completed by | | |
| Date | | |
| Read-only pass | | |
| Order pass | | |
| SL/TP pass | | |
| Close pass | | |
| Recommendation | | |
