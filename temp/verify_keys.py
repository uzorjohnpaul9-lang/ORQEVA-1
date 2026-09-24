import httpx

ALP = "https://paper-api.alpaca.markets"
DATA = "https://data.alpaca.markets"
TWELVE = "https://api.twelvedata.com"

def env_value(name):
    with open(r"C:\Users\Munachi\ai-trading-system\.env", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line.startswith(name + "="):
                return line.split("=", 1)[1].strip().strip('"')
    return None

async def main():
    ak = env_value("ALPACA_API_KEY")
    asc = env_value("ALPACA_SECRET_KEY")
    tk = env_value("TWELVE_DATA_API_KEY")

    async with httpx.AsyncClient(timeout=30) as c:
        # 1) Alpaca account info from paper API (validates keys + paper endpoint)
        try:
            r = await c.get(ALP + "/v2/account", headers={"APCA-API-KEY-ID": ak, "APCA-API-SECRET-KEY": asc})
            if r.status_code == 200:
                acc = r.json()
                print(f"ALPACA OK: account={acc.get('account_number')} status={acc.get('status')} "
                      f"equity=${float(acc.get('equity',0)):,.2f} paper={acc.get('account_blocked') is not None and acc.get('status')!='ACTIVE'}")
                print(f"   trading_enabled={acc.get('trading_blocked')==False} currencies={acc.get('currency')}")
            else:
                print("ALPACA FAIL:", r.status_code, r.text[:200])
        except Exception as e:
            print("ALPACA ERROR:", e)

        # 2) Alpaca historical bars (data endpoint) for AAPL
        try:
            r = await c.get(DATA + "/v2/stocks/AAPL/bars", params={"timeframe": "1Day", "limit": 3},
                            headers={"APCA-API-KEY-ID": ak, "APCA-API-SECRET-KEY": asc})
            if r.status_code == 200:
                bars = r.json().get("bars", [])
                print(f"ALPACA DATA OK: {len(bars)} AAPL bars, last close={bars[-1]['c'] if bars else 'n/a'}")
            else:
                print("ALPACA DATA FAIL:", r.status_code, r.text[:200])
        except Exception as e:
            print("ALPACA DATA ERROR:", e)

        # 3) Twelve Data time_series for a crypto pair
        try:
            r = await c.get(TWELVE + "/time_series", params={"symbol": "BTC/USD", "interval": "1day", "outputsize": 3, "apikey": tk})
            if r.status_code == 200 and r.json().get("status") == "ok":
                d = r.json()
                print(f"TWELVE OK: {d['meta']['symbol']} {d['meta']['interval']}, values={len(d.get('values',[]))}, "
                      f"last close={d['values'][0]['close'] if d.get('values') else 'n/a'}")
            else:
                print("TWELVE FAIL:", r.status_code, r.text[:200])
        except Exception as e:
            print("TWELVE ERROR:", e)

        # 4) Twelve Data time_series for a forex pair
        try:
            r = await c.get(TWELVE + "/time_series", params={"symbol": "EUR/USD", "interval": "1day", "outputsize": 2, "apikey": tk})
            if r.status_code == 200 and r.json().get("status") == "ok":
                d = r.json()
                print(f"TWELVE FX OK: {d['meta']['symbol']}, last close={d['values'][0]['close'] if d.get('values') else 'n/a'}")
            else:
                print("TWELVE FX FAIL:", r.status_code, r.text[:200])
        except Exception as e:
            print("TWELVE FX ERROR:", e)

import asyncio
asyncio.run(main())