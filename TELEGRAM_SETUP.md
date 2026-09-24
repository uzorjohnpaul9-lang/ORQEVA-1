# Telegram Bot Setup Guide

## Step 1: Create 3 Bots with @BotFather

Open Telegram and search for **@BotFather**. For each bot, send `/newbot`:

### Bot 1: Free Tier
```
Name: AI Trading Signals (Free)
Username: YourFreeTradingBot
```
Copy the token → put in `.env` as `TELEGRAM_BOT_TOKEN_FREE`

### Bot 2: Premium Tier
```
Name: AI Trading Signals (Premium)
Username: YourPremiumTradingBot
```
Copy the token → put in `.env` as `TELEGRAM_BOT_TOKEN_PREMIUM`

### Bot 3: VIP Tier
```
Name: AI Trading Signals (VIP)
Username: YourVIPTradingBot
```
Copy the token → put in `.env` as `TELEGRAM_BOT_TOKEN_VIP`

## Step 2: Get Your Chat ID

1. Search for **@userinfobot** on Telegram
2. Send `/start`
3. It returns your **Chat ID** (a number like `123456789`)
4. Put it in `.env` as `TELEGRAM_CHAT_IDS_FREE` (and others)

For multiple subscribers, separate with commas:
```
TELEGRAM_CHAT_IDS_FREE=123456789,987654321,555555555
```

## Step 3: Test Each Bot

1. Search for each bot on Telegram
2. Send `/start`
3. Run: `python test_alpaca.py`

## How It Works

| Tier | Bot | Signals/Day | Price |
|------|-----|-------------|-------|
| Free | @YourFreeBot | 3 | $0 |
| Premium | @YourPremiumBot | 15 | $49/mo |
| VIP | @YourVIPBot | Unlimited | $199/mo |

## Signal Flow

```
Trading System → Analyzes Market → Generates Signal
                                      ↓
                    ┌─────────────────┼─────────────────┐
                    ↓                 ↓                 ↓
              Free Bot          Premium Bot        VIP Bot
            (3 signals)       (15 signals)      (unlimited)
                    ↓                 ↓                 ↓
              Free Users       Premium Users      VIP Users
```
