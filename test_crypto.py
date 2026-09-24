import sys
sys.path.insert(0, '.')
from crypto.crypto_analyzer import CryptoAnalyzer

ca = CryptoAnalyzer()

results = []
# Test just BTC
results.append("Testing BTC/USD...")
signal = ca.analyze_pair("BTC/USD")
if signal:
    results.append(f"  {signal['direction']} @ ${signal['price']:,.2f} ({signal['confidence']:.1%})")
else:
    results.append("  No signal")

with open("crypto_test.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(results))
