import sys
sys.path.insert(0, '.')
from live_engine import TelegramNotifier
from dotenv import load_dotenv
load_dotenv()

notifier = TelegramNotifier()

results = []
results.append("Testing Free tier 3-signal limit...")

# Send 5 DIFFERENT signals to free
symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"]
for i, symbol in enumerate(symbols):
    signal = {
        "symbol": symbol,
        "direction": "BUY",
        "price": 100.00 + i,
        "confidence": 0.80,
        "reason": f"Test {i}",
        "target_price": 105.00,
        "stop_loss": 98.00,
    }
    can_send = notifier.can_send_signal("free")
    results.append(f"\nSignal {i+1} ({symbol}): Can send = {can_send}")
    if can_send:
        notifier.send_signal(signal, "free")
        results.append(f"  Sent! Count: {notifier.daily_signal_count['free']}/3")
    else:
        results.append(f"  BLOCKED - Limit reached!")

with open("limit_test.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(results))
