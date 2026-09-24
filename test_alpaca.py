"""
Alpaca Connection Test
Verify API keys work and show account info.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from data.market_data import MarketDataManager

print("=" * 60)
print("ALPACA CONNECTION TEST")
print("=" * 60)

md = MarketDataManager()

print(f"\nConnection Status: {'CONNECTED' if md.connected else 'NOT CONNECTED'}")

if md.connected:
    print("\n--- Account Info ---")
    account = md.get_account_info()
    print(f"  Status:   {account['status']}")
    print(f"  Equity:   ${account['equity']:,.2f}")
    print(f"  Cash:     ${account['cash']:,.2f}")
    print(f"  Buying Power: ${account['buying_power']:,.2f}")

    print("\n--- Current Positions ---")
    positions = md.get_positions()
    if positions:
        for p in positions:
            print(f"  {p['symbol']}: {p['qty']} shares @ ${p['avg_entry_price']:.2f} | P&L: ${p['unrealized_pl']:.2f}")
    else:
        print("  No open positions")

    print("\n--- Real-Time Quotes ---")
    for symbol in ["AAPL", "MSFT", "GOOGL"]:
        quote = md.get_realtime_quote(symbol)
        print(f"  {symbol}: Bid ${quote['bid']:.2f} | Ask ${quote['ask']:.2f} | Last ${quote['last']:.2f}")

    print("\n--- Historical Data (AAPL, 1h, last 5 bars) ---")
    df = md.get_stock_data("AAPL", "1h")
    if not df.empty:
        print(df[['timestamp', 'open', 'high', 'low', 'close', 'volume']].tail(5).to_string(index=False))

else:
    print("\nCould not connect. Check your API keys in .env file.")

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)
