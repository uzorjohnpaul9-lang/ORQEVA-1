-- Phase I: billing scale.
-- Gateway columns on invoices, idempotent payment_events log, subscription
-- grace/cancel-at-period-end + provider binding for renewals.

-- invoices ------------------------------------------------------------------------
alter table public.invoices add column if not exists provider     text not null default 'manual';
alter table public.invoices add column if not exists provider_ref text;
alter table public.invoices add column if not exists checkout_url text;
alter table public.invoices add column if not exists unique_amount numeric(18,2);
alter table public.invoices add column if not exists memo         text;
alter table public.invoices add column if not exists currency     text not null default 'USD';
alter table public.invoices add column if not exists paid_at      timestamptz;

create unique index if not exists invoices_provider_ref_uq
  on public.invoices (provider, provider_ref) where provider_ref is not null;
create index if not exists invoices_status_created_idx on public.invoices (status, created_at desc);

-- payment_events ------------------------------------------------------------------
create table if not exists public.payment_events (
  id          text primary key,
  provider    text not null,
  event_id    text not null,
  invoice_id  text,
  type        text,
  status      text not null default 'processed' check (status in ('processed','ignored','error','duplicate')),
  detail      text,
  payload     jsonb,
  created_at  timestamptz not null default timezone('utc', now())
);
alter table public.payment_events enable row level security;
create unique index if not exists payment_events_provider_event_uq
  on public.payment_events (provider, event_id);
create index if not exists payment_events_invoice_idx on public.payment_events (invoice_id);

-- subscriptions -------------------------------------------------------------------
alter table public.subscriptions add column if not exists grace_until            timestamptz;
alter table public.subscriptions add column if not exists provider               text;
alter table public.subscriptions add column if not exists provider_ref           text;
alter table public.subscriptions add column if not exists cancel_at_period_end   boolean not null default false;
alter table public.subscriptions add column if not exists reminder_sent_count    int not null default 0;
