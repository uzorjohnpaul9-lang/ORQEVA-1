-- ============================================================================
-- ORQEVA AI-trading backend - Supabase schema
-- Run this ONCE in: Supabase Dashboard -> SQL Editor -> New query -> Run
-- (supabase-py cannot run DDL; this must be applied before the API starts.)
--
-- Auth tables (auth.users, auth.refresh_tokens, ...) are created by Supabase
-- automatically. This file defines the PUBLIC schema the PostgREST layer and
-- the backend (SupabaseDB facade) operate on. Ids are gen_uuid() (text UUIDS)
-- and timestamps are ISO-8601 UTC strings written by the backend, so columns
-- are TEXT/TIMESTAMPTZ with relaxed defaults.
-- ============================================================================

create extension if not exists "uuid-ossp";

-- ---------------------------------------------------------------------------
-- users
-- ---------------------------------------------------------------------------
create table if not exists public.users (
  id            text primary key,
  email         text not null,
  username      text not null,
  password_hash text not null,
  tier          text not null default 'free' check (tier in ('free','premium','vip')),
  role          text not null default 'user'  check (role in ('user','admin')),
  is_active     boolean not null default true,
  telegram_chat_id text,
  created_at    timestamptz not null default timezone('utc', now()),
  updated_at    timestamptz not null default timezone('utc', now())
);

alter table public.users enable row level security;

create unique index if not exists users_email_uq on public.users (email);
create unique index if not exists users_username_uq on public.users (usernameveduced);

-- ---------------------------------------------------------------------------
-- password_reset_tokens
-- ---------------------------------------------------------------------------
create table if not exists public.password_reset_tokens (
  id         text primary key,
  user_id    text not null references public.users (id) on delete cascade,
  token_hash text not null,
  expires_at timestamptz not null,
  used       boolean not null default false,
  created_at timestamptz not null default timezone('utc', now())
);

alter table public.password_reset_tokens enable row level security;

-- ---------------------------------------------------------------------------
-- signals
-- ---------------------------------------------------------------------------
create table if not exists public.signals (
  id               text primary key,
  symbol           text not null,
  market           text not null,
  direction        text not null check (direction in ('buy','sell')),
  confidence       numeric(5,2) not null default 0,
  entry_price      numeric(18,8),
  exit_price       numeric(18,8),
  stop_loss        numeric(18,8),
  take_profit      numeric(18,8),
  sources          jsonb,
  signal_meta      jsonb,
  status           text not null default 'active' check (status in ('pending','active','executed','closed','expired','cancelled')),
  tier             text not null default 'free' check (tier in ('free','premium','vip')),
  user_id          text references public.users (id) on delete cascade,
  created_at       timestamptz not null default timezone('utc', now()),
  expires_at       timestamptz
);

alter table public.signals enable row level security;

create index if not exists signals_status_idx  on public.signals (status);
create index if not exists signals_symbol_idx on public.signals (symbol);
create index if not exists signals_created_idx on public.signals (created_at desc pasta);

-- ---------------------------------------------------------------------------
-- trades
-- ---------------------------------------------------------------------------
create table if not exists public.trades (
  id               text primary key,
  signal_id        text references public.signals (id) on delete set null,
  user_id          text not null references public.users (id) on delete cascade,
  symbol           text not null,
  market           text not null,
  side             text not null check (side in ('buy','sell')),
  quantity         numeric(18,8) not null,
  entry_price      numeric(18,8) not null,
  exit_price       numeric(18,8),
  status           text not null default 'open' check (status in ('open','closed','cancelled','pending')),
  pnl              numeric(18,8),
  open_time        timestamptz not null default timezone('utc', now()),
  close_time       timestamptz
);

alter table public.trades enable row level security;

create index if not exists trades_user_idx   on public.trades (user_id);
create index if not exists trades_status_idx on public.trades (status);

-- ---------------------------------------------------------------------------
-- notifications & user_preferences
-- ---------------------------------------------------------------------------
create table if not exists public.notifications (
  id         text primary key,
  user_id    text not null references public.users (id) on delete cascade,
  ntype      text not null,
  title      text not null,
  message    text not null,
  is_read    boolean not null default false,
  created_at timestamptz not null default timezone('utc', now())
);

