// Shared frontend types
export type UserRole = 'user' | 'premium' | 'vip' | 'admin';

export type Market = 'stock' | 'forex' | 'crypto' | 'commodity';

export interface User {
  id: string;
  email: string;
  tier: UserRole;
  is_active: boolean;
  email_verified: boolean;
}

export interface Signal {
  id: string;
  symbol: string;
  market: Market;
  direction: 'BUY' | 'SELL';
  confidence: number;
  entry_price: number;
  stop_loss: number;
  take_profit: number;
  strategy?: string;
  tier?: UserRole;
  created_at: string;
  indicators?: Record<string, any>;
}

export interface Trade {
  id: string;
  symbol: string;
  market: Market;
  direction: 'BUY' | 'SELL';
  quantity: number;
  entry_price: number;
  exit_price?: number;
  status: 'open' | 'closed' | 'cancelled';
  pnl?: number;
  pnl_percent?: number;
  created_at: string;
  closed_at?: string;
}