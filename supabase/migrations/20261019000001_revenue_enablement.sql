-- Phase K: revenue enablement.
-- Annual billing term on invoices, affiliate partner tracking (broker +
-- prop-firm links with click/conversion attribution), metered API keys.

-- invoices: annual term -------------------------------------------------------
-- NULL means the default monthly term; a yearly plan stores 365.
alter table public.invoices add column if not exists duration_days int;
create index if not exists invoices_user_status_idx on public.invoices (user_id, status);

-- affiliate partners ----------------------------------------------------------
create table if not exists public.affiliate_partners (
  id               text primary key,
  name             text not null,
  url              text not null,
  category         text not null default 'broker'
                   check (category in ('broker', 'prop_firm', 'partner')),
  click_count      int not null default 0,
  conversion_count int not null default 0,
  revenue_usd      numeric(12,2) not null default 0,
  active           boolean not null default true,
  created_at       timestamptz not null default timezone('utc', now())
);
alter table public.affiliate_partners enable row level security;

create table if not exists public.affiliate_clicks (
  id         text primary key,
  partner_id text not null references public.affiliate_partners(id) on delete cascade,
  user_id    text,
  created_at timestamptz not null default timezone('utc', now())
);
alter table public.affiliate_clicks enable row level security;
create index if not exists affiliate_clicks_user_idx on public.affiliate_clicks (user_id, created_at desc);

create table if not exists public.affiliate_conversions (
  id         text primary key,
  partner_id text not null references public.affiliate_partners(id) on delete cascade,
  user_id    text,
  invoice_id text,
  amount_usd numeric(12,2) not null default 0,
  created_at timestamptz not null default timezone('utc', now())
);
alter table public.affiliate_conversions enable row level security;
create index if not exists affiliate_conversions_partner_idx on public.affiliate_conversions (partner_id, created_at desc);

-- api keys (metered signal API) ------------------------------------------------
create table if not exists public.api_keys (
  id             text primary key,
  user_id        text not null,
  name           text not null default 'default',
  key_hash       text not null,
  key_prefix     text not null,
  created_at     timestamptz not null default timezone('utc', now()),
  last_used_at   timestamptz,
  revoked_at     timestamptz,
  usage_day      date,
  requests_today int not null default 0,
  requests_total int not null default 0
);
alter table public.api_keys enable row level security;
create unique index if not exists api_keys_hash_uq on public.api_keys (key_hash);
create index if not exists api_keys_user_idx on public.api_keys (user_id, created_at desc);
