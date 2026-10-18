-- Phase G: security sentinel
create table if not exists public.security_events (
  id          text primary key,
  user_id     text references public.users (id) on delete set null,
  ip          text,
  kind        text not null
              check (kind in ('login_fail','rate_limit','abuse','anomaly','geo','token','suspicious')),
  severity    text not null default 'info'
              check (severity in ('info','warn','high','critical')),
  details     jsonb not null default '{}'::jsonb,
  resolved    boolean not null default false,
  resolved_by text references public.users (id) on delete set null,
  resolved_at timestamptz,
  created_at  timestamptz not null default timezone('utc', now())
);

alter table public.security_events enable row level security;

create index if not exists security_events_created_idx on public.security_events (created_at desc);
create index if not exists security_events_user_idx on public.security_events (user_id, created_at desc);
create index if not exists security_events_kind_sev_idx on public.security_events (kind, severity);
