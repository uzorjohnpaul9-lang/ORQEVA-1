-- Auto-Trade: per-user settings + execution ledger (matches backend auto_trade_service.py).
-- Applies idempotently; safe to re-run. Backend writes via the service key (bypasses RLS).

-- auto_trade_settings --------------------------------------------------------
create table if not exists public.auto_trade_settings (
  id                 text primary key,
  user_id            text not null references public.users (id) on delete cascade,
  enabled            boolean not null default false,
  route              text not null default 'paper' check (route in ('paper','live')),
  markets            jsonb not null default '["forex","crypto","stock"]'::jsonb,
  per_trade_risk_pct numeric(6,2) not null default 1.0,
  min_confidence     numeric(6,4) not null default 0.0,
  created_at         timestamptz not null default timezone('utc', now()),
  updated_at         timestamptz not null default timezone('utc', now())
);
alter table public.auto_trade_settings enable row level security;
create unique index if not exists auto_trade_user_uq on public.auto_trade_settings (user_id);
create index if not exists auto_trade_enabled_idx on public.auto_trade_settings (enabled);

-- auto_trade_log -------------------------------------------------------------
create table if not exists public.auto_trade_log (
  id            text primary key,
  user_id       text not null references public.users (id) on delete cascade,
  signal_id     text references public.signals (id) on delete set null,
  symbol        text not null,
  market        text not null check (market in ('stock','forex','crypto','commodity')),
  direction     text not null check (direction in ('buy','sell')),
  confidence    numeric(6,4),
  quantity      numeric(18,8),
  entry_price   numeric(18,8),
  route         text not null default 'paper' check (route in ('paper','live')),
  status        text not null check (status in ('placed','skipped','rejected','error')),
  reason        text,
  trade_id      text references public.trades (id) on delete set null,
  created_at    timestamptz not null default timezone('utc', now())
);
alter table public.auto_trade_log enable row level security;
create unique index if not exists auto_log_user_signal_uq on public.auto_trade_log (user_id, signal_id);
create index if not exists auto_log_user_created_idx on public.auto_trade_log (user_id, created_at desc);