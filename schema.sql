-- Run this entire file in the Supabase SQL Editor. It does not delete data.
-- The public.users table is Ripple's application table, separate from auth.users.
BEGIN;

CREATE TABLE IF NOT EXISTS public.users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username TEXT NOT NULL UNIQUE CHECK (length(btrim(username)) BETWEEN 1 AND 100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    nessie_customer_id TEXT,
    nessie_account_id TEXT,
    CHECK ((nessie_customer_id IS NULL) = (nessie_account_id IS NULL))
);
CREATE TABLE IF NOT EXISTS public.receipts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id),
    merchant TEXT,
    purchase_date DATE,
    subtotal NUMERIC CHECK (subtotal >= 0 AND subtotal < 'Infinity'::numeric),
    tax NUMERIC CHECK (tax >= 0 AND tax < 'Infinity'::numeric),
    total NUMERIC NOT NULL CHECK (total >= 0 AND total < 'Infinity'::numeric),
    raw_json JSONB NOT NULL CHECK (jsonb_typeof(raw_json) = 'object'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS public.receipt_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    receipt_id UUID NOT NULL REFERENCES public.receipts(id) ON DELETE CASCADE,
    raw_name TEXT NOT NULL CHECK (length(btrim(raw_name)) > 0),
    expanded_name TEXT NOT NULL CHECK (length(btrim(expanded_name)) > 0),
    category TEXT NOT NULL CHECK (category IN (
        'groceries', 'produce', 'dairy', 'meat_seafood', 'bakery', 'beverages',
        'snacks', 'household', 'personal_care', 'health', 'electronics',
        'clothing', 'restaurant', 'entertainment', 'transportation', 'other'
    )),
    quantity NUMERIC NOT NULL CHECK (quantity > 0 AND quantity < 'Infinity'::numeric),
    unit_price NUMERIC CHECK (unit_price >= 0 AND unit_price < 'Infinity'::numeric),
    total_price NUMERIC NOT NULL CHECK (total_price >= 0 AND total_price < 'Infinity'::numeric),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    purchased_at TIMESTAMPTZ NOT NULL,
    position INTEGER NOT NULL CHECK (position >= 0),
    UNIQUE (receipt_id, position)
);
CREATE INDEX IF NOT EXISTS receipts_user_history_idx
    ON public.receipts (user_id, purchase_date DESC NULLS LAST, created_at DESC);
CREATE INDEX IF NOT EXISTS receipt_items_purchase_date_idx ON public.receipt_items (purchased_at DESC);
CREATE INDEX IF NOT EXISTS receipt_items_category_date_idx ON public.receipt_items (category, purchased_at DESC);

ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.receipts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.receipt_items ENABLE ROW LEVEL SECURITY;
-- No client-facing policies: all data access goes through the backend secret.
REVOKE ALL ON public.users, public.receipts, public.receipt_items FROM PUBLIC, anon, authenticated;
GRANT USAGE ON SCHEMA public TO service_role;
GRANT SELECT, INSERT, UPDATE ON public.users, public.receipts, public.receipt_items TO service_role;

-- Internal serialization functions are not exposed through the Data API.
CREATE SCHEMA IF NOT EXISTS ripple_private;
REVOKE ALL ON SCHEMA ripple_private FROM PUBLIC, anon, authenticated;
GRANT USAGE ON SCHEMA ripple_private TO service_role;

CREATE OR REPLACE FUNCTION ripple_private.owner_id(p_user_id UUID)
RETURNS UUID LANGUAGE SQL STABLE SECURITY INVOKER SET search_path = '' AS $$
    SELECT COALESCE(p_user_id, (SELECT id FROM public.users WHERE username = 'ripple-demo'));
