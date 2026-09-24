import type { Signal, Trade, Notification } from "./types";

export const demoSignals: Signal[] = [
  { id: "1", symbol: "EUR/USD", market: "forex", direction: "buy", confidence: 0.82, entry_price: 1.0845, stop_loss: 1.0790, take_profit: 1.0920, strategy: "Trend Following", status: "active", tier_required: "free", created_at: "2026-08-20T10:30:00Z" },
  { id: "2", symbol: "AAPL", market: "stock", direction: "buy", confidence: 0.75, entry_price: 198.50, stop_loss: 194.00, take_profit: 210.00, strategy: "Breakout", status: "active", tier_required: "premium", created_at: "2026-08-20T09:15:00Z" },
  { id: "3", symbol: "BTC/USDT", market: "crypto", direction: "sell", confidence: 0.68, entry_price: 67500, stop_loss: 69000, take_profit: 64000, strategy: "RSI Reversal", status: "active", tier_required: "vip", created_at: "2026-08-20T08:00:00Z" },
  { id: "4", symbol: "GBP/JPY", market: "forex", direction: "sell", confidence: 0.71, entry_price: 188.45, stop_loss: 189.20, take_profit: 187.00, strategy: "Bounce", status: "active", tier_required: "free", created_at: "2026-08-20T07:45:00Z" },
  { id: "5", symbol: "TSLA", market: "stock", direction: "buy", confidence: 0.88, entry_price: 245.00, stop_loss: 238.00, take_profit: 265.00, strategy: "Momentum", status: "active", tier_required: "premium", created_at: "2026-08-20T06:30:00Z" },
  { id: "6", symbol: "ETH/USDT", market: "crypto", direction: "buy", confidence: 0.79, entry_price: 3420, stop_loss: 3300, take_profit: 3700, strategy: "MACD Crossover", status: "active", tier_required: "vip", created_at: "2026-08-19T22:00:00Z" },
  { id: "7", symbol: "USD/NGN", market: "forex", direction: "sell", confidence: 0.65, entry_price: 1550.00, stop_loss: 1570.00, take_profit: 1520.00, strategy: "Support Break", status: "expired", tier_required: "free", created_at: "2026-08-19T14:00:00Z" },
  { id: "8", symbol: "NVDA", market: "stock", direction: "buy", confidence: 0.92, entry_price: 135.00, stop_loss: 130.00, take_profit: 150.00, strategy: "AI Momentum", status: "active", tier_required: "premium", created_at: "2026-08-20T11:00:00Z" },
];

export const demoTrades: Trade[] = [
  { id: "1", symbol: "EUR/USD", market: "forex", side: "buy", quantity: 10000, entry_price: 1.0820, exit_price: 1.0895, pnl: 69.26, status: "closed", strategy: "Trend Following", opened_at: "2026-08-18T10:00:00Z", closed_at: "2026-08-19T14:30:00Z" },
  { id: "2", symbol: "AAPL", market: "stock", side: "buy", quantity: 50, entry_price: 195.00, exit_price: 201.50, pnl: 325.00, status: "closed", strategy: "Breakout", opened_at: "2026-08-17T09:30:00Z", closed_at: "2026-08-19T15:00:00Z" },
  { id: "3", symbol: "BTC/USDT", market: "crypto", side: "sell", quantity: 0.5, entry_price: 68000, exit_price: 65500, pnl: 1250.00, status: "closed", strategy: "RSI Reversal", opened_at: "2026-08-16T20:00:00Z", closed_at: "2026-08-18T08:00:00Z" },
  { id: "4", symbol: "TSLA", market: "stock", side: "buy", quantity: 30, entry_price: 240.00, exit_price: 235.00, pnl: -150.00, status: "closed", strategy: "Momentum", opened_at: "2026-08-19T09:30:00Z", closed_at: "2026-08-20T10:00:00Z" },
  { id: "5", symbol: "GBP/JPY", market: "forex", side: "sell", quantity: 5000, entry_price: 188.90, exit_price: 188.45, pnl: 12.50, status: "closed", strategy: "Bounce", opened_at: "2026-08-20T07:00:00Z", closed_at: "2026-08-20T11:00:00Z" },
  { id: "6", symbol: "ETH/USDT", market: "crypto", side: "buy", quantity: 2, entry_price: 3350, exit_price: null, pnl: null, status: "open", strategy: "MACD Crossover", opened_at: "2026-08-20T12:00:00Z", closed_at: null },
  { id: "7", symbol: "NVDA", market: "stock", side: "buy", quantity: 40, entry_price: 132.00, exit_price: null, pnl: null, status: "open", strategy: "AI Momentum", opened_at: "2026-08-20T09:35:00Z", closed_at: null },
];

export const demoNotifications: Notification[] = [
  { id: "1", type: "signal", title: "New Buy Signal", message: "EUR/USD buy signal generated with 82% confidence", is_read: false, created_at: "2026-08-20T10:30:00Z" },
  { id: "2", type: "tp", title: "Take Profit Hit", message: "BTC/USDT short position hit TP at $65,500. +$1,250 profit", is_read: false, created_at: "2026-08-20T08:15:00Z" },
  { id: "3", type: "risk", title: "Risk Alert", message: "Daily loss approaching 60% of limit. Current: $600 / $1,000", is_read: true, created_at: "2026-08-19T16:00:00Z" },
  { id: "4", type: "system", title: "Engine restarted", message: "Trading engine restarted successfully", is_read: true, created_at: "2026-08-19T06:00:00Z" },
  { id: "5", type: "sl", title: "Stop Loss Triggered", message: "TSLA long position closed at SL $235. -$150 loss", is_read: false, created_at: "2026-08-20T10:05:00Z" },
];

export const demoPortfolioValue = 102450.75;
export const demoDailyPnl = 1250.50;
export const demoWinRate = 72.5;
