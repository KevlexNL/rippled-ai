-- Run manually in Supabase SQL editor
-- Seeds 5 mock contexts for Kevin's user and assigns context_id to relevant commitments.
-- Replace <OWNER_USER_ID> with Kevin's actual user UUID before running.

DO $$
DECLARE
    v_user_id UUID;
    v_ctx_acme UUID;
    v_ctx_vertex UUID;
    v_ctx_marketing UUID;
    v_ctx_allhands UUID;
    v_ctx_finance UUID;
BEGIN
    -- Look up Kevin's user ID (adjust email if needed)
    SELECT id INTO v_user_id FROM users WHERE email = 'kevin@kevlex.digital' LIMIT 1;

    IF v_user_id IS NULL THEN
        RAISE NOTICE 'User not found — skipping seed';
        RETURN;
    END IF;

    -- Insert mock contexts (idempotent: skip if name already exists for user)
    INSERT INTO commitment_contexts (id, user_id, name, summary)
    VALUES (gen_random_uuid(), v_user_id, 'Acme onboarding', 'Client onboarding workstream for Acme Corp')
    ON CONFLICT DO NOTHING
    RETURNING id INTO v_ctx_acme;

    IF v_ctx_acme IS NULL THEN
        SELECT id INTO v_ctx_acme FROM commitment_contexts WHERE user_id = v_user_id AND name = 'Acme onboarding';
    END IF;

    INSERT INTO commitment_contexts (id, user_id, name, summary)
    VALUES (gen_random_uuid(), v_user_id, 'Vertex legal / NDA', 'Legal and NDA review cycle with Vertex Partners')
    ON CONFLICT DO NOTHING
    RETURNING id INTO v_ctx_vertex;

    IF v_ctx_vertex IS NULL THEN
        SELECT id INTO v_ctx_vertex FROM commitment_contexts WHERE user_id = v_user_id AND name = 'Vertex legal / NDA';
    END IF;

    INSERT INTO commitment_contexts (id, user_id, name, summary)
    VALUES (gen_random_uuid(), v_user_id, 'Marketing team deliverables', 'Design and content deliverables for the marketing team')
    ON CONFLICT DO NOTHING
    RETURNING id INTO v_ctx_marketing;

    IF v_ctx_marketing IS NULL THEN
        SELECT id INTO v_ctx_marketing FROM commitment_contexts WHERE user_id = v_user_id AND name = 'Marketing team deliverables';
    END IF;

    INSERT INTO commitment_contexts (id, user_id, name, summary)
    VALUES (gen_random_uuid(), v_user_id, 'Company all-hands prep', 'Preparation for the upcoming company all-hands meeting')
    ON CONFLICT DO NOTHING
    RETURNING id INTO v_ctx_allhands;

    IF v_ctx_allhands IS NULL THEN
        SELECT id INTO v_ctx_allhands FROM commitment_contexts WHERE user_id = v_user_id AND name = 'Company all-hands prep';
    END IF;

    INSERT INTO commitment_contexts (id, user_id, name, summary)
    VALUES (gen_random_uuid(), v_user_id, 'Q1 finance review', 'Quarterly finance review and budget alignment')
    ON CONFLICT DO NOTHING
    RETURNING id INTO v_ctx_finance;

    IF v_ctx_finance IS NULL THEN
        SELECT id INTO v_ctx_finance FROM commitment_contexts WHERE user_id = v_user_id AND name = 'Q1 finance review';
    END IF;

    RAISE NOTICE 'Seeded contexts: acme=%, vertex=%, marketing=%, allhands=%, finance=%',
        v_ctx_acme, v_ctx_vertex, v_ctx_marketing, v_ctx_allhands, v_ctx_finance;
END $$;