$$;
CREATE OR REPLACE FUNCTION ripple_private.item_json(i public.receipt_items)
RETURNS JSONB LANGUAGE SQL STABLE SECURITY INVOKER SET search_path = '' SET timezone = 'UTC' AS $$
    SELECT jsonb_build_object(
        'id', i.id, 'receipt_id', i.receipt_id, 'raw_name', i.raw_name,
        'full_name', i.expanded_name, 'category', i.category,
        'quantity', i.quantity::text, 'unit_price', i.unit_price::text,
        'total_price', i.total_price::text, 'purchased_at', i.purchased_at,
        'created_at', i.created_at
    );
$$;
CREATE OR REPLACE FUNCTION ripple_private.receipt_json(r public.receipts)
RETURNS JSONB LANGUAGE SQL STABLE SECURITY INVOKER SET search_path = '' SET timezone = 'UTC' AS $$
    SELECT jsonb_build_object(
        'id', r.id, 'store_name', r.merchant, 'purchase_date', r.purchase_date,
        'subtotal', r.subtotal::text, 'tax', r.tax::text, 'total', r.total::text,
        'raw_json', r.raw_json, 'created_at', r.created_at,
        'warnings', COALESCE(r.raw_json->'warnings', '[]'::jsonb),
        'items', (SELECT COALESCE(jsonb_agg(ripple_private.item_json(i) ORDER BY i.position), '[]'::jsonb)
                  FROM public.receipt_items i WHERE i.receipt_id = r.id)
    );
$$;

CREATE OR REPLACE FUNCTION public.ripple_get_or_create_user(p_username TEXT)
RETURNS JSONB LANGUAGE plpgsql SECURITY INVOKER SET search_path = '' SET timezone = 'UTC' AS $$
DECLARE v_user public.users;
BEGIN
    INSERT INTO public.users (id, username) VALUES (gen_random_uuid(), btrim(p_username))
    ON CONFLICT (username) DO UPDATE SET username = EXCLUDED.username
    RETURNING * INTO v_user;
    RETURN jsonb_build_object('id', v_user.id, 'username', v_user.username, 'created_at', v_user.created_at);
END;
$$;
CREATE OR REPLACE FUNCTION public.ripple_get_user(p_user_id UUID)
RETURNS JSONB LANGUAGE SQL STABLE SECURITY INVOKER SET search_path = '' SET timezone = 'UTC' AS $$
    SELECT jsonb_build_object('id', id, 'username', username, 'created_at', created_at)
    FROM public.users WHERE id = p_user_id;
$$;

-- One RPC = one PostgreSQL transaction. There are no exception handlers that
-- swallow insert errors: a failed line rolls back the owner, receipt, and items.
CREATE OR REPLACE FUNCTION public.ripple_save_receipt(
    p_receipt JSONB, p_user_id UUID DEFAULT NULL, p_fallback_date DATE DEFAULT NULL
)
RETURNS JSONB LANGUAGE plpgsql SECURITY INVOKER SET search_path = '' SET timezone = 'UTC' AS $$
DECLARE
    v_owner UUID := p_user_id;
    v_receipt public.receipts;
    v_line JSONB;
    v_position BIGINT;
    v_now TIMESTAMPTZ := statement_timestamp();
    v_purchase_date DATE := (p_receipt->>'purchase_date')::date;
    v_purchased_at TIMESTAMPTZ;
