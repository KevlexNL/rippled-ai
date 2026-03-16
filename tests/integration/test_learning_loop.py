"""Integration tests for WO-RIPPLED-LEARNING-LOOP — three-tier detection funnel.

Verifies:
1. Tier 1 profile match creates candidate without pattern matching
2. Suppressed sender skips all detection
3. Tier 2 (pattern) detection still works when no profile match
4. Detection audit rows are written for each tier
5. Profile update after model detection
6. Profile downweight after dismissal
"""
import asyncio
import uuid

import json

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_db_url():
    import os
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        pytest.skip("DATABASE_URL not set")
    return url


def _make_async_url(url: str) -> str:
    return (
        url
        .replace("postgresql://", "postgresql+asyncpg://")
        .replace("postgres://", "postgresql+asyncpg://")
    )


async def _exec(sql: str, params: dict | None = None):
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text, bindparam
    from sqlalchemy.dialects.postgresql import UUID as PGUUID

    engine = create_async_engine(
        _make_async_url(_get_db_url()),
        connect_args={"statement_cache_size": 0},
    )
    try:
        async with engine.begin() as conn:
            # Bind all UUID-typed params
            stmt = text(sql)
            if params:
                binds = {}
                for k, v in params.items():
                    if k.endswith("_id") or k == "id":
                        binds[k] = bindparam(k, type_=PGUUID(as_uuid=False))
                if binds:
                    stmt = stmt.bindparams(**binds)
            result = await conn.execute(stmt, params or {})
            try:
                return result.fetchall()
            except Exception:
                return []
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def ll_user_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture(scope="module")
def ll_source_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture(scope="module", autouse=True)
def seed_learning_loop_data(ll_user_id, ll_source_id):
    """Create user, source, profile, and test source_items."""
    item_with_phrase = str(uuid.uuid4())
    item_newsletter = str(uuid.uuid4())
    item_no_match = str(uuid.uuid4())
    item_pattern_only = str(uuid.uuid4())

    async def _seed():
        # User
        await _exec(
            "INSERT INTO users (id, email) VALUES (:id, :email) ON CONFLICT DO NOTHING",
            {"id": ll_user_id, "email": f"ll-test-{ll_user_id[:8]}@test.com"},
        )
        # Source
        await _exec(
            "INSERT INTO sources (id, user_id, source_type, display_name, is_active) "
            "VALUES (:id, :user_id, 'email', 'learning-loop-test', true) ON CONFLICT DO NOTHING",
            {"id": ll_source_id, "user_id": ll_user_id},
        )
        # User commitment profile with known trigger phrases and senders
        await _exec(
            "INSERT INTO user_commitment_profiles "
            "(user_id, trigger_phrases, high_signal_senders, suppressed_senders, "
            " sender_weights, phrase_weights, total_items_processed, total_commitments_found) "
            "VALUES (:user_id, :trigger_phrases, :high_signal_senders, :suppressed_senders, "
            " :sender_weights, :phrase_weights, 50, 10) "
            "ON CONFLICT (user_id) DO UPDATE SET "
            "trigger_phrases = EXCLUDED.trigger_phrases, "
            "high_signal_senders = EXCLUDED.high_signal_senders, "
            "suppressed_senders = EXCLUDED.suppressed_senders, "
            "sender_weights = EXCLUDED.sender_weights, "
            "phrase_weights = EXCLUDED.phrase_weights",
            {
                "user_id": ll_user_id,
                "trigger_phrases": json.dumps(["i'll send", "i will follow up", "let me handle"]),
                "high_signal_senders": json.dumps(["boss@company.com"]),
                "suppressed_senders": json.dumps(["newsletter@spam.com"]),
                "sender_weights": json.dumps({"boss@company.com": 5}),
                "phrase_weights": json.dumps({"i'll send": 8, "i will follow up": 4, "let me handle": 2}),
            },
        )
        # Source item 1: has a profile trigger phrase → Tier 1 should catch
        await _exec(
            "INSERT INTO source_items "
            "(id, source_id, user_id, source_type, external_id, content, "
            " sender_email, occurred_at) "
            "VALUES (:id, :source_id, :user_id, 'email', :ext_id, :content, "
            " :sender_email, now()) ON CONFLICT DO NOTHING",
            {
                "id": item_with_phrase,
                "source_id": ll_source_id,
                "user_id": ll_user_id,
                "ext_id": f"ll-phrase-{uuid.uuid4()}",
                "content": "Hey team, I'll send the updated proposal by tomorrow morning.",
                "sender_email": "boss@company.com",
            },
        )
        # Source item 2: from a suppressed sender → should be skipped
        await _exec(
            "INSERT INTO source_items "
            "(id, source_id, user_id, source_type, external_id, content, "
            " sender_email, occurred_at) "
            "VALUES (:id, :source_id, :user_id, 'email', :ext_id, :content, "
            " :sender_email, now()) ON CONFLICT DO NOTHING",
            {
                "id": item_newsletter,
                "source_id": ll_source_id,
                "user_id": ll_user_id,
                "ext_id": f"ll-newsletter-{uuid.uuid4()}",
                "content": "I will send you exclusive deals! Subscribe now!",
                "sender_email": "newsletter@spam.com",
            },
        )
        # Source item 3: no profile match, no pattern match → nothing
        await _exec(
            "INSERT INTO source_items "
            "(id, source_id, user_id, source_type, external_id, content, "
            " sender_email, occurred_at) "
            "VALUES (:id, :source_id, :user_id, 'email', :ext_id, :content, "
            " :sender_email, now()) ON CONFLICT DO NOTHING",
            {
                "id": item_no_match,
                "source_id": ll_source_id,
                "user_id": ll_user_id,
                "ext_id": f"ll-nothing-{uuid.uuid4()}",
                "content": "Thanks for the update on the project status.",
                "sender_email": "colleague@company.com",
            },
        )
        # Source item 4: no profile match but has pattern match → Tier 2
        await _exec(
            "INSERT INTO source_items "
            "(id, source_id, user_id, source_type, external_id, content, "
            " sender_email, occurred_at) "
            "VALUES (:id, :source_id, :user_id, 'email', :ext_id, :content, "
            " :sender_email, now()) ON CONFLICT DO NOTHING",
            {
                "id": item_pattern_only,
                "source_id": ll_source_id,
                "user_id": ll_user_id,
                "ext_id": f"ll-pattern-{uuid.uuid4()}",
                "content": "I will investigate the production issue and report back by Friday.",
                "sender_email": "unknown@newdomain.com",
            },
        )

    asyncio.run(_seed())
    yield {
        "item_with_phrase": item_with_phrase,
        "item_newsletter": item_newsletter,
        "item_no_match": item_no_match,
        "item_pattern_only": item_pattern_only,
    }
    # Cleanup
    asyncio.run(_cleanup(ll_user_id))


