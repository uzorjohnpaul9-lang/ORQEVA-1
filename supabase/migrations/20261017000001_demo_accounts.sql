-- Demo accounts (Phase D).
-- Paper trades (no broker / 'paper' venue) are the demo ledger; live-routed
-- trades (a real exchange venue) are the live ledger. Each user gets a
-- configurable demo starting balance so the demo book can be reset.
-- Applies idempotently; safe to re-run.

alter table public.trades
  add column if not exists is_demo boolean not null default false;

-- Existing paper trades are demo trades.
update public.trades
  set is_demo = true
  where (exchange is null or exchange = 'paper') and is_demo = false;

create index if not exists trades_user_demo_opened_idx
  on public.trades (user_id, is_demo, opened_at desc);

alter table public.user_preferences
  add column if not exists demo_starting_balance numeric(18,8) not null default 100000;

alter table public.user_preferences
  drop constraint if exists user_preferences_demo_balance_chk;
alter table public.user_preferences
  add constraint user_preferences_demo_balance_chk
  check (demo_starting_balance >= 0);