BEGIN
    IF jsonb_typeof(p_receipt) IS DISTINCT FROM 'object'
       OR jsonb_typeof(p_receipt->'items') IS DISTINCT FROM 'array' THEN
        RAISE EXCEPTION USING ERRCODE = '22023', MESSAGE = 'Invalid receipt document';
    END IF;
    IF v_owner IS NULL THEN
        v_owner := (public.ripple_get_or_create_user('ripple-demo')->>'id')::uuid;
    END IF;
    v_purchased_at := COALESCE(v_purchase_date, p_fallback_date, CURRENT_DATE)::timestamp AT TIME ZONE 'UTC';
    INSERT INTO public.receipts
        (id, user_id, merchant, purchase_date, subtotal, tax, total, raw_json, created_at)
    VALUES
        (gen_random_uuid(), v_owner, p_receipt->>'store_name', v_purchase_date,
         (p_receipt->>'subtotal')::numeric, (p_receipt->>'tax')::numeric,
         (p_receipt->>'total')::numeric, p_receipt, v_now)
    RETURNING * INTO v_receipt;
    FOR v_line, v_position IN SELECT value, ordinality - 1
        FROM jsonb_array_elements(p_receipt->'items') WITH ORDINALITY
    LOOP
        INSERT INTO public.receipt_items
            (id, receipt_id, raw_name, expanded_name, category, quantity,
             unit_price, total_price, created_at, purchased_at, position)
        VALUES
            (gen_random_uuid(), v_receipt.id, v_line->>'raw_name', v_line->>'full_name',
             v_line->>'category', (v_line->>'quantity')::numeric,
             (v_line->>'unit_price')::numeric, (v_line->>'total_price')::numeric,
             v_now, v_purchased_at, v_position);
    END LOOP;
    RETURN ripple_private.receipt_json(v_receipt);
END;
$$;

CREATE OR REPLACE FUNCTION public.ripple_receipts(p_user_id UUID DEFAULT NULL, p_receipt_id UUID DEFAULT NULL)
RETURNS JSONB LANGUAGE SQL STABLE SECURITY INVOKER SET search_path = '' SET timezone = 'UTC' AS $$
    SELECT COALESCE(jsonb_agg(ripple_private.receipt_json(r)
                             ORDER BY r.purchase_date DESC NULLS LAST, r.created_at DESC, r.id), '[]'::jsonb)
    FROM public.receipts r WHERE r.user_id = ripple_private.owner_id(p_user_id)
    AND (p_receipt_id IS NULL OR r.id = p_receipt_id);
$$;
CREATE OR REPLACE FUNCTION public.ripple_items(
    p_category TEXT DEFAULT NULL, p_start DATE DEFAULT NULL, p_end DATE DEFAULT NULL, p_user_id UUID DEFAULT NULL
)
RETURNS JSONB LANGUAGE SQL STABLE SECURITY INVOKER SET search_path = '' SET timezone = 'UTC' AS $$
    SELECT COALESCE(jsonb_agg(ripple_private.item_json(i)
        ORDER BY i.purchased_at DESC, i.created_at DESC, i.position, i.id), '[]'::jsonb)
    FROM public.receipt_items i JOIN public.receipts r ON r.id = i.receipt_id
    WHERE r.user_id = ripple_private.owner_id(p_user_id)
    AND (p_category IS NULL OR i.category = p_category)
    AND (p_start IS NULL OR i.purchased_at >= p_start::timestamp AT TIME ZONE 'UTC')
    AND (p_end IS NULL OR (i.purchased_at AT TIME ZONE 'UTC')::date <= p_end);
$$;
CREATE OR REPLACE FUNCTION public.ripple_spending_summary(p_period TEXT, p_user_id UUID DEFAULT NULL)
RETURNS JSONB LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path = '' SET timezone = 'UTC' AS $$
DECLARE
    v_owner UUID := ripple_private.owner_id(p_user_id);
    v_cutoff TIMESTAMPTZ;
