-- Auto-mirror every new auth.users row into public.users + user_preferences.
-- Frontend signs users up directly via Supabase Auth (browser -> Supabase), so
-- the backend's public.users lookup (backend/auth.py get_current_user) must find
-- a matching row. Without this, every new signup would 401 on protected routes.

-- Backfill existing auth users that never got a public.users mirror.
-- Same rule as handle_new_user(): do not promote privileges from user metadata.
do $$
declare
  r record;
  meta jsonb;
  uname text;
begin
  for r in
    select u.id, u.email
      from auth.users u
     where u.email_confirmed_at is not null
  loop
    select raw_user_meta_data into meta from auth.users where id = r.id;

    uname := coalesce(
      nullif(meta ->> 'username', ''),
      split_part(r.email, '@', 1)
    );

    insert into public.users (id, email, username, tier, is_active, is_admin, created_at, updated_at)
    values (
      r.id,
      r.email,
      left(uname, 100),
      'free',
      true,
      false,
      now(), now())
    on conflict (id) do nothing;
  end loop;
end $$;

-- Trigger function + trigger only: creates mirror rows for NEW signups.
--
-- SECURITY: never read is_admin or tier from new.raw_user_meta_data. Signup is
-- performed browser-side with the publishable (anon) key, so raw_user_meta_data
-- is attacker-controlled. Only backend/api/admin.py may grant is_admin/tier.
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  uname text := coalesce(
    nullif(new.raw_user_meta_data ->> 'username', ''),
    split_part(new.email, '@', 1)
  );
begin
  insert into public.users
    (id, email, username, tier, is_active, is_admin, telegram_chat_id, created_at, updated_at)
  values
    (new.id, new.email, left(uname, 100), 'free', true,
     false,
     null, now(), now())
  on conflict (id) do nothing;

  insert into public.user_preferences (id, user_id)
  values (gen_random_uuid()::text, new.id)
  on conflict (user_id) do nothing;

  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();