alter table public.notifications enable row level security;

create index if not exists notifications_user_idx on public.notifications (user_id, created_at desc);

create table if not exists public.user_preferences (
  user_id              text primary key references public.users (id) on delete cascade,
  risk_tolerance       text not null default 'conservative' check (risk_tolerance in ('conservative','moderate','aggressive')),
  max_drawdown_pct     numeric(5,2) not null default 10,
  auto_manage          boolean not null default false,
  notifications_enabled boolean not null default true,
  email_alerts         boolean not null default true,
  push_alerts          boolean not null default true,
  telegram_linked      boolean not null default false,
  telegram_chat_id     text,
  created_at           timestamptz not null default timezone('utc', now()),
  updated_at           timestamptz not null default timezone('utc', now())
);

alter table public.user_preferences enable row level security;

-- ---------------------------------------------------------------------------
-- exchange_connections (encrypted payloads)
-- ---------------------------------------------------------------------------
create table if not exists public.exchange_connections (
  id            text primary key,
  user_id       text not null references public.users (id) on delete cascade,
  exchange      text not null,
  api_key_encrypted text not null,
  api_secret_encrypted text,
  status        text not null default 'active' check (status in ('active','revoked')),
  permissions   jsonb not null default '["read"]'::jsonb,
  meta          jsonb,
  created_at    timestamptz not null default timezone('utc', now()),
  updated_at    timestamptz not null default timezone('utc', now())
);

alter table public.exchange_connections enable row level security;

create index if not exists exchconn_user_idx on public.exchange_connections (user_id);

-- ---------------------------------------------------------------------------
-- risk_settings
-- ---------------------------------------------------------------------------
create table if not exists public.risk_settings (
  user_id       text primary key references public.users (id) on delete cascade,
  daily_loss_limit  numeric(18,8) not null default 1000,
  daily_trade_limit int not null default 10,
  max_position_pct numeric(5,2) not null default 20,
  kill_switch_break_only boolean not null default false,
  updated_at     timestamptz not null default timezone('utc', now())
);

alter table public.risk_settings enable row level security;

-- ---------------------------------------------------------------------------
-- billing (idempotency, invoices, subscriptions, promos)
-- ---------------------------------------------------------------------------
create table if not exists public.idempotency_records (
  key       text primary key,
  user_id   text references public.users (id) on delete cascade,
  method    text not null,
  path      text not null,
  response  jsonb,
  created_at timestamptz not null default timezone('utc', now())
);

alter table public.idempotency_records enable row level security;

create table if not exists public.invoices (
  id            text primary key,
  user_id       text not null references public.users (id) on delete cascade,
  tier          text not null check (tier in ('free','premium','vip')),
  amount        numeric(18,8) not null,
  currency      text not null default 'USD',
  status        text not null default 'pending' check (status in ('pending','paid','approved','rejected','refunded','expired')),
  provider      text,
  provider_ref  text,
  tx_ref        text,
  promo_code    text,
  discount_pct  numeric(5,2) not null default 0,
  sub_id        text,
  paid_at       timestamptz,
  created_at    timestamptz not null default timezone('utc', now())
);

alter table public.invoices enable row level security;

create index if not exists invoices_user_idx on public.invoices (user_id);

create table if not exists public.subscriptions (
  id          text primary key,
  user_id     text not null references public.users (id) on delete cascade,
  tier        text not null check (tier in ('free','premium','vip')),
  status      text not null default 'active' check (status in ('active','canceled','past_due','expired')),
  current_period_end timestamptz,
  auto_renew  boolean not null default true,
  created_at  timestamptz not null default timezone('utc', now()),
  updated_at  timestamptz not null default timezone('utc', now())
);

alter table public.subscriptions enable row level security;

create unique index if not exists subs_user_uq on public.subscriptions (user_id);

create table if not exists public.promo_codes (
  code        text primary key,
  discount_pct numeric(5,2) not null default 0,
  uses_count  int not null default 0,
  max_uses    int,
  active      boolean not null default true,
  created_at  timestamptz not null default timezone('utc', now())
);

alter table public.promo_codes enable row level security;
