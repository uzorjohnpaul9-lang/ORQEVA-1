export interface User {
  id: string;
  email: string;
  username: string;
  tier: string;
  is_active: boolean;
  is_admin: boolean;
  created_at: string;
}

export interface Signal {
  id: string;
  symbol: string;
  market: "stock" | "forex" | "crypto";
  direction: "buy" | "sell";
  confidence: number;
  effective_confidence?: number | null;
  age_hours?: number | null;
  entry_price: number | null;
  stop_loss: number | null;
  take_profit: number | null;
  strategy: string | null;
  status: string;
  tier_required: string;
  indicators?: Record<string, unknown> | null;
  created_at: string;
}

export interface StrategyAccuracy {
  strategy: string;
  markets: string[];
  closed_trades: number;
  wins: number;
  losses: number;
  win_rate: number;
  total_pnl: number;
}

export interface AccuracyStats {
  overall: { closed_trades: number; win_rate: number };
  strategies: StrategyAccuracy[];
}

export interface Trade {
  id: string;
  symbol: string;
  market: string;
  side: "buy" | "sell";
  quantity: number;
  entry_price: number;
  exit_price: number | null;
  pnl: number | null;
  status: "open" | "closed";
  strategy: string | null;
  opened_at: string;
  closed_at: string | null;
}

export interface Position extends Trade {
  current_price: number | null;
  unrealized_pnl: number | null;
}

export interface Holding {
  symbol: string;
  market: string;
  quantity: number;
  avg_entry_price: number;
  trade_count: number;
  strategy: string | null;
  current_price: number | null;
  market_value: number | null;
  unrealized_pnl: number | null;
}

export interface EquityPoint {
  label: string;
  value: number;
}

export interface AllocationSlice {
  market: string;
  value: number;
}

export interface PortfolioPerformance {
  starting_value: number;
  portfolio_value: number;
  total_pnl: number;
  win_rate: number;
  wins: number;
  losses: number;
  max_drawdown: number;
  equity_curve: EquityPoint[];
  allocation: AllocationSlice[];
}

export interface Notification {
  id: string;
  type: string;
  title: string;
  message: string;
  is_read: boolean;
  created_at: string;
}

export interface DashboardOverview {
  total_signals: number;
  active_signals: number;
  open_trades: number;
  total_pnl: number;
  win_rate: number;
  portfolio_value: number;
}

export interface MarketQuote {
  symbol: string;
  price: number | null;
  change: number | null;
  change_percent: number | null;
  is_market_open?: boolean | null;
  error?: string;
}

export interface IndexCard extends MarketQuote {
  label: string;
  market: string;
}

export interface Mover extends MarketQuote {
  day_high?: number | null;
  day_low?: number | null;
}

export interface MarketOverview {
  indices: IndexCard[];
  movers: { gainers: Mover[]; losers: Mover[] };
}

export interface DiscoveryCoin {
  symbol: string;
  price: number;
  rsi: number;
  score: number;
  momentum_5d: number;
  direction: string;
}
