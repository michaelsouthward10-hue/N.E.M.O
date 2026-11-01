create extension if not exists pgcrypto;

create table if not exists public.god_avatars (
  id text primary key,
  display_name text not null,
  tradition text not null,
  unlock_type text not null check (unlock_type in ('starter', 'level', 'membership', 'newsletter')),
  unlock_level integer,
  sort_order integer not null unique
);

insert into public.god_avatars (id, display_name, tradition, unlock_type, unlock_level, sort_order) values
  ('athena', 'Athena', 'Greek', 'starter', 1, 1),
  ('zeus', 'Zeus', 'Greek', 'level', 2, 2),
  ('poseidon', 'Poseidon', 'Greek', 'level', 3, 3),
  ('artemis', 'Artemis', 'Greek', 'level', 4, 4),
  ('apollo', 'Apollo', 'Greek', 'level', 5, 5),
  ('odin', 'Odin', 'Norse', 'membership', null, 6),
  ('hera', 'Hera', 'Greek', 'newsletter', null, 7)
on conflict (id) do update set
  display_name = excluded.display_name, tradition = excluded.tradition,
  unlock_type = excluded.unlock_type, unlock_level = excluded.unlock_level, sort_order = excluded.sort_order;

create table if not exists public.member_profiles (
  user_id uuid primary key references auth.users (id) on delete cascade,
  display_name text not null default 'Fellow Scholar' check (char_length(display_name) between 2 and 40),
  website_theme text not null default 'parchment' check (website_theme in ('parchment', 'odin')),
  avatar_id text not null default 'athena' references public.god_avatars (id),
  experience integer not null default 0 check (experience >= 0),
  newsletter_subscribed boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.member_avatar_unlocks (
  user_id uuid not null references auth.users (id) on delete cascade,
  avatar_id text not null references public.god_avatars (id) on delete cascade,
  unlocked_via text not null check (unlocked_via in ('starter', 'level', 'membership', 'newsletter')),
  unlocked_at timestamptz not null default now(),
  primary key (user_id, avatar_id)
);

create or replace function public.create_member_profile()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  chosen_name text;
begin
  chosen_name := left(trim(coalesce(new.raw_user_meta_data ->> 'display_name', 'Fellow Scholar')), 40);
  if char_length(chosen_name) < 2 then
    chosen_name := 'Fellow Scholar';
  end if;
  insert into public.member_profiles (user_id, display_name)
  values (new.id, chosen_name)
  on conflict (user_id) do nothing;
  insert into public.member_avatar_unlocks (user_id, avatar_id, unlocked_via)
  values (new.id, 'athena', 'starter')
  on conflict (user_id, avatar_id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created_member_profile on auth.users;
create trigger on_auth_user_created_member_profile
  after insert on auth.users
  for each row execute procedure public.create_member_profile();

create table if not exists public.memberships (
  user_id uuid primary key references auth.users (id) on delete cascade,
  stripe_customer_id text not null unique,
  stripe_subscription_id text not null unique,
  status text not null check (status in ('incomplete', 'incomplete_expired', 'trialing', 'active', 'past_due', 'canceled', 'unpaid', 'paused')),
  current_period_start timestamptz not null,
  current_period_end timestamptz not null,
  cancel_at_period_end boolean not null default false,
  last_event_created bigint not null default 0,
  updated_at timestamptz not null default now()
);

create or replace function public.is_fellow_scholar(target_user_id uuid default auth.uid())
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
    from public.memberships m
    where m.user_id = target_user_id
      and target_user_id = (select auth.uid())
      and m.status in ('active', 'trialing')
      and m.current_period_end > now()
  );
$$;

revoke all on function public.is_fellow_scholar(uuid) from public, anon;
grant execute on function public.is_fellow_scholar(uuid) to authenticated, service_role;

create or replace function public.can_use_god_avatar(target_avatar_id text)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1 from public.member_avatar_unlocks a
    where a.user_id = (select auth.uid()) and a.avatar_id = target_avatar_id
  );
$$;

revoke all on function public.can_use_god_avatar(text) from public, anon;
grant execute on function public.can_use_god_avatar(text) to authenticated;

create or replace function public.can_use_website_theme(target_theme text)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select target_theme = 'parchment'
    or public.is_fellow_scholar((select auth.uid()))
    or exists (
      select 1 from public.member_profiles p
      where p.user_id = (select auth.uid()) and p.website_theme = target_theme
    );
$$;

