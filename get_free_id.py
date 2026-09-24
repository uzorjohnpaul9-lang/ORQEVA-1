import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

tier = sys.argv[1].lower() if len(sys.argv) > 1 else "free"
env_key = f"TELEGRAM_BOT_TOKEN_{tier.upper()}"
token = os.getenv(env_key, "")

if not token:
    print(f"Error: {env_key} not set in .env")
    sys.exit(1)

url = f"https://api.telegram.org/bot{token}/getUpdates"
r = requests.get(url + "?offset=-1", timeout=15)
print("Cleared:", r.status_code)

r = requests.get(url, timeout=15)
data = r.json()
updates = data.get("result", [])
print(f"Found {len(updates)} updates")

for u in updates:
    for key in ["channel_post", "message", "my_chat_member"]:
        if key in u:
            chat = u[key].get("chat", {})
            print(f"  Chat ID: {chat.get('id')}, Title: {chat.get('title')}, Type: {chat.get('type')}")

if not updates:
    print(f"No updates. Send a test message in your {tier.title()} channel first.")
