-- Signal holding-horizon taxonomy.
--
-- Additive and safe to run on the production database. Existing rows are
-- backfilled to very_long, preserving the current daily-swing behaviour.
--
-- Apply this through the Supabase SQL editor before enabling the fast lane.

alter table public.signals
  add column if not exists term text not null default 'very_long';

alter table public.signals
  add column if not exists timeframe text;

alter table public.signals
  add column if not exists resolution_interval text;

do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'signals_term_check'
  ) then
    alter table public.signals
      add constraint signals_term_check
      check (term in ('very_short', 'short', 'medium', 'long', 'very_long'));
  end if;
end $$;

update public.signals
  set term = 'very_long'
  where term is null or term = '';

create index if not exists signals_status_term_idx
  on public.signals (status, term);

alter table public.user_preferences
  add column if not exists terms text[] not null default '{}';

alter table public.auto_trade_settings
  add column if not exists terms text[] not null default '{}';
