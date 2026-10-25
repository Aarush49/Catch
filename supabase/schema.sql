-- Ripple database schema. Run this whole file in the Supabase SQL Editor.
-- Every table is owned by a Supabase Auth user (auth.users). The mobile app
-- reads and writes its own rows directly through row level security; the
-- backend uses the service-role key only for bank data it imports from Nessie.
-- Safe to re-run: it creates missing objects and never deletes Ripple data.

begin;

create extension if not exists pgcrypto;

-- One-time cleanup of the retired backend-only schema (custom users/sessions
-- tables and ripple_* RPCs). Aborts instead of dropping anything that holds rows.
do $$
declare
  legacy boolean;
  t text;
  has_rows boolean;
  fn regprocedure;
begin
  legacy := to_regclass('public.sessions') is not null
    or to_regclass('public.users') is not null
    or exists (select 1 from information_schema.columns
               where table_schema = 'public' and table_name = 'receipt_items' and column_name = 'expanded_name');
  if not legacy then
    return;
  end if;
  foreach t in array array['receipt_items', 'receipts', 'shopping_items', 'transactions', 'linked_accounts', 'sessions', 'users'] loop
    if to_regclass('public.' || t) is not null then
      execute format('select exists (select 1 from public.%I)', t) into has_rows;
      if has_rows then
        raise exception 'Legacy table public.% contains data; migrate it manually before running this schema.', t;
      end if;
    end if;
  end loop;
  for fn in select p.oid::regprocedure from pg_proc p join pg_namespace n on n.oid = p.pronamespace
            where n.nspname = 'public' and p.proname like 'ripple\_%' loop
    execute format('drop function %s', fn);
  end loop;
  drop schema if exists ripple_private cascade;
  drop table if exists public.receipt_items, public.receipts, public.shopping_items, public.transactions,
    public.linked_accounts, public.sessions, public.users cascade;
end;
$$;

create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  display_name text,
  created_at timestamptz not null default now()
);

create table if not exists public.receipts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  merchant text,
  purchased_at date,
  subtotal numeric not null default 0 check (subtotal >= 0),
  tax numeric not null default 0 check (tax >= 0),
  total numeric not null default 0 check (total >= 0),
  image_path text,
  created_at timestamptz not null default now()
);
create index if not exists receipts_user_date_idx on public.receipts (user_id, purchased_at desc);

-- price is the unit price; the line total is price * quantity.
create table if not exists public.receipt_items (
  id uuid primary key default gen_random_uuid(),
  receipt_id uuid not null references public.receipts(id) on delete cascade,
  position integer not null default 0,
  name text not null check (length(btrim(name)) > 0),
  quantity numeric not null default 1 check (quantity > 0),
  price numeric not null check (price >= 0),
  category text not null default 'Other' check (category in ('Groceries','Dining','Household','Health','Transport','Other')),
  carbon_kg_co2e numeric check (carbon_kg_co2e >= 0)
);
create index if not exists receipt_items_receipt_idx on public.receipt_items (receipt_id, position);

-- price/brand/category/allow_lower_quality are optional inputs for the
-- backend's SerpAPI comparison; the app's list only needs name and completed.
create table if not exists public.shopping_items (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  name text not null check (length(btrim(name)) > 0),
  completed boolean not null default false,
  price numeric check (price > 0),
  brand text,
  category text not null default 'other',
  allow_lower_quality boolean not null default false,
  created_at timestamptz not null default now()
);
create index if not exists shopping_items_user_idx on public.shopping_items (user_id, created_at);

create table if not exists public.accepted_recommendations (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  original_name text not null,
  replacement_name text not null,
  savings numeric not null default 0,
  created_at timestamptz not null default now()
);

create table if not exists public.linked_accounts (
  user_id uuid primary key references auth.users(id) on delete cascade,
  provider text not null default 'nessie',
  customer_id text not null,
  account_id text not null,
  linked_at timestamptz not null default now()
);

create table if not exists public.transactions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  source text not null,
  external_id text not null,
  transaction_type text not null,
  amount numeric not null,
  date date not null,
  description text not null default '',
  category text not null default 'other',
  raw_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (user_id, source, external_id)
);
create index if not exists transactions_user_date_idx on public.transactions (user_id, date);

alter table public.profiles enable row level security;
alter table public.receipts enable row level security;
alter table public.receipt_items enable row level security;
alter table public.shopping_items enable row level security;
alter table public.accepted_recommendations enable row level security;
alter table public.linked_accounts enable row level security;
alter table public.transactions enable row level security;

drop policy if exists "profiles own row" on public.profiles;
create policy "profiles own row" on public.profiles for all to authenticated
  using ((select auth.uid()) = id) with check ((select auth.uid()) = id);
drop policy if exists "receipts own rows" on public.receipts;
create policy "receipts own rows" on public.receipts for all to authenticated
  using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
