-- After schema.sql: exercise the seven-table API schema. No test data persists.
BEGIN;
DO $$
DECLARE
    v_email TEXT := 'sql-account-' || gen_random_uuid()::text || '@example.com';
    v_a UUID; v_b UUID; v_shopping UUID; v_other_item UUID;
    v_token TEXT := replace(gen_random_uuid()::text, '-', '') || replace(gen_random_uuid()::text, '-', '');
    v_expired TEXT := replace(gen_random_uuid()::text, '-', '') || replace(gen_random_uuid()::text, '-', '');
    v_rows JSONB;
    v_result JSONB;
    v_receipt JSONB;
    v_transaction UUID;
    v_role TEXT;
    v_table TEXT;
    v_function RECORD;
BEGIN
    v_a := (public.ripple_create_account(v_email, repeat('01', 16), repeat('ab', 32))->>'id')::uuid;
    v_b := (public.ripple_create_account('other-' || v_email, repeat('02', 16), repeat('cd', 32))->>'id')::uuid;
    ASSERT public.ripple_auth_record(upper(v_email))->>'id' = v_a::text;
    ASSERT public.ripple_auth_record(v_email)->>'password_hash' = repeat('ab', 32);
    BEGIN
        PERFORM public.ripple_create_account(upper(v_email), repeat('01', 16), repeat('ab', 32));
        RAISE EXCEPTION 'Expected duplicate-email rejection';
    EXCEPTION WHEN unique_violation THEN NULL;
    END;

    PERFORM public.ripple_create_session(v_a, v_token, CURRENT_TIMESTAMP + INTERVAL '1 day');
    ASSERT public.ripple_session_user(v_token) = jsonb_build_object('id', v_a, 'email', v_email);
    PERFORM public.ripple_create_session(v_b, v_expired, CURRENT_TIMESTAMP - INTERVAL '1 day');
    ASSERT public.ripple_session_user(v_expired) IS NULL;
    PERFORM public.ripple_delete_session(v_token);
    ASSERT public.ripple_session_user(v_token) IS NULL;

    PERFORM public.ripple_save_link(v_a, 'customer-a', 'account-a');
    ASSERT public.ripple_get_link(v_a)->>'account_id' = 'account-a';
    ASSERT public.ripple_get_link(v_b) IS NULL;
    PERFORM public.ripple_save_link(v_a, 'customer-a', 'account-a2');
    ASSERT public.ripple_get_link(v_a)->>'account_id' = 'account-a2';
    ASSERT (SELECT count(*) FROM public.linked_accounts WHERE user_id = v_a) = 1;

    v_rows := '[
        {"id":"purchase-1","source":"nessie","type":"purchase","amount":"0.10","date":"2026-10-24","description":"Coffee","category":"restaurant","raw":{"demo":true}},
        {"id":"salary-1","source":"nessie","type":"income","amount":"12345678901234567890.123456789","date":"2026-10-23","description":"Salary","category":"salary","raw":{}}
    ]'::jsonb;
    ASSERT public.ripple_upsert_transactions(v_a, v_rows)->>'count' = '2';
    SELECT id INTO v_transaction FROM public.transactions WHERE user_id = v_a AND external_id = 'purchase-1';
    v_rows := jsonb_set(v_rows, '{0,amount}', '"0.20"'::jsonb);
    PERFORM public.ripple_upsert_transactions(v_a, v_rows);
    ASSERT (SELECT id FROM public.transactions WHERE user_id = v_a AND external_id = 'purchase-1') = v_transaction;
    ASSERT (SELECT count(*) FROM public.transactions WHERE user_id = v_a) = 2;
    ASSERT (public.ripple_transactions(v_a)->0->>'amount')::numeric = 0.20;
    ASSERT public.ripple_transactions(v_a)->1->>'amount' = '12345678901234567890.123456789';
    ASSERT public.ripple_transactions(v_b) = '[]'::jsonb;
    PERFORM public.ripple_upsert_transactions(v_b, v_rows);
    ASSERT jsonb_array_length(public.ripple_transactions(v_b)) = 2;
    BEGIN
        PERFORM public.ripple_upsert_transactions(v_a,
            jsonb_set(jsonb_set(v_rows, '{0,amount}', '"9.99"'), '{1,amount}', '"NaN"'));
        RAISE EXCEPTION 'Expected an invalid transaction amount';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
    ASSERT (public.ripple_transactions(v_a)->0->>'amount')::numeric = 0.20, 'Transaction batch was partially saved';

    v_receipt := public.ripple_save_receipt('{
        "store_name":"Hardware","purchase_date":"2026-10-24","subtotal":null,"tax":null,"total":"10.00","warnings":[],
        "items":[{"raw_name":"Bulb","full_name":"Bulb","category":"utilities","quantity":"1","unit_price":"10.00","total_price":"10.00","carbon_kg_co2e":"2.345"}]
    }'::jsonb, v_a);
    ASSERT v_receipt->'items'->0->>'carbon_kg_co2e' = '2.345';
    ASSERT public.ripple_receipts(v_a, (v_receipt->>'id')::uuid)->0 = v_receipt;
    ASSERT public.ripple_receipts(v_b, (v_receipt->>'id')::uuid) = '[]'::jsonb;

    v_result := public.ripple_add_shopping_item(v_a, '{"name":"Shoes","price":"80.10","brand":null,"category":"clothing","allow_lower_quality":true}');
    v_shopping := (v_result->>'id')::uuid;
    ASSERT (v_result->>'allow_lower_quality')::boolean;
    ASSERT v_result->>'price' = '80.10';
    v_other_item := (public.ripple_add_shopping_item(v_b, '{"name":"Other","price":"1","category":"other"}')->>'id')::uuid;
    ASSERT jsonb_array_length(public.ripple_shopping_items(v_a)) = 1;
    ASSERT NOT (public.ripple_delete_shopping_item(v_b, v_shopping)->>'deleted')::boolean;
    ASSERT (public.ripple_delete_shopping_item(v_a, v_shopping)->>'deleted')::boolean;
    ASSERT public.ripple_shopping_items(v_a) = '[]'::jsonb;
    ASSERT (public.ripple_shopping_items(v_b)->0->>'id')::uuid = v_other_item;

    ASSERT public.ripple_check()->>'schema_version' = '2';
    FOREACH v_role IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        FOREACH v_table IN ARRAY ARRAY['users', 'sessions', 'linked_accounts', 'transactions', 'receipts', 'receipt_items', 'shopping_items'] LOOP
            ASSERT NOT has_table_privilege(v_role, 'public.' || v_table, 'SELECT'), 'Client role can read a backend table';
            ASSERT (SELECT relrowsecurity FROM pg_class WHERE oid = ('public.' || v_table)::regclass), 'Table is missing RLS';
        END LOOP;
        FOR v_function IN SELECT p.oid FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
                          WHERE n.nspname = 'public' AND p.proname LIKE 'ripple_%' LOOP
            ASSERT NOT has_function_privilege(v_role, v_function.oid, 'EXECUTE'), 'Client role can execute a backend RPC';
            ASSERT has_function_privilege('service_role', v_function.oid, 'EXECUTE'), 'Backend role cannot execute an RPC';
        END LOOP;
    END LOOP;
END;
$$;
ROLLBACK;
