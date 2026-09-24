-- Runtime schema for ORQEVA backend (matches backend/*.py insert/update/fetch shapes).
-- Applies idempotently; safe to re-run. Backend writes via the service (secret) key,
-- which bypasses RLS, so tables are RLS-enabled for browser safety but no policies yet.

-- users ----------------------------------------------------------------------
create table if not exists public.users (
  id              text primary key,
  email           text not null,
  username        text not null,
  tier            text not null default 'free' check (tier in ('free','premium','vip')),
  is_admin        boolean not null default false,
  is_active       boolean not null default true,
  telegram_chat_id text,
  created_at      timestamptz not null default timezone('utc', now()),
  updated_at      timestamptz not null default timezone('utc', now())
);
alter table public.users enable row level security;
create unique index if not exists users_email_uq    on public.users (email);
create unique index if not exists users_username_uq on public.users (username);

-- password_reset_tokens ------------------------------------------------------
create table if not exists public.password_reset_tokens (
  id         text primary key,
  user_id    text not null references public.users (id) on delete cascade,
  token_hash text not null,
  expires_at timestamptz not null,
  used       boolean not null default false,
  created_at timestamptz not null default timezone('utc', now())
);
alter table public.password_reset_tokens enable row level security;
create index if not exists prt_token_hash_uq on public.password_reset_tokens (token_hash);

-- signals --------------------------------------------------------------------
create table if not exists public.signals (
  id            text primary key,
  user_id       text default null references public.users (id) on delete cascade,
  symbol        text not null,
  market        text not null check (market in ('stock','forex','crypto','commodity')),
  direction     text not null check (direction in ('buy','sell')),
  confidence    numeric(6,4) not null default 0,
  entry_price   numeric(18,8),
  stop_loss     numeric(18,8),
  take_profit   numeric(18,8),
  strategy      text,
  status        text not null default 'active' check (status in ('pending','active','expired','executed','closed','cancelled')),
  tier_required text not null default 'free' check (tier_required in ('free','premium','vip')),
  indicators    jsonb,
  created_at    timestamptz not null default timezone('utc', now()),
  expires_at    timestamptz
);
alter table public.signals enable row level security;
create index if not exists signals_tier_status_created_idx on public.signals (tier_required, status, created_at desc);
create index if not exists signals_market_created_idx      on public.signals (market, created_at desc);

-- trades ---------------------------------------------------------------------
create table if not exists public.trades (
  id              text primary key,
  user_id         text not null references public.users (id) on delete cascade,
  signal_id       text references public.signals (id) on delete set null,
  symbol          text not null,
  market          text not null check (market in ('stock','forex','crypto','commodity')),
  side            text not null check (side in ('buy','sell')),
  quantity        numeric(18,8) not null,
  entry_price     numeric(18,8) not null,
  exit_price      numeric(18,8),
  pnl             numeric(18,8),
  status          text not null default 'open' check (status in ('open','closed','cancelled','pending')),
  strategy        text,
  exchange        text,
  broker_order_id text,
  stop_loss       numeric(18,8),
  take_profit     numeric(18,8),
  opened_at       timestamptz not null default timezone('utc', now()),
  closed_at       timestamptz
);
alter table public.trades enable row level security;
create index if not exists trades_user_opened_idx on public.trades (user_id, opened_at desc);
create index if not exists trades_user_status_idx on public.trades (user_id, status);

-- notifications --------------------------------------------------------------
create table if not exists public.notifications (
  id         text primary key,
  user_id    text not null references public.users (id) on delete cascade,
  type       text not null,
  title      text not null,
  message    text not null,
  is_read    boolean not null default false,
  channel    text not null default 'in_app',
  created_at timestamptz not null default timezone('utc', now())
);
alter table public.notifications enable row level security;
create index if not exists notifications_user_created_idx on public.notifications (user_id, created_at desc);

-- user_preferences -----------------------------------------------------------
create table if not exists public.user_preferences (
  id                    text primary key,
  user_id               text not null references public.users (id) on delete cascade,
  telegram_signals      boolean not null default true,
  telegram_tp_sl        boolean not null default true,
  telegram_market_analysis boolean not null default false,
  telegram_risk_alerts  boolean not null default true,
  telegram_system_alerts boolean not null default true,
  email_notifications   boolean not null default false,
  web_notifications     boolean not null default true,
  default_market        text not null default 'all',
  risk_tolerance        text not null default 'moderate',
  theme                 text not null default 'dark'
);
alter table public.user_preferences enable row level security;
create unique index if not exists prefs_user_uq on public.user_preferences (user_id);

-- exchange_connections -------------------------------------------------------
create table if not exists public.exchange_connections (
  id                 text primary key,
  user_id            text not null references public.users (id) on delete cascade,
  exchange           text not null,
  api_key_encrypted  text not null,
  api_secret_encrypted text,
  is_paper           boolean not null default true,
  is_active          boolean not null default false,
  connected_at       timestamptz not null default timezone('utc', now()),
  last_checked       timestamptz
);
alter table public.exchange_connections enable row level security;
create index if not exists exchconn_user_connected_idx on public.exchange_connections (user_id, connected_at desc);

-- risk_settings --------------------------------------------------------------
create table if not exists public.risk_settings (
  id                    text primary key,
  user_id               text not null references public.users (id) on delete cascade,
  max_daily_loss_pct    numeric(6,2) not null default 5.0,
  max_positions         int not null default 10,
  max_position_size_pct numeric(6,2) not null default 10.0,
  max_daily_trades      int not null default 20,
  kill_switch_active    boolean not null default false,
  updated_at            timestamptz not null default timezone('utc', now()),
  last_checked          timestamptz
);
alter table public.risk_settings enable row level security;
create unique index if not exists risk_user_uq on public.risk_settings (user_id);

-- idempotency_records --------------------------------------------------------
create table if not exists public.idempotency_records (
  id            text primary key,
  user_id       text not null references public.users (id) on delete cascade,
  endpoint      text not null,
  key           text not null,
  response_json jsonb,
  created_at    timestamptz not null default timezone('utc', now())
);
alter table public.idempotency_records enable row level security;
create unique index if not exists idem_user_endpoint_key_uq on public.idempotency_records (user_id, endpoint, key);

-- invoices -------------------------------------------------------------------
create table if not exists public.invoices (
  id            text primary key,
  user_id       text not null references public.users (id) on delete cascade,
  tier          text not null check (tier in ('free','premium','vip')),
  method        text not null default 'crypto' check (method in ('crypto','manual')),
  network       text,
  wallet_address text,
  amount_usd    numeric(18,2) not null,
  discount_usd  numeric(18,2) not null default 0,
  promo_code    text,
  status        text not null default 'pending' check (status in ('pending','approved','rejected','cancelled','refunded','expired')),
  tx_ref        text,
  note          text,
  created_at    timestamptz not null default timezone('utc', now()),
  expires_at    timestamptz,
  processed_at  timestamptz,
  processed_by  text
);
alter table public.invoices enable row level security;
create index if not exists invoices_user_created_idx on public.invoices (user_id, created_at desc);

-- subscriptions --------------------------------------------------------------
create table if not exists public.subscriptions (
  id               text primary key,
  user_id          text not null references public.users (id) on delete cascade,
  tier             text not null check (tier in ('free','premium','vip')),
  status           text not null default 'active' check (status in ('active','expired','cancelled')),
  auto_renew       boolean not null default true,
  started_at       timestamptz not null default timezone('utc', now()),
  expires_at       timestamptz,
  last_invoice_id  text
);
alter table public.subscriptions enable row level security;
create unique index if not exists subs_user_uq on public.subscriptions (user_id);

-- promo_codes ----------------------------------------------------------------
create table if not exists public.promo_codes (
  code         text primary key,
  discount_pct numeric(5,2) not null default 0,
  uses_count   int not null default 0,
  max_uses     int,
  active       boolean not null default true,
  expires_at   timestamptz,
  created_at   timestamptz not null default timezone('utc', now())
);
alter table public.promo_codes enable row level security;