BEGIN
    IF p_period IS NULL OR p_period NOT IN ('week', 'month', 'all') THEN
        RAISE EXCEPTION USING ERRCODE = '22023', MESSAGE = 'Invalid spending period';
    END IF;
    v_cutoff := CASE p_period WHEN 'week' THEN CURRENT_TIMESTAMP - INTERVAL '7 days'
                             WHEN 'month' THEN CURRENT_TIMESTAMP - INTERVAL '30 days' ELSE NULL END;
    RETURN jsonb_build_object(
        'period', p_period,
        'by_category', (SELECT COALESCE(jsonb_agg(to_jsonb(t) ORDER BY t.category), '[]'::jsonb)
            FROM (SELECT i.category, SUM(i.total_price)::text AS total
                  FROM public.receipt_items i JOIN public.receipts r ON r.id = i.receipt_id
                  WHERE r.user_id = v_owner AND (v_cutoff IS NULL OR i.purchased_at >= v_cutoff)
                  GROUP BY i.category) t),
        'by_day', (SELECT COALESCE(jsonb_agg(to_jsonb(t) ORDER BY t.day), '[]'::jsonb)
            FROM (SELECT (i.purchased_at AT TIME ZONE 'UTC')::date AS day, SUM(i.total_price)::text AS total
                  FROM public.receipt_items i JOIN public.receipts r ON r.id = i.receipt_id
                  WHERE r.user_id = v_owner AND (v_cutoff IS NULL OR i.purchased_at >= v_cutoff)
                  GROUP BY (i.purchased_at AT TIME ZONE 'UTC')::date) t)
    );
END;
$$;
CREATE OR REPLACE FUNCTION public.ripple_demo_ids(p_customer_id TEXT DEFAULT NULL, p_account_id TEXT DEFAULT NULL)
RETURNS JSONB LANGUAGE plpgsql SECURITY INVOKER SET search_path = '' AS $$
DECLARE v_user public.users; v_id UUID;
BEGIN
    IF p_customer_id IS NOT NULL OR p_account_id IS NOT NULL THEN
        IF p_customer_id IS NULL OR p_account_id IS NULL
           OR btrim(p_customer_id) = '' OR btrim(p_account_id) = '' THEN
            RAISE EXCEPTION USING ERRCODE = '22023', MESSAGE = 'Both demo IDs are required';
        END IF;
        v_id := (public.ripple_get_or_create_user('ripple-demo')->>'id')::uuid;
        UPDATE public.users SET nessie_customer_id = p_customer_id, nessie_account_id = p_account_id WHERE id = v_id;
    END IF;
    SELECT * INTO v_user FROM public.users WHERE username = 'ripple-demo';
    IF v_user.nessie_customer_id IS NULL THEN RETURN NULL; END IF;
    RETURN jsonb_build_object('customer_id', v_user.nessie_customer_id, 'account_id', v_user.nessie_account_id);
END;
$$;
CREATE OR REPLACE FUNCTION public.ripple_check()
RETURNS JSONB LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path = '' AS $$
BEGIN
    PERFORM id FROM public.users LIMIT 1;
    PERFORM id FROM public.receipts LIMIT 1;
    PERFORM id FROM public.receipt_items LIMIT 1;
    RETURN jsonb_build_object('status', 'ok', 'schema_version', 1);
END;
$$;

-- Scope grants to Ripple's objects; do not change other applications' defaults.
REVOKE ALL ON FUNCTION ripple_private.owner_id(UUID), ripple_private.item_json(public.receipt_items),
    ripple_private.receipt_json(public.receipts) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION ripple_private.owner_id(UUID), ripple_private.item_json(public.receipt_items),
    ripple_private.receipt_json(public.receipts) TO service_role;
REVOKE ALL ON FUNCTION public.ripple_get_or_create_user(TEXT), public.ripple_get_user(UUID),
    public.ripple_save_receipt(JSONB, UUID, DATE), public.ripple_receipts(UUID, UUID),
    public.ripple_items(TEXT, DATE, DATE, UUID), public.ripple_spending_summary(TEXT, UUID),
    public.ripple_demo_ids(TEXT, TEXT), public.ripple_check() FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.ripple_get_or_create_user(TEXT), public.ripple_get_user(UUID),
    public.ripple_save_receipt(JSONB, UUID, DATE), public.ripple_receipts(UUID, UUID),
    public.ripple_items(TEXT, DATE, DATE, UUID), public.ripple_spending_summary(TEXT, UUID),
    public.ripple_demo_ids(TEXT, TEXT), public.ripple_check() TO service_role;
NOTIFY pgrst, 'reload schema';
COMMIT;
