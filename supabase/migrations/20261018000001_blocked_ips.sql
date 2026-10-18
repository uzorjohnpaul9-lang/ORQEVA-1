-- Phase G: auto-block IP TTL list (sentinel middleware)
create table if not exists public.blocked_ips (
  ip            text primary key,
  reason        text not null default '',
  hits          integer not null default 1,
  blocked_until timestamptz,
  created_at    timestamptz not null default timezone('utc', now()),
  created_by    text not null default 'sentinel',
  cleared_at    timestamptz
);

alter table public.blocked_ips enable row level security;

create index if not exists blocked_ips_until_idx on public.blocked_ips (blocked_until);