revoke all on function public.can_use_website_theme(text) from public, anon;
grant execute on function public.can_use_website_theme(text) to authenticated;

create table if not exists public.scholar_stories (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  byline text not null default 'Fellow Scholar' check (char_length(byline) between 2 and 40),
  submission_month date not null,
  title text not null check (char_length(title) between 4 and 100),
  tradition text not null check (char_length(tradition) between 2 and 80),
  region text not null default '' check (char_length(region) <= 100),
  story text not null check (char_length(story) between 100 and 8000),
  source_notes text not null default '' check (char_length(source_notes) <= 1200),
  sharing_consent boolean not null default false,
  status text not null default 'pending' check (status in ('pending', 'needs_revision', 'approved', 'rejected')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, submission_month)
);

create index if not exists scholar_stories_public_wall_idx
  on public.scholar_stories (created_at desc)
  where status = 'approved';

create or replace function public.prepare_scholar_story()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  chosen_name text;
begin
  if auth.uid() is null then
    raise exception 'A signed-in author is required.' using errcode = '42501';
  end if;

  if tg_op = 'INSERT' then
    new.user_id := auth.uid();
    new.submission_month := date_trunc('month', timezone('UTC', now()))::date;
    new.status := 'pending';
    if new.sharing_consent is not true then
      raise exception 'Please confirm you have permission to share this story.' using errcode = '42501';
    end if;
    select p.display_name into chosen_name
      from public.member_profiles p where p.user_id = auth.uid();
    new.byline := coalesce(chosen_name, 'Fellow Scholar');
    new.created_at := now();
  else
    if auth.uid() <> old.user_id then
      raise exception 'Only the author can edit this story.' using errcode = '42501';
    end if;
    if old.status not in ('pending', 'needs_revision') then
      raise exception 'Only pending stories can be edited.' using errcode = '42501';
    end if;
    new.user_id := old.user_id;
    new.submission_month := old.submission_month;
    new.byline := old.byline;
    new.sharing_consent := old.sharing_consent;
    new.created_at := old.created_at;
    if old.status = 'needs_revision' then
      new.status := 'pending';
    else
      new.status := old.status;
    end if;
    new.updated_at := now();
  end if;
  return new;
end;
$$;

drop trigger if exists prepare_scholar_story on public.scholar_stories;
create trigger prepare_scholar_story
  before insert or update on public.scholar_stories
  for each row execute procedure public.prepare_scholar_story();

create table if not exists public.scholar_wallpapers (
  id uuid primary key default gen_random_uuid(),
  title text not null check (char_length(title) between 2 and 80),
  tradition text not null check (char_length(tradition) between 2 and 80),
  release_month date not null,
  orientation text not null check (orientation in ('desktop', 'mobile')),
  object_path text not null unique,
  created_at timestamptz not null default now()
);

create table if not exists public.daily_quiz_answer_keys (
  quiz_id text primary key,
  answers smallint[] not null,
  question_count integer not null check (question_count > 0),
  xp_per_correct integer not null default 20,
  completion_xp integer not null default 10,
  active boolean not null default true,
  check (cardinality(answers) = question_count)
);

insert into public.daily_quiz_answer_keys (quiz_id, answers, question_count, xp_per_correct, completion_xp)
values ('athena-olive-01', array[0,1,0,1,0]::smallint[], 5, 20, 10)
on conflict (quiz_id) do update set
  answers = excluded.answers, question_count = excluded.question_count,
  xp_per_correct = excluded.xp_per_correct, completion_xp = excluded.completion_xp, active = true;

create table if not exists public.daily_quiz_attempts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  quiz_id text not null references public.daily_quiz_answer_keys (quiz_id),
  quiz_date date not null,
  correct_answers integer not null,
  xp_earned integer not null,
  created_at timestamptz not null default now(),
  unique (user_id, quiz_id, quiz_date)
);

insert into storage.buckets (id, name, public)
values ('scholar-wallpapers', 'scholar-wallpapers', false)
on conflict (id) do update set public = false;

alter table public.member_profiles enable row level security;
alter table public.memberships enable row level security;
alter table public.scholar_stories enable row level security;
alter table public.scholar_wallpapers enable row level security;
alter table public.god_avatars enable row level security;
alter table public.daily_quiz_answer_keys enable row level security;
alter table public.daily_quiz_attempts enable row level security;
alter table public.member_avatar_unlocks enable row level security;

