-- Admin audit log: every admin mutation (user tier/admin flags, disables,
-- password resets, signal invalidations) is recorded here. Written only by the
-- backend service key, so RLS stays disabled-with-no-policies like siblings.

create table if not exists public.audit_log (
  id          text primary key,
  admin_id    text not null references public.users (id) on delete cascade,
  admin_email text not null,
  action      text not null,
  target_type text not null,
  target_id   text,
  details     jsonb,
  created_at  timestamptz not null default timezone('utc', now())
);
alter table public.audit_log enable row level security;
create index if not exists audit_log_created_idx on public.audit_log (created_at desc);
create index if not exists audit_log_target_idx  on public.audit_log (target_id);