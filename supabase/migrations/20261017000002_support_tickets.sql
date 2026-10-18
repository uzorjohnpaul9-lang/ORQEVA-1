-- Phase F: support channel + admin read-only context.
-- A support ticket is created either by a signed-in user or from the login
-- page (user_id null, contact email required). Admins read the queue and reply;
-- the context view reads a user's data without ever mutating it.
create table if not exists public.support_tickets (
  id          text primary key,
  user_id     text references public.users (id) on delete set null,
  email       text not null,
  subject     text not null,
  message     text not null,
  category    text not null default 'general'
              check (category in ('general','billing','technical','account','other')),
  status      text not null default 'open'
              check (status in ('open','in_progress','resolved','closed')),
  priority    text not null default 'normal'
              check (priority in ('low','normal','high')),
  source      text not null default 'app'
              check (source in ('app','login')),
  assigned_to text references public.users (id) on delete set null,
  reply       text,
  replied_by  text,
  replied_at  timestamptz,
  created_at  timestamptz not null default timezone('utc', now()),
  updated_at  timestamptz not null default timezone('utc', now())
);

alter table public.support_tickets enable row level security;

create index if not exists support_tickets_status_idx on public.support_tickets (status, created_at desc);
create index if not exists support_tickets_user_idx on public.support_tickets (user_id, created_at desc);