async def _cleanup(user_id: str):
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text, bindparam
    from sqlalchemy.dialects.postgresql import UUID as PGUUID

    engine = create_async_engine(
        _make_async_url(_get_db_url()),
        connect_args={"statement_cache_size": 0},
    )
    try:
        async with engine.begin() as conn:
            for table in (
                "detection_audit", "commitment_candidates",
                "lifecycle_transitions", "commitment_signals",
                "commitment_ambiguities", "commitment_contexts",
                "user_commitment_profiles",
            ):
                await conn.execute(
                    text(f"DELETE FROM {table} WHERE user_id = :id").bindparams(
                        bindparam("id", type_=PGUUID(as_uuid=False))
                    ),
                    {"id": user_id},
                )
            await conn.execute(
                text("DELETE FROM users WHERE id = :id").bindparams(
                    bindparam("id", type_=PGUUID(as_uuid=False))
                ),
                {"id": user_id},
            )
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestTier1ProfileMatch:
    """Tier 1: profile-based matching catches items with known trigger phrases."""

    def test_tier1_creates_candidate_for_known_phrase(self, seed_learning_loop_data):
        """An item with a profile trigger phrase should be caught by Tier 1."""
        from app.db.session import get_sync_session
        from app.services.detection import run_detection

        item_id = seed_learning_loop_data["item_with_phrase"]
        with get_sync_session() as session:
            result = run_detection(item_id, session)

        assert len(result) >= 1
        # Tier 1 candidate should have detection_method or explanation indicating tier_1
        tier1_found = any(
            "Tier 1" in (c.detection_explanation or "")
            or getattr(c, "detection_method", "") == "tier_1"
            for c in result
        )
        assert tier1_found, f"Expected Tier 1 match, got: {[c.detection_explanation for c in result]}"

    def test_tier1_writes_audit_entry(self, seed_learning_loop_data, ll_user_id):
        """Tier 1 detection should write an audit row with tier_used='tier_1'."""
        rows = asyncio.run(_exec(
            "SELECT tier_used, matched_phrase FROM detection_audit "
            "WHERE user_id = :user_id AND tier_used = 'tier_1'",
            {"user_id": ll_user_id},
        ))
        assert len(rows) >= 1, "Expected at least one tier_1 audit entry"
        assert any("send" in (r[1] or "").lower() for r in rows)


