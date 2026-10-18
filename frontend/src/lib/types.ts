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
  market: "stock" | "forex" | "crypto" | "commodity";
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
  /** meme | hot | major | alt for crypto; else the market name. */
  category?: string | null;
  /** Resolved outcome once the signal closes: tp | sl | expired | breakeven. */
  outcome?: string | null;
  exit_price?: number | null;
  resolved_at?: string | null;
  r_multiple?: number | null;
  /** Provenance of the data behind the signal. */
  data_source?: "live" | "simulated" | null;
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

export interface MarketAccuracy {
  market: string;
  closed_trades: number;
  wins: number;
  losses: number;
  win_rate: number;
  total_pnl: number;
}

export interface SignalCounts {
  total_signals: number;
  active_signals: number;
  by_market: Record<string, number>;
}

export interface OutcomeBucket {
  market: string;
  resolved: number;
  wins: number;
  win_rate: number;
}

export interface OutcomeStats {
  resolved: number;
  wins: number;
  losses: number;
  win_rate: number;
  avg_r: number;
  by_outcome: Record<string, number>;
  by_market: OutcomeBucket[];
  live: number;
  simulated: number;
  unknown: number;
}

export interface AccuracyStats {
  overall: { closed_trades: number; win_rate: number; total_pnl: number };
  signals: SignalCounts;
  outcomes?: OutcomeStats;
  strategies: StrategyAccuracy[];
  markets: MarketAccuracy[];
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
  /** True for virtual/demo (paper) trades; false for live broker trades. */
  is_demo?: boolean | null;
  opened_at: string;
  closed_at: string | null;
}

export interface DemoAccount {
  starting_balance: number;
  realized_pnl: number;
  portfolio_value: number;
  open_positions: number;
  closed_trades: number;
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

export interface AutoTradeSettings {
  enabled: boolean;
  route: "paper" | "live";
  markets: string[];
  per_trade_risk_pct: number;
  min_confidence: number;
  updated_at?: string | null;
}

export interface AutoTradeLogEntry {
  id: string;
  symbol: string;
  market: string;
  direction: "buy" | "sell";
  confidence: number | null;
  quantity: number | null;
  entry_price: number | null;
  route: "paper" | "live";
  status: "placed" | "skipped" | "rejected" | "error";
  reason: string | null;
  trade_id: string | null;
  created_at: string;
}

export interface CalendarEvent {
  name: string;
  title: string;
  impact: "high" | "medium" | "low";
  category: string;
  all_day: boolean;
  date: string | null;
  time_utc: string | null;
  time_et: string | null;
  consensus: string | null;
  prior: string | null;
  actual: string | null;
  url: string | null;
  affected_markets: string[];
  minutes_away?: number;
}

export interface CalendarAttribution {
  source: string;
  url: string;
}

export interface CalendarFeed {
  events: CalendarEvent[];
  attribution: CalendarAttribution;
}

export interface CalendarActiveFeed extends CalendarFeed {
  affected_markets: string[];
}

export interface CalendarEventContext {
  window_minutes: number;
  events: CalendarEvent[];
  affected_markets: string[];
  attribution: CalendarAttribution;
}

export interface SupportTicket {
  id: string;
  subject: string;
  message: string;
  category: string;
  status: string;
  reply?: string | null;
  replied_at?: string | null;
  created_at: string;
  updated_at?: string;
  user_id?: string | null;
  email?: string;
  user_email?: string;
  priority?: string;
  source?: string;
  assigned_to?: string | null;
  replied_by?: string | null;
}

export interface AdminUserContext {
  profile: {
    id: string;
    email: string;
    username: string;
    tier: string;
    is_admin: boolean;
    is_active: boolean;
    telegram_chat_id: string | null;
    created_at: string;
  };
  preferences: Record<string, unknown> | null;
  risk: Record<string, unknown> | null;
  activity: {
    open_positions: number;
    closed_positions: number;
    realized_pnl: number;
    recent_trades: Array<Record<string, unknown>>;
  };
  exchanges: Array<Record<string, unknown>>;
  subscriptions: Array<Record<string, unknown>>;
  support_tickets: Array<Record<string, unknown>>;
  notifications_unread: number;
}
