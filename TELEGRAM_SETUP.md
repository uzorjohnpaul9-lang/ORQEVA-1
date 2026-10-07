# Telegram Bot Setup Guide (4 bots)

ORQEVA uses **one bot per tier** plus a **dedicated admin bot**:

| Purpose | Env var | Where it posts |
|---------|---------|----------------|
| Free tier signals | `TELEGRAM_BOT_TOKEN_FREE` | Free channel (`TELEGRAM_CHANNEL_FREE`) |
| Premium tier signals | `TELEGRAM_BOT_TOKEN_PREMIUM` | Premium channel (`TELEGRAM_CHANNEL_PREMIUM`) |
| VIP tier signals | `TELEGRAM_BOT_TOKEN_VIP` | VIP channel (`TELEGRAM_CHANNEL_VIP`) |
| Admin / payment alerts | `TELEGRAM_BOT_TOKEN_ADMIN` | Your DM (`TELEGRAM_ADMIN_CHAT_ID`) |

## Step 1: Create the bots with @BotFather

Open Telegram, search **@BotFather**, and for each bot send `/newbot`:

```
Free:     ORQEVA Free      -> e.g. orqeva_free_signals_bot
Premium:  ORQEVA Premium   -> e.g. orqeva_premium_signals_bot
VIP:      ORQEVA VIP       -> e.g. orqeva_vip_signals_bot
Admin:    ORQEVA Admin     -> e.g. orqeva_admin_bot
```

Save each token in a text file, one per line (labels optional):

```
orqeva free token: 8123456789:AAH...
orqeva premium token: 9123456789:AAH...
orqeva vip token: 7123456789:AAH...
orqeva admin token: 6123456789:AAH...
```

Then send `/start` to each of the 4 bots (required before they can message you).

## Step 2: Revoke and delete the old bots

In @BotFather:

1. Send `/mybots`
2. Select each **old** bot → **API Token** → **Revoke current token**
3. Same menu → **Delete this bot** (once revoked, its old `.env` token is dead anyway)

## Step 3: Get your admin chat ID

1. Search **@userinfobot** → send `/start`
2. Copy the numeric ID it replies with

(The number before `:` in a bot token is the **bot's own ID**, not your chat ID.)

## Step 4: Run the replacement script

```bash
python setup_telegram.py            # auto-finds Downloads\telegram tokens.txt
# or
python setup_telegram.py "C:\path\to\tokens.txt"
```

The script:

- validates each token against Telegram `getMe` and shows the bot username
- backs up `.env` to `.env.backup-<timestamp>` before changing anything
- writes the 4 tokens (secrets are never printed)
- prompts for your admin chat ID (and optionally sets `TELEGRAM_CHAT_IDS_*`)
- sends a test message through the new **admin bot**

**Warning:** at the chat-ID prompt, **type the numeric ID** (from Step 3) and
then press the Enter key — do **not** type the word "Enter" itself, it gets
saved literally as the chat ID and breaks admin alerts. Pressing Enter on an
empty line keeps the current value.

## Step 5: Add tier bots to their channels

For each tier bot, open its channel → **Add Admin** → select the bot → grant
**Post Messages**. If your channel IDs change, update `TELEGRAM_CHANNEL_*` in
`.env` (fetch them with `python get_channel_id.py`).

## Step 6: Test

```bash
python test_notifications.py
```

## Notes

- The admin bot only needs your DM — do **not** put it in a channel.
- Privacy setting (`/setprivacy`) only affects groups; DMs always work. If you
  ever add a bot to a group and it ignores commands, set privacy to **Disable**.
- `TELEGRAM_BOT_TOKEN_ADMIN` falls back to `TELEGRAM_BOT_TOKEN_FREE` when
  empty, so older setups keep working.
