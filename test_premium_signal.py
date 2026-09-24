import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from notifications.channel_notifier import ChannelNotifier
from dotenv import load_dotenv
load_dotenv()

notifier = ChannelNotifier()

signal = {
    "direction": "BUY",
    "symbol": "TSLA",
    "price": 250.75,
    "confidence": 0.89,
    "reason": "EV sector momentum + delivery beat"
}

print("Sending test signal to Premium channel...")
notifier.send_signal(signal, target_tiers=["premium"])
print("Done! Check your Premium Telegram channel.")
