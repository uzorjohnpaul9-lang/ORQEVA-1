import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, '.')
from forex.forex_analyzer import ForexAnalyzer
from dotenv import load_dotenv
load_dotenv()

fa = ForexAnalyzer()

results = []
results.append("Testing forex data...")

# Test one pair
data = fa.get_forex_data("EUR/USD")
if data:
    results.append(f"EUR/USD data: {len(data['prices'])} bars")
    results.append(f"Current: {data['current_price']}")
    
    # Analyze
    signal = fa.analyze_pair("EUR/USD")
    if signal:
        results.append(f"Signal: {signal['direction']} @ {signal['price']} ({signal['confidence']:.1%})")
    else:
        results.append("No signal for EUR/USD")
else:
    results.append("No data returned")
    results.append(f"API Key: {fa.api_key[:10]}...")

with open("forex_test.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(results))
