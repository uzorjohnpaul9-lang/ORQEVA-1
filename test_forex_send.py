import sys
sys.path.insert(0, '.')
from forex.forex_analyzer import ForexAnalyzer
from live_engine import TelegramNotifier
from dotenv import load_dotenv
load_dotenv()

notifier = TelegramNotifier()
fa = ForexAnalyzer()

signals = fa.analyze_all()

results = []
results.append(f"Found {len(signals)} forex signals")

for s in signals:
    results.append(f"Sending {s['direction']} {s['symbol']} to Premium...")
    ok1 = notifier.send_signal(s, "premium")
    results.append(f"  Result: {ok1}")
    results.append(f"Sending {s['direction']} {s['symbol']} to VIP...")
    ok2 = notifier.send_signal(s, "vip")
    results.append(f"  Result: {ok2}")

with open("forex_send_test.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(results))
