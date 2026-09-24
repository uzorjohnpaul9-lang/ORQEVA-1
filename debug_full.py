import sys
sys.path.insert(0, '.')
from engines.indicators import calculate_rsi, calculate_macd, calculate_bollinger, score_signal
from engines.forex_engine import ForexEngine
from engines.crypto_engine import CryptoEngine

results = []
fe = ForexEngine()
ce = CryptoEngine()

for pair in fe.get_symbols():
    prices = fe.fetch_prices(pair, 30)
    if not prices or len(prices) < 26:
        results.append(f"{pair}: insufficient data ({len(prices) if prices else 0})")
        continue
    config = fe.indicator_config
    rsi = calculate_rsi(prices, config.rsi_period)
    macd = calculate_macd(prices, config.macd_fast, config.macd_slow, config.macd_signal)
    bb = calculate_bollinger(prices, config.bollinger_period, config.bollinger_std)
    result = score_signal(rsi, macd, bb, prices, prices[-1], config)
    results.append(f"FX {pair}: RSI={rsi:.1f} MACD_h={macd['histogram']:.6f} BB_mid={bb['middle']:.4f} dir={result['direction']} score={result['confidence']:.2f} reasons={result['reasons']}")

for pair in ce.get_symbols():
    prices = ce.fetch_prices(pair, 30)
    if not prices or len(prices) < 26:
        results.append(f"{pair}: insufficient data ({len(prices) if prices else 0})")
        continue
    config = ce.indicator_config
    rsi = calculate_rsi(prices, config.rsi_period)
    macd = calculate_macd(prices, config.macd_fast, config.macd_slow, config.macd_signal)
    bb = calculate_bollinger(prices, config.bollinger_period, config.bollinger_std)
    result = score_signal(rsi, macd, bb, prices, prices[-1], config)
    results.append(f"CR {pair}: RSI={rsi:.1f} MACD_h={macd['histogram']:.2f} BB_mid={bb['middle']:.2f} dir={result['direction']} score={result['confidence']:.2f} reasons={result['reasons']}")

with open("full_debug.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(results))
print("Done", file=sys.stderr)
