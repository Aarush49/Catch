create extension if not exists pgcrypto;

create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  display_name text,
  created_at timestamptz not null default now()
);
create table if not exists public.receipts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  merchant text,
  purchased_at date,
  subtotal numeric not null default 0 check (subtotal >= 0),
  tax numeric not null default 0 check (tax >= 0),
  total numeric not null default 0 check (total >= 0),
  image_path text,
  created_at timestamptz not null default now()
);
create table if not exists public.receipt_items (
  id uuid primary key default gen_random_uuid(),
  receipt_id uuid not null references public.receipts(id) on delete cascade,
  name text not null,
  quantity numeric not null default 1 check (quantity > 0),
  price numeric not null check (price >= 0),
  category text not null default 'Other' check (category in ('Groceries','Dining','Household','Health','Transport','Other'))
);
create table if not exists public.shopping_items (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  name text not null,
  completed boolean not null default false,
  created_at timestamptz not null default now()
);
create table if not exists public.accepted_recommendations (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  original_name text not null,
  replacement_name text not null,
  savings numeric not null default 0,
  created_at timestamptz not null default now()
);

alter table public.profiles enable row level security;
alter table public.receipts enable row level security;
alter table public.receipt_items enable row level security;
alter table public.shopping_items enable row level security;
alter table public.accepted_recommendations enable row level security;

create policy "profiles own row" on public.profiles for all using (auth.uid() = id) with check (auth.uid() = id);
create policy "receipts own rows" on public.receipts for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "receipt items through owned receipt" on public.receipt_items for all
  using (exists (select 1 from public.receipts r where r.id = receipt_id and r.user_id = auth.uid()))
  with check (exists (select 1 from public.receipts r where r.id = receipt_id and r.user_id = auth.uid()));
create policy "shopping own rows" on public.shopping_items for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "recommendations own rows" on public.accepted_recommendations for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

create or replace function public.handle_new_user() returns trigger language plpgsql security definer set search_path = '' as $$
begin
  insert into public.profiles (id, display_name) values (new.id, new.raw_user_meta_data ->> 'display_name');
  return new;
end;
$$;
drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created after insert on auth.users for each row execute function public.handle_new_user();
