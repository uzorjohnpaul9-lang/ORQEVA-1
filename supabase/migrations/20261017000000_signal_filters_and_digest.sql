-- Signal filters + weekly digest (Phase C).
-- Per-user watchlist / direction / confidence filters for Telegram signal
-- alerts, plus an opt-in weekly digest. Applies idempotently; safe to re-run.

alter table public.user_preferences
  add column if not exists watchlist text[] not null default '{}';
alter table public.user_preferences
  add column if not exists directions text[] not null default '{}';
alter table public.user_preferences
  add column if not exists min_confidence numeric(4,3) not null default 0;
alter table public.user_preferences
  add column if not exists telegram_weekly_digest boolean not null default false;

alter table public.user_preferences
  drop constraint if exists user_preferences_min_confidence_chk;
alter table public.user_preferences
  add constraint user_preferences_min_confidence_chk
  check (min_confidence >= 0 and min_confidence <= 1);