revoke all on public.member_profiles, public.memberships, public.scholar_stories, public.scholar_wallpapers, public.daily_quiz_attempts, public.member_avatar_unlocks from anon, authenticated;
revoke all on public.daily_quiz_answer_keys from anon, authenticated;
revoke all on public.god_avatars from anon, authenticated;
grant select on public.god_avatars to anon, authenticated;
grant select on public.member_avatar_unlocks to authenticated;
grant select, update (display_name, website_theme, avatar_id) on public.member_profiles to authenticated;
grant select on public.memberships to authenticated;
grant select on public.scholar_stories to anon, authenticated;
grant insert (title, tradition, region, story, source_notes, sharing_consent) on public.scholar_stories to authenticated;
grant update (title, tradition, region, story, source_notes) on public.scholar_stories to authenticated;
grant select on public.scholar_wallpapers to authenticated;
grant all on public.member_profiles, public.memberships, public.scholar_stories, public.scholar_wallpapers, public.daily_quiz_attempts, public.daily_quiz_answer_keys, public.god_avatars, public.member_avatar_unlocks to service_role;

drop policy if exists "Anyone can see the avatar collection" on public.god_avatars;
create policy "Anyone can see the avatar collection" on public.god_avatars
  for select to anon, authenticated using (true);

drop policy if exists "Scholars read their own portrait unlocks" on public.member_avatar_unlocks;
create policy "Scholars read their own portrait unlocks" on public.member_avatar_unlocks
  for select to authenticated using (user_id = auth.uid());

drop policy if exists "Members read their own profile" on public.member_profiles;
create policy "Members read their own profile"
  on public.member_profiles for select to authenticated
  using (user_id = auth.uid());

drop policy if exists "Members update their profile" on public.member_profiles;
create policy "Members update their profile"
  on public.member_profiles for update to authenticated
  using (user_id = auth.uid())
  with check (
    user_id = auth.uid()
    and public.can_use_website_theme(website_theme)
    and public.can_use_god_avatar(avatar_id)
  );

drop policy if exists "Members read their own subscription" on public.memberships;
create policy "Members read their own subscription"
  on public.memberships for select to authenticated
  using (user_id = auth.uid());

drop policy if exists "Public can read approved stories and authors can read their own" on public.scholar_stories;
create policy "Public can read approved stories and authors can read their own"
  on public.scholar_stories for select to anon, authenticated
  using (status = 'approved' or user_id = auth.uid());

drop policy if exists "Active scholars can submit one story per month" on public.scholar_stories;
create policy "Active scholars can submit one story per month"
  on public.scholar_stories for insert to authenticated
  with check (
    user_id = auth.uid()
    and status = 'pending'
    and public.is_fellow_scholar(auth.uid())
  );

drop policy if exists "Authors can edit stories awaiting review" on public.scholar_stories;
create policy "Authors can edit stories awaiting review"
  on public.scholar_stories for update to authenticated
  using (user_id = auth.uid() and status in ('pending', 'needs_revision'))
  with check (user_id = auth.uid() and status in ('pending', 'needs_revision'));

drop policy if exists "Members can see wallpaper details" on public.scholar_wallpapers;
create policy "Members can see wallpaper details"
  on public.scholar_wallpapers for select to authenticated
  using (public.is_fellow_scholar(auth.uid()));

drop policy if exists "Active scholars can download wallpaper files" on storage.objects;
create policy "Active scholars can download wallpaper files"
  on storage.objects for select to authenticated
  using (bucket_id = 'scholar-wallpapers' and public.is_fellow_scholar(auth.uid()));

create or replace function public.sync_membership_from_stripe(
  p_user_id uuid,
  p_customer_id text,
  p_subscription_id text,
  p_status text,
  p_period_start timestamptz,
  p_period_end timestamptz,
  p_cancel_at_period_end boolean,
  p_event_created bigint
)
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.memberships (
    user_id, stripe_customer_id, stripe_subscription_id, status,
    current_period_start, current_period_end, cancel_at_period_end, last_event_created, updated_at
  ) values (
    p_user_id, p_customer_id, p_subscription_id, p_status,
    p_period_start, p_period_end, p_cancel_at_period_end, p_event_created, now()
  )
  on conflict (user_id) do update set
    stripe_customer_id = excluded.stripe_customer_id,
    stripe_subscription_id = excluded.stripe_subscription_id,
    status = excluded.status,
    current_period_start = excluded.current_period_start,
    current_period_end = excluded.current_period_end,
    cancel_at_period_end = excluded.cancel_at_period_end,
    last_event_created = excluded.last_event_created,
    updated_at = now()
  where public.memberships.last_event_created <= excluded.last_event_created;

  if exists (
    select 1 from public.memberships m
    where m.user_id = p_user_id and m.status in ('active', 'trialing') and m.current_period_end > now()
  ) then
    insert into public.member_avatar_unlocks (user_id, avatar_id, unlocked_via)
    values (p_user_id, 'odin', 'membership')
    on conflict (user_id, avatar_id) do nothing;
  end if;
