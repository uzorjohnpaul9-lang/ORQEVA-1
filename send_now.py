import sys
sys.path.insert(0, '.')
from live_engine import TelegramNotifier
from dotenv import load_dotenv
load_dotenv()

notifier = TelegramNotifier()

# Stock signal
stock = {
    "symbol": "TSLA", "direction": "SELL", "price": 351.12,
    "confidence": 0.65, "reason": "RSI overbought",
    "target_price": 337.26, "stop_loss": 358.93, "type": "stock"
}

# Forex signal
forex = {
    "symbol": "EUR/USD", "direction": "SELL", "price": 1.1683,
    "confidence": 0.65, "reason": "RSI overbought",
    "target_price": 1.1633, "stop_loss": 1.1708, "type": "forex"
}

# Crypto signal
crypto = {
    "symbol": "BTC/USD", "direction": "SELL", "price": 71821.55,
    "confidence": 0.65, "reason": "RSI overbought",
    "target_price": 68230.47, "stop_loss": 73976.20, "type": "crypto"
}

print("Sending to Free...")
notifier.send_signal(stock, "free")

print("Sending to Premium...")
notifier.send_signal(stock, "premium")
notifier.send_signal(forex, "premium")

print("Sending to VIP...")
notifier.send_signal(stock, "vip")
notifier.send_signal(forex, "vip")
notifier.send_signal(crypto, "vip")

print("Done! Check your channels.")
