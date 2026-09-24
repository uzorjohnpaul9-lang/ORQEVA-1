-- Grant admin role to uzorjohnpaul9@gmail.com
-- Frontend reads is_admin from the auth token's user_metadata, so we patch
-- auth.users.raw_user_meta_data; the public.users mirror (if present) is
-- updated defensively too.

do $$
declare
  target_id uuid;
begin
  select id into target_id
    from auth.users
   where lower(email) = 'uzorjohnpaul9@gmail.com';

  if target_id is null then
    raise exception 'auth.users has no row for uzorjohnpaul9@gmail.com';
  end if;

  update auth.users
     set raw_user_meta_data = coalesce(raw_user_meta_data, '{}'::jsonb)
                              || ('{"is_admin": true, "tier": "vip"}'::jsonb)
   where id = target_id;

  raise notice 'admin role granted to uzorjohnpaul9@gmail.com (auth id %)', target_id;
end $$;

-- Defensive mirror update only if the public.users table exists.
do $$
declare
  target_id uuid;
begin
  if to_regclass('public.users') is not null then
    select id into target_id
      from auth.users
     where lower(email) = 'uzorjohnpaul9@gmail.com';

    if target_id is not null then
      insert into public.users (id, email, username, tier, is_active, is_admin, created_at, updated_at)
      select id, email, split_part(email, '@', 1), 'vip'::text, true, true, now(), now()
        from auth.users
       where id = target_id
      on conflict (id) do update
         set is_admin = true, tier = 'vip', is_active = true, updated_at = now();
    end if;
  end if;
end $$;