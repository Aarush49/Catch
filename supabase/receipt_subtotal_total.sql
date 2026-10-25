-- Run this once in the Supabase SQL Editor to make scanned receipt totals
-- use the OCR subtotal without adding tax. Manual receipts still default to
-- subtotal + tax when no explicit total is supplied.
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