end;
$$;

revoke all on function public.sync_membership_from_stripe(uuid, text, text, text, timestamptz, timestamptz, boolean, bigint) from public, anon, authenticated;
grant execute on function public.sync_membership_from_stripe(uuid, text, text, text, timestamptz, timestamptz, boolean, bigint) to service_role;

create or replace function public.submit_quiz_attempt(p_quiz_id text, p_answers smallint[])
returns table (xp_awarded integer, total_experience integer, scholar_level integer, newly_unlocked_avatars text[])
language plpgsql
security definer
set search_path = ''
as $$
declare
  caller_id uuid := auth.uid();
  expected_answers smallint[];
  expected_count integer;
  correct_count integer;
  points integer;
  previous_experience integer;
  inserted_attempt boolean;
begin
  if caller_id is null then
    raise exception 'Sign in to save quiz experience.' using errcode = '42501';
  end if;
  if p_answers is null then
    raise exception 'Quiz answers are required.' using errcode = '22023';
  end if;

  select k.answers, k.question_count into expected_answers, expected_count
    from public.daily_quiz_answer_keys k
    where k.quiz_id = p_quiz_id and k.active;
  if expected_answers is null then
    raise exception 'This quiz is unavailable for experience.' using errcode = '22023';
  end if;
  if cardinality(p_answers) <> expected_count then
    raise exception 'Please answer every quiz question.' using errcode = '22023';
  end if;
  if array_position(p_answers, null::smallint) is not null then
    raise exception 'Every quiz question needs an answer.' using errcode = '22023';
  end if;
  if exists (select 1 from unnest(p_answers) as supplied(value) where supplied.value < 0 or supplied.value > 10) then
    raise exception 'One or more quiz answers are invalid.' using errcode = '22023';
  end if;

  select count(*)::integer into correct_count
    from generate_subscripts(expected_answers, 1) as positions(question_index)
    where p_answers[positions.question_index] = expected_answers[positions.question_index];

  select p.experience into previous_experience
    from public.member_profiles p where p.user_id = caller_id for update;
  if previous_experience is null then
    raise exception 'Your scholar profile could not be found.' using errcode = 'P0002';
  end if;

  points := correct_count * 20 + 10;
  insert into public.daily_quiz_attempts (user_id, quiz_id, quiz_date, correct_answers, xp_earned)
  values (caller_id, p_quiz_id, date_trunc('day', timezone('UTC', now()))::date, correct_count, points)
  on conflict (user_id, quiz_id, quiz_date) do nothing
  returning true into inserted_attempt;

  if inserted_attempt is distinct from true then
    select a.xp_earned into points from public.daily_quiz_attempts a
      where a.user_id = caller_id and a.quiz_id = p_quiz_id
        and a.quiz_date = date_trunc('day', timezone('UTC', now()))::date;
    return query select 0, previous_experience,
      floor(previous_experience / 100.0)::integer + 1, array[]::text[];
    return;
  end if;

  update public.member_profiles p
    set experience = p.experience + points, updated_at = now()
    where p.user_id = caller_id
    returning p.experience into total_experience;
  scholar_level := floor(total_experience / 100.0)::integer + 1;
  xp_awarded := points;
  insert into public.member_avatar_unlocks (user_id, avatar_id, unlocked_via)
    select caller_id, a.id, 'level' from public.god_avatars a
    where a.unlock_type = 'level' and a.unlock_level <= scholar_level
    on conflict (user_id, avatar_id) do nothing;
  select coalesce(array_agg(a.id order by a.sort_order), array[]::text[])
    into newly_unlocked_avatars
    from public.god_avatars a
    where a.unlock_type = 'level'
      and a.unlock_level > floor(previous_experience / 100.0)::integer + 1
      and a.unlock_level <= scholar_level;
  return next;
end;
$$;

revoke all on function public.submit_quiz_attempt(text, smallint[]) from public, anon;
grant execute on function public.submit_quiz_attempt(text, smallint[]) to authenticated;