drop policy if exists "receipt items through owned receipt" on public.receipt_items;
create policy "receipt items through owned receipt" on public.receipt_items for all to authenticated
  using (exists (select 1 from public.receipts r where r.id = receipt_id and r.user_id = (select auth.uid())))
  with check (exists (select 1 from public.receipts r where r.id = receipt_id and r.user_id = (select auth.uid())));
drop policy if exists "shopping own rows" on public.shopping_items;
create policy "shopping own rows" on public.shopping_items for all to authenticated
  using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
drop policy if exists "recommendations own rows" on public.accepted_recommendations;
create policy "recommendations own rows" on public.accepted_recommendations for all to authenticated
  using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
drop policy if exists "linked account read own" on public.linked_accounts;
create policy "linked account read own" on public.linked_accounts for select to authenticated
  using ((select auth.uid()) = user_id);
drop policy if exists "transactions read own" on public.transactions;
create policy "transactions read own" on public.transactions for select to authenticated
  using ((select auth.uid()) = user_id);

revoke all on public.profiles, public.receipts, public.receipt_items, public.shopping_items,
  public.accepted_recommendations, public.linked_accounts, public.transactions from public, anon, authenticated;
grant select, insert, update, delete on public.profiles, public.receipts, public.receipt_items,
  public.shopping_items, public.accepted_recommendations to authenticated;
-- Bank data is written only by the backend (service role); users may read their own.
grant select on public.linked_accounts, public.transactions to authenticated;
grant all on public.profiles, public.receipts, public.receipt_items, public.shopping_items,
  public.accepted_recommendations, public.linked_accounts, public.transactions to service_role;

create or replace function public.handle_new_user() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  insert into public.profiles (id, display_name) values (new.id, new.raw_user_meta_data ->> 'display_name')
  on conflict (id) do nothing;
  return new;
end;
$$;
revoke all on function public.handle_new_user() from public, anon, authenticated;
drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created after insert on auth.users for each row execute function public.handle_new_user();

-- Creates a receipt, or replaces an owned receipt's details and lines, in one
-- transaction. Runs as the caller, so row level security still applies.
-- Subtotal is the sum of item lines. A scanned receipt may provide its own
-- authoritative total; otherwise total defaults to subtotal plus tax.
create or replace function public.save_receipt(p_receipt jsonb) returns uuid
language plpgsql security invoker set search_path = '' as $$
declare
  v_user uuid := auth.uid();
  v_id uuid := nullif(p_receipt ->> 'id', '')::uuid;
  v_tax numeric := coalesce(nullif(p_receipt ->> 'tax', '')::numeric, 0);
  v_subtotal numeric;
  v_total numeric;
begin
  if v_user is null then
    raise exception 'Sign in to save receipts.' using errcode = '42501';
  end if;
  if jsonb_typeof(p_receipt -> 'items') is distinct from 'array' then
    raise exception 'A receipt needs an items list.' using errcode = '22023';
  end if;
  select coalesce(sum(coalesce(nullif(e ->> 'quantity', '')::numeric, 1) * (e ->> 'price')::numeric), 0)
    into v_subtotal from jsonb_array_elements(p_receipt -> 'items') as e;
  v_total := coalesce(nullif(p_receipt ->> 'total', '')::numeric, v_subtotal + v_tax);

  if v_id is null then
    insert into public.receipts (user_id, merchant, purchased_at, subtotal, tax, total)
    values (v_user, nullif(btrim(p_receipt ->> 'merchant'), ''), nullif(p_receipt ->> 'purchased_at', '')::date,
            v_subtotal, v_tax, v_total)
    returning id into v_id;
  else
    update public.receipts
      set merchant = nullif(btrim(p_receipt ->> 'merchant'), ''), purchased_at = nullif(p_receipt ->> 'purchased_at', '')::date,
          subtotal = v_subtotal, tax = v_tax, total = v_total
      where id = v_id and user_id = v_user;
    if not found then
      raise exception 'Receipt not found.' using errcode = 'P0002';
    end if;
    delete from public.receipt_items where receipt_id = v_id;
  end if;

  insert into public.receipt_items (receipt_id, position, name, quantity, price, category, carbon_kg_co2e)
  select v_id, (ord - 1)::integer, btrim(e ->> 'name'), coalesce(nullif(e ->> 'quantity', '')::numeric, 1),
         (e ->> 'price')::numeric, coalesce(nullif(e ->> 'category', ''), 'Other'), nullif(e ->> 'carbon_kg_co2e', '')::numeric
  from jsonb_array_elements(p_receipt -> 'items') with ordinality as t(e, ord);
  return v_id;
end;
$$;
revoke all on function public.save_receipt(jsonb) from public, anon;
grant execute on function public.save_receipt(jsonb) to authenticated;

-- Lets `python -m scripts.init_db` confirm this schema version is installed.
create or replace function public.ripple_schema_version() returns integer
language sql immutable set search_path = '' as $$ select 3 $$;
revoke all on function public.ripple_schema_version() from public, anon, authenticated;
grant execute on function public.ripple_schema_version() to service_role;

commit;

notify pgrst, 'reload schema';
