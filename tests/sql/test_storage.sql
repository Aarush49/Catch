-- Optional SQL Editor regression checks AFTER schema.sql. All test writes roll back.
BEGIN;
DO $$
DECLARE
    v_user UUID;
    v_other UUID;
    v_name TEXT := 'sql-test-' || gen_random_uuid()::text;
    v_saved JSONB;
    v_read JSONB;
    v_document JSONB := '{
        "store_name":"SQL Test", "purchase_date":"2026-10-24",
        "subtotal":"0.30", "tax":null, "total":"0.30",
        "items":[
            {"raw_name":"A","full_name":"Apple","category":"produce","quantity":"1","unit_price":"0.10","total_price":"0.10"},
            {"raw_name":"B","full_name":"Banana","category":"produce","quantity":"1","unit_price":"0.20","total_price":"0.20"}
        ], "warnings":["SQL test"]
    }'::jsonb;
    v_count BIGINT;
    v_line_count BIGINT;
    v_role TEXT;
    v_function RECORD;
BEGIN
    v_user := (public.ripple_get_or_create_user(v_name)->>'id')::uuid;
    ASSERT (public.ripple_get_or_create_user(v_name)->>'id')::uuid = v_user, 'User creation must be idempotent';
    ASSERT (public.ripple_get_user(v_user)->>'username') = v_name;
    ASSERT public.ripple_get_user(gen_random_uuid()) IS NULL;
    v_other := (public.ripple_get_or_create_user(v_name || '-other')->>'id')::uuid;
    v_saved := public.ripple_save_receipt(v_document, v_user);
    ASSERT jsonb_array_length(v_saved->'items') = 2, 'Atomic save must return both lines';
    ASSERT v_saved->'items'->0->>'raw_name' = 'A';
    ASSERT v_saved->'items'->1->>'raw_name' = 'B';
    ASSERT jsonb_typeof(v_saved->'total') = 'string', 'Never send money as JSON floats';
    ASSERT v_saved->'warnings' = '["SQL test"]'::jsonb;
    v_read := public.ripple_receipts(v_user, (v_saved->>'id')::uuid);
    ASSERT v_read->0 = v_saved, 'Receipt round trip must preserve response';
    ASSERT public.ripple_receipts(v_other, (v_saved->>'id')::uuid) = '[]'::jsonb;
    ASSERT public.ripple_items(NULL, NULL, NULL, v_other) = '[]'::jsonb;
    ASSERT jsonb_array_length(public.ripple_items('produce', '2026-10-24', '2026-10-24', v_user)) = 2;
    ASSERT public.ripple_items('other', NULL, NULL, v_user) = '[]'::jsonb;
    ASSERT (public.ripple_spending_summary('all', v_user)->'by_category'->0->>'total')::numeric = 0.30;

    SELECT count(*) INTO v_count FROM public.receipts WHERE user_id = v_user;
    SELECT count(*) INTO v_line_count FROM public.receipt_items i JOIN public.receipts r ON r.id = i.receipt_id WHERE r.user_id = v_user;
    BEGIN
        PERFORM public.ripple_save_receipt(jsonb_set(v_document, '{items,1,total_price}', '"-1"'::jsonb), v_user);
        RAISE EXCEPTION 'Expected a second-item check violation';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
    ASSERT (SELECT count(*) FROM public.receipts WHERE user_id = v_user) = v_count, 'Failed second line left a receipt';
    ASSERT (SELECT count(*) FROM public.receipt_items i JOIN public.receipts r ON r.id = i.receipt_id WHERE r.user_id = v_user) = v_line_count,
        'Failed second line left items';
    BEGIN
        PERFORM public.ripple_save_receipt(v_document, gen_random_uuid());
        RAISE EXCEPTION 'Expected an owner foreign-key violation';
    EXCEPTION WHEN foreign_key_violation THEN NULL;
    END;

    v_document := jsonb_set(v_document, '{total}', '"12345678901234567890.123456789"'::jsonb);
    v_saved := public.ripple_save_receipt(v_document, v_user);
    ASSERT v_saved->>'total' = '12345678901234567890.123456789', 'Numeric precision was lost';
    ASSERT (public.ripple_receipts(v_user, (v_saved->>'id')::uuid)->0->>'total') = v_saved->>'total';

    v_saved := public.ripple_save_receipt(
        '{"store_name":null,"purchase_date":null,"subtotal":null,"tax":null,"total":"0","items":[],"warnings":[]}'::jsonb,
        v_user, '2026-10-20'
    );
    ASSERT v_saved->'purchase_date' = 'null'::jsonb AND v_saved->'subtotal' = 'null'::jsonb;
    ASSERT v_saved->'items' = '[]'::jsonb;
    v_document := jsonb_set(v_document, '{purchase_date}', 'null'::jsonb);
    v_saved := public.ripple_save_receipt(v_document, v_user, '2026-10-20');
    ASSERT (v_saved->'items'->0->>'purchased_at')::timestamptz = '2026-10-20 00:00:00+00';

    PERFORM public.ripple_demo_ids('test-customer', 'test-account');
    ASSERT public.ripple_demo_ids() = '{"customer_id":"test-customer","account_id":"test-account"}'::jsonb;
    ASSERT public.ripple_check()->>'status' = 'ok';

    FOREACH v_role IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        ASSERT NOT has_table_privilege(v_role, 'public.users', 'SELECT');
        ASSERT NOT has_table_privilege(v_role, 'public.receipts', 'SELECT');
        ASSERT NOT has_table_privilege(v_role, 'public.receipt_items', 'SELECT');
        ASSERT NOT has_schema_privilege(v_role, 'ripple_private', 'USAGE');
        FOR v_function IN SELECT p.oid FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
                          WHERE n.nspname = 'public' AND p.proname LIKE 'ripple_%' LOOP
            ASSERT NOT has_function_privilege(v_role, v_function.oid, 'EXECUTE'), 'Client role can execute a backend RPC';
            ASSERT has_function_privilege('service_role', v_function.oid, 'EXECUTE'), 'Backend RPC is not granted';
        END LOOP;
    END LOOP;
    ASSERT (SELECT bool_and(relrowsecurity) FROM pg_class WHERE oid IN ('public.users'::regclass, 'public.receipts'::regclass, 'public.receipt_items'::regclass)),
        'RLS must be enabled on all tables';
    ASSERT NOT EXISTS (SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
                      WHERE n.nspname IN ('public', 'ripple_private') AND p.proname LIKE 'ripple_%' AND p.prosecdef),
        'Ripple RPCs must use invoker privileges';
END;
$$;
ROLLBACK;
