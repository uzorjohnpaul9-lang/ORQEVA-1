-- Signal outcome tracking.
-- Each generated signal is resolved against subsequent price action so the
-- platform can report real TP/SL hit-rates instead of empty trade stats.
-- Applies idempotently; safe to re-run.

alter table public.signals add column if not exists outcome text
  check (outcome in ('tp','sl','expired','breakeven'));
alter table public.signals add column if not exists exit_price numeric(18,8);
alter table public.signals add column if not exists resolved_at timestamptz;
alter table public.signals add column if not exists r_multiple numeric(10,4);

-- Provenance: was the signal generated from live data or a simulated fallback?
alter table public.signals add column if not exists data_source text
  check (data_source in ('live','simulated'));

create index if not exists signals_outcome_idx on public.signals (outcome);

-- Backfill: signals already expired before this migration have no outcome.
update public.signals set outcome = 'expired'
  where status = 'expired' and outcome is null;
