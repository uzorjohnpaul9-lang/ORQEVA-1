import sys
sys.path.insert(0, '.')
from live_engine import MarketAnalyzer

a = MarketAnalyzer()
results = []
for symbol in ["AAPL", "NVDA", "TSLA", "META", "AMD"]:
    data = a.get_stock_data(symbol)
    if not data:
        results.append(f'{symbol}: No data')
        continue
    prices = data['prices']
    rsi = a.calculate_rsi(prices)
    macd = a.calculate_macd(prices)
    bollinger = a.calculate_bollinger(prices)
    sma20 = sum(prices[-20:]) / 20
    sma5 = sum(prices[-5:]) / 5
    trend = "up" if sma5 > sma20 else "down"
    current = data['current_price']

    results.append(f'\n{symbol}: ${current:.2f} | RSI:{rsi:.1f} | MACD:{macd["histogram"]:.4f} | Trend:{trend}')
    results.append(f'  Bollinger: {bollinger["lower"]:.2f} - {bollinger["middle"]:.2f} - {bollinger["upper"]:.2f}')

    signal = a.analyze_stock(symbol)
    if signal:
        results.append(f'  SIGNAL: {signal["direction"]} ({signal["confidence"]:.1%}) - {signal["reason"]}')
    else:
        results.append(f'  No signal')

with open("debug_output.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(results))