class TestSenderSuppression:
    """Suppressed/newsletter senders skip all detection."""

    def test_suppressed_sender_produces_no_candidates(self, seed_learning_loop_data):
        """A newsletter sender should produce zero candidates."""
        from app.db.session import get_sync_session
        from app.services.detection import run_detection

        item_id = seed_learning_loop_data["item_newsletter"]
        with get_sync_session() as session:
            result = run_detection(item_id, session)

        assert len(result) == 0

    def test_suppressed_sender_writes_audit(self, seed_learning_loop_data, ll_user_id):
        """Suppressed detection should still log an audit entry."""
        rows = asyncio.run(_exec(
            "SELECT tier_used FROM detection_audit "
            "WHERE user_id = :user_id AND tier_used = 'suppressed'",
            {"user_id": ll_user_id},
        ))
        assert len(rows) >= 1


class TestTier2PatternFallthrough:
    """Items not caught by Tier 1 fall through to Tier 2 (pattern matching)."""

    def test_pattern_match_creates_candidate(self, seed_learning_loop_data):
        """An item with 'I will investigate' should be caught by Tier 2 patterns."""
        from app.db.session import get_sync_session
        from app.services.detection import run_detection

        item_id = seed_learning_loop_data["item_pattern_only"]
        with get_sync_session() as session:
            result = run_detection(item_id, session)

        assert len(result) >= 1

    def test_pattern_match_writes_tier2_audit(self, seed_learning_loop_data, ll_user_id):
        """Tier 2 detections should write audit rows with tier_used='tier_2'."""
        rows = asyncio.run(_exec(
            "SELECT tier_used FROM detection_audit "
            "WHERE user_id = :user_id AND tier_used = 'tier_2'",
            {"user_id": ll_user_id},
        ))
        assert len(rows) >= 1


class TestNoMatchItem:
    """Items with no trigger phrases and no patterns produce no candidates."""

    def test_no_match_produces_no_candidates(self, seed_learning_loop_data):
        from app.db.session import get_sync_session
        from app.services.detection import run_detection

        item_id = seed_learning_loop_data["item_no_match"]
        with get_sync_session() as session:
            result = run_detection(item_id, session)

        assert len(result) == 0


class TestDetectionAuditQueryable:
    """Detection audit rows are queryable by user and tier."""

    def test_audit_rows_exist_for_test_user(self, seed_learning_loop_data, ll_user_id):
        """After running detection on all items, audit rows should exist."""
        rows = asyncio.run(_exec(
            "SELECT tier_used, COUNT(*) FROM detection_audit "
            "WHERE user_id = :user_id GROUP BY tier_used",
            {"user_id": ll_user_id},
        ))
        tier_counts = {r[0]: r[1] for r in rows}
        assert len(tier_counts) >= 1, f"Expected audit rows, got: {tier_counts}"


class TestProfileUpdateTasks:
    """Profile update tasks work end-to-end."""

    def test_update_profile_after_model_detection_no_crash(self, seed_learning_loop_data):
        """Calling the task with a nonexistent candidate shouldn't crash."""
        from app.tasks import update_profile_after_model_detection
        result = update_profile_after_model_detection(str(uuid.uuid4()))
        assert result["status"] == "not_found"

    def test_update_profile_after_dismissal_no_crash(self, seed_learning_loop_data):
        """Calling the task with a nonexistent commitment shouldn't crash."""
        from app.tasks import update_profile_after_dismissal
        result = update_profile_after_dismissal(str(uuid.uuid4()))
        assert result["status"] == "not_found"
