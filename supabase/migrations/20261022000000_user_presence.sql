-- Presence: "online" is derived from last_seen_at and is deliberately
-- separate from is_active (which means the account is enabled, not that the
-- person is currently on the site).
alter table public.users add column if not exists last_seen_at timestamptz;

comment on column public.users.last_seen_at is
  'Last authenticated API activity (presence heartbeat). NULL = never seen since presence shipped.';

create index if not exists users_last_seen_idx on public.users (last_seen_at desc);
