"""Replace the ORQEVA Telegram bots.

Reads new bot tokens from a text file (never prints them), validates each
against Telegram's getMe, backs up .env, writes the new tokens, then sends a
test message through the admin bot.

Usage:
    python setup_telegram.py [path-to-tokens-file]

Expected tokens file format (one bot per line, any order):
    orqeva free token: 8123456789:AAH...
    orqeva premium token: 9123456789:AAH...
    orqeva vip token: 7123456789:AAH...
    orqeva admin token: 6123456789:AAH...
"""
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

ROOT = Path(__file__).parent
ENV_FILE = ROOT / ".env"

TOKEN_RE = re.compile(r"\d{6,}:[A-Za-z0-9_-]{20,}")
TIER_KEYS = {
    "free": "TELEGRAM_BOT_TOKEN_FREE",
    "premium": "TELEGRAM_BOT_TOKEN_PREMIUM",
    "vip": "TELEGRAM_BOT_TOKEN_VIP",
    "admin": "TELEGRAM_BOT_TOKEN_ADMIN",
}
DEFAULT_TOKEN_FILES = [
    Path.home() / "Downloads" / "telegram tokens.txt",
    Path.home() / "Documents" / "telegram token.txt",
]


def classify(label: str) -> str | None:
    lowered = label.lower()
    for tier in ("premium", "vip", "free", "admin"):
        if tier in lowered:
            return tier
    return None


def read_tokens(path: Path) -> tuple[dict, list]:
    """Return ({tier: (token, label)}, [unlabeled tokens]) from a tokens file."""
    found, unlabeled = {}, []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = TOKEN_RE.search(line)
        if not match:
            continue
        token = match.group(0)
        label = line[: match.start()].strip(" \t:,-")
        tier = classify(label) if label else None
        if tier and tier not in found:
            found[tier] = (token, label)
        else:
            unlabeled.append(token)
    return found, unlabeled


def update_env(key: str, value: str) -> None:
    """Set key=value in .env, appending the key if it does not exist yet."""
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i] = f"{key}={value}"
            break
    else:
        lines.append(f"{key}={value}")
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def get_env(key: str) -> str:
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return os.getenv(key, "")


def validate(token: str) -> str | None:
    """Return the bot username if the token is live, else None."""
    try:
        resp = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=15)
        data = resp.json()
        if data.get("ok"):
            return "@" + data["result"]["username"]
    except Exception as exc:
        print(f"    [ERROR] network problem: {exc}")
    return None


def send_test(token: str, chat_id: str) -> bool:
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": "✅ <b>ORQEVA admin bot connected.</b>\nPayment and system alerts will arrive here.",
                "parse_mode": "HTML",
            },
            timeout=15,
        )
        return bool(resp.json().get("ok"))
    except Exception:
        return False


def locate_tokens_file() -> Path | None:
    if len(sys.argv) > 1:
        candidate = Path(sys.argv[1])
        return candidate if candidate.exists() else None
    for candidate in DEFAULT_TOKEN_FILES:
        if candidate.exists():
            return candidate
    return None


def main() -> int:
    print("=" * 55)
    print("ORQEVA TELEGRAM BOT REPLACEMENT")
    print("=" * 55)

    path = locate_tokens_file()
    if not path:
        print("No tokens file found. Pass one: python setup_telegram.py <file>")
        return 1
    print(f"\nTokens file: {path}")

    found, unlabeled = read_tokens(path)

    for token in unlabeled:
        known = any(token == existing for existing, _ in found.values())
        if not known:
            print("\nUnlabeled token found - assign it to a tier:")
            print("  1=free  2=premium  3=vip  4=admin  5=ignore")
            choice = input("  choice: ").strip()
            tier = {"1": "free", "2": "premium", "3": "vip", "4": "admin"}.get(choice)
            if tier and tier not in found:
                found[tier] = (token, "assigned manually")

    missing = [t for t in TIER_KEYS if t not in found]
    if missing:
        print(f"\n[WARN] no token found for: {', '.join(missing)}")
    if not found:
        print("[FAIL] no tokens found in the file.")
        return 1

    print("\nValidating tokens with Telegram getMe...")
    validated = {}
    for tier in TIER_KEYS:
        if tier not in found:
            continue
        token, label = found[tier]
        username = validate(token)
        if username:
            print(f"  [OK] {tier:<8} -> {username}")
            validated[tier] = (token, username)
        else:
            print(f"  [FAIL] {tier:<8} -> rejected by Telegram (check the token)")

    if not validated:
        print("\n[FAIL] no valid tokens - .env not modified.")
        return 1

    if ENV_FILE.exists():
        backup = ENV_FILE.with_name(f".env.backup-{datetime.now():%Y%m%d-%H%M%S}")
        shutil.copy2(ENV_FILE, backup)
        print(f"\n.env backed up to {backup.name}")

    for tier, (token, _) in validated.items():
        update_env(TIER_KEYS[tier], token)
    print(f"Saved {len(validated)} token(s) to .env (secrets not displayed).")

    admin_token = validated.get("admin", (None,))[0]
    admin_username = validated.get("admin", (None, None))[1]

    current_chat = get_env("TELEGRAM_ADMIN_CHAT_ID")
    print(f"\nAdmin chat ID: {current_chat or '(not set)'}")
    chat_id = input("New admin chat ID (Enter keeps current): ").strip()
    if chat_id:
        update_env("TELEGRAM_ADMIN_CHAT_ID", chat_id)
        current_chat = chat_id

    answer = input("Also use this chat ID as subscriber chat for all tiers? [y/N]: ").strip()
    if answer.lower() in ("y", "yes") and current_chat:
        for tier in ("FREE", "PREMIUM", "VIP"):
            update_env(f"TELEGRAM_CHAT_IDS_{tier}", current_chat)

    print("\nSending test message via admin bot...")
    if admin_token and current_chat and send_test(admin_token, current_chat):
        print("  [OK] test message delivered")
    else:
        print("  [SKIP] need a valid admin bot + admin chat ID (message not sent)")

    print("\n" + "=" * 55)
    print("STATUS")
    print("=" * 55)
    for tier in TIER_KEYS:
        if tier in validated:
            print(f"  {tier:<8} {validated[tier][1]:<24} saved")
        else:
            print(f"  {tier:<8} {'(no token)':<24} unchanged")
    print("\nNext: python test_notifications.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
