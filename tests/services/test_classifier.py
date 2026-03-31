"""Tests for Phase 06 — commitment_classifier.py.

Strategy:
- All tests use SimpleNamespace (no DB required). Pure functions.
- Cover: externality, timing_strength, business_consequence, cognitive_burden,
         confidence_for_surfacing, has_critical_ambiguity, get_source_type,
         classify() end-to-end.
"""
from __future__ import annotations

import types
import uuid
from decimal import Decimal

import pytest

from app.services.commitment_classifier import (
    classify,
    get_source_type,
    has_critical_ambiguity,
    is_external,
    score_business_consequence,
    score_cognitive_burden,
    score_confidence_for_surfacing,
    score_timing_strength,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_commitment(**kwargs) -> types.SimpleNamespace:
    """Create a minimal commitment-like namespace."""
    defaults = {
        "id": str(uuid.uuid4()),
        "title": "Send the revised proposal",
        "description": None,
        "commitment_text": "I'll send the revised proposal by Friday",
        "context_type": "internal",
        "resolved_deadline": None,
        "vague_time_phrase": None,
        "deadline_candidates": None,
        "timing_ambiguity": None,
        "deliverable": "revised proposal",
        "target_entity": None,
        "confidence_commitment": Decimal("0.85"),
        "confidence_owner": Decimal("0.80"),
        "confidence_actionability": Decimal("0.75"),
        "ownership_ambiguity": None,
        "deliverable_ambiguity": None,
        "resolved_owner": "Alice",
        "suggested_owner": None,
        "observe_until": None,
        "lifecycle_state": "active",
        # candidate_commitments chain — absent by default → email_internal fallback
        "candidate_commitments": [],
    }
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


def make_candidate_chain(source_type: str) -> list:
    """Build a fake candidate_commitments chain with a given source_type."""
    source = types.SimpleNamespace(source_type=source_type)
    source_item = types.SimpleNamespace(source=source)
    cc = types.SimpleNamespace(source_item=source_item)
    return [cc]


# ---------------------------------------------------------------------------
# TestGetSourceType
# ---------------------------------------------------------------------------

class TestGetSourceType:
    def test_no_chain_defaults_to_email_internal(self):
        commitment = make_commitment(candidate_commitments=[])
        assert get_source_type(commitment) == "email_internal"

    def test_missing_attribute_defaults_to_email_internal(self):
        commitment = types.SimpleNamespace()  # no candidate_commitments
        assert get_source_type(commitment) == "email_internal"

    def test_chain_returns_source_type(self):
        commitment = make_commitment(
            candidate_commitments=make_candidate_chain("email_external")
        )
        assert get_source_type(commitment) == "email_external"

    def test_broken_chain_source_item_none(self):
        cc = types.SimpleNamespace(source_item=None)
        commitment = make_commitment(candidate_commitments=[cc])
        assert get_source_type(commitment) == "email_internal"

    def test_broken_chain_source_none(self):
        source_item = types.SimpleNamespace(source=None)
        cc = types.SimpleNamespace(source_item=source_item)
        commitment = make_commitment(candidate_commitments=[cc])
        assert get_source_type(commitment) == "email_internal"


# ---------------------------------------------------------------------------
# TestIsExternal
# ---------------------------------------------------------------------------

class TestIsExternal:
    def test_context_type_external_returns_true(self):
        commitment = make_commitment(context_type="external")
        assert is_external(commitment) is True

    def test_context_type_internal_returns_false(self):
        commitment = make_commitment(context_type="internal")
        assert is_external(commitment) is False

    def test_no_context_type_external_source_type(self):
        commitment = make_commitment(
            context_type=None,
            candidate_commitments=make_candidate_chain("email_external"),
        )
        assert is_external(commitment) is True

    def test_no_context_type_internal_source_type(self):
        commitment = make_commitment(
            context_type=None,
            candidate_commitments=make_candidate_chain("email_internal"),
        )
        assert is_external(commitment) is False


# ---------------------------------------------------------------------------
# TestScoreTimingStrength
# ---------------------------------------------------------------------------

class TestScoreTimingStrength:
    def test_resolved_deadline_returns_8(self):
        from datetime import datetime, timezone
        commitment = make_commitment(resolved_deadline=datetime.now(timezone.utc))
        assert score_timing_strength(commitment) == 8

    def test_strong_vague_phrase_returns_7(self):
        commitment = make_commitment(vague_time_phrase="by Friday")
        assert score_timing_strength(commitment) == 7

    def test_weak_vague_phrase_returns_2(self):
        commitment = make_commitment(vague_time_phrase="soon")
        assert score_timing_strength(commitment) == 2

    def test_deadline_candidates_non_empty_returns_4(self):
        commitment = make_commitment(deadline_candidates=["next week", "this week"])
        assert score_timing_strength(commitment) == 4

    def test_timing_ambiguity_missing_returns_0(self):
        commitment = make_commitment(timing_ambiguity="missing")
        assert score_timing_strength(commitment) == 0

    def test_no_timing_info_returns_3(self):
        commitment = make_commitment()
        assert score_timing_strength(commitment) == 3

    def test_vague_phrase_today_returns_7(self):
        commitment = make_commitment(vague_time_phrase="today by 5pm")
        assert score_timing_strength(commitment) == 7

    def test_vague_phrase_at_some_point_returns_2(self):
        commitment = make_commitment(vague_time_phrase="at some point next month")
        assert score_timing_strength(commitment) == 2


# ---------------------------------------------------------------------------
# TestScoreBusinessConsequence
# ---------------------------------------------------------------------------

class TestScoreBusinessConsequence:
    def test_external_has_higher_base_than_internal(self):
        internal = score_business_consequence(make_commitment(deliverable=None), external=False)
        external = score_business_consequence(make_commitment(deliverable=None, confidence_commitment=None), external=True)
        assert external > internal

    def test_high_confidence_boosts_score(self):
        base = score_business_consequence(
            make_commitment(confidence_commitment=Decimal("0.5")), external=False
        )
        boosted = score_business_consequence(
            make_commitment(confidence_commitment=Decimal("0.9")), external=False
        )
        assert boosted > base

    def test_explicit_deliverable_boosts_score(self):
        without = score_business_consequence(
            make_commitment(deliverable=None, confidence_commitment=None), external=False
        )
        with_del = score_business_consequence(
            make_commitment(deliverable="report", confidence_commitment=None), external=False
        )
        assert with_del > without

    def test_explicit_deadline_boosts_score(self):
        from datetime import datetime, timezone
        without = score_business_consequence(
            make_commitment(resolved_deadline=None, deliverable=None, confidence_commitment=None),
            external=False,
        )
        with_dl = score_business_consequence(
            make_commitment(
                resolved_deadline=datetime.now(timezone.utc),
                deliverable=None,
                confidence_commitment=None,
            ),
            external=False,
        )
        assert with_dl > without

    def test_score_capped_at_10(self):
        from datetime import datetime, timezone
        score = score_business_consequence(
            make_commitment(
                context_type="external",
                confidence_commitment=Decimal("0.99"),
                deliverable="big thing",
                resolved_deadline=datetime.now(timezone.utc),
            ),
            external=True,
        )
        assert score <= 10


# ---------------------------------------------------------------------------
# TestScoreCognitiveBurden
# ---------------------------------------------------------------------------

class TestScoreCognitiveBurden:
    def test_strong_followup_language_scores_high(self):
        commitment = make_commitment(
            commitment_text="I'll send the doc and I'll reply after the meeting",
            title="Send doc and reply",
        )
        result = score_cognitive_burden(commitment)
        assert result >= 6

    def test_neutral_language_scores_around_3(self):
        commitment = make_commitment(
            commitment_text="Q4 revenue projections complete",
            title="Q4 revenue analysis",
        )
        result = score_cognitive_burden(commitment)
        assert 2 <= result <= 5

    def test_external_context_adds_bonus(self):
        internal = make_commitment(context_type="internal")
        external = make_commitment(context_type="external")
        assert score_cognitive_burden(external) >= score_cognitive_burden(internal)

    def test_long_deliverable_boosts_score(self):
        short = make_commitment(deliverable="report")
        long_del = make_commitment(
            deliverable="a comprehensive 20-page analysis with appendix covering all the Q3 data points in detail"
        )
        assert score_cognitive_burden(long_del) >= score_cognitive_burden(short)


# ---------------------------------------------------------------------------
# TestScoreConfidenceForSurfacing
# ---------------------------------------------------------------------------

class TestScoreConfidenceForSurfacing:
    def test_all_high_confidence_near_one(self):
        commitment = make_commitment(
            confidence_commitment=Decimal("0.9"),
            confidence_owner=Decimal("0.9"),
            confidence_actionability=Decimal("0.9"),
        )
        result = score_confidence_for_surfacing(commitment)
        assert result >= 0.85

    def test_all_none_returns_half(self):
        commitment = make_commitment(
            confidence_commitment=None,
            confidence_owner=None,
            confidence_actionability=None,
        )
        result = score_confidence_for_surfacing(commitment)
        assert result == pytest.approx(0.5, abs=0.01)

    def test_null_sub_dimensions_default_to_commitment_confidence(self):
        """When confidence_owner and confidence_actionability are NULL,
        the composite should equal confidence_commitment, not be dragged
        down by a 0.5 default.

        This is the typical case for promoted commitments from Tier 2 detection.
        """
        commitment = make_commitment(
            confidence_commitment=Decimal("0.60"),
            confidence_owner=None,
            confidence_actionability=None,
        )
        result = score_confidence_for_surfacing(commitment)
        # Should be 0.6, not 0.54 (which is what happens with 0.5 defaults)
        assert result == pytest.approx(0.6, abs=0.01)

    def test_null_owner_only_defaults_to_commitment_confidence(self):
        """When only confidence_owner is NULL, default to confidence_commitment."""
        commitment = make_commitment(
            confidence_commitment=Decimal("0.70"),
            confidence_owner=None,
            confidence_actionability=Decimal("0.80"),
        )
        result = score_confidence_for_surfacing(commitment)
        # (0.7 * 0.4) + (0.7 * 0.3) + (0.8 * 0.3) = 0.28 + 0.21 + 0.24 = 0.73
        assert result == pytest.approx(0.73, abs=0.01)

    def test_low_commitment_conf_lowers_score(self):
        high = make_commitment(confidence_commitment=Decimal("0.9"))
        low = make_commitment(confidence_commitment=Decimal("0.1"))
        assert score_confidence_for_surfacing(low) < score_confidence_for_surfacing(high)

    def test_result_bounded_0_1(self):
        commitment = make_commitment(
            confidence_commitment=Decimal("1.0"),
            confidence_owner=Decimal("1.0"),
            confidence_actionability=Decimal("1.0"),
        )
        result = score_confidence_for_surfacing(commitment)
        assert 0.0 <= result <= 1.0


# ---------------------------------------------------------------------------
# TestHasCriticalAmbiguity
# ---------------------------------------------------------------------------

class TestHasCriticalAmbiguity:
    def test_owner_missing_is_critical(self):
        commitment = make_commitment(ownership_ambiguity="missing")
        assert has_critical_ambiguity(commitment) is True

    def test_owner_conflicting_is_critical(self):
        commitment = make_commitment(ownership_ambiguity="conflicting")
        assert has_critical_ambiguity(commitment) is True

    def test_timing_conflicting_is_critical(self):
        commitment = make_commitment(timing_ambiguity="conflicting")
        assert has_critical_ambiguity(commitment) is True

    def test_deliverable_unclear_is_critical(self):
        commitment = make_commitment(deliverable_ambiguity="unclear")
        assert has_critical_ambiguity(commitment) is True

    def test_external_no_owner_is_critical(self):
        commitment = make_commitment(
            context_type="external",
            resolved_owner=None,
            suggested_owner=None,
        )
        assert has_critical_ambiguity(commitment) is True

    def test_no_ambiguity_returns_false(self):
        commitment = make_commitment(
            ownership_ambiguity=None,
            timing_ambiguity=None,
            deliverable_ambiguity=None,
            context_type="internal",
            resolved_owner="Alice",
        )
        assert has_critical_ambiguity(commitment) is False

    def test_internal_no_owner_not_critical(self):
        """Internal commitment with no owner is NOT automatically critical."""
        commitment = make_commitment(
            context_type="internal",
            resolved_owner=None,
            suggested_owner=None,
            ownership_ambiguity=None,
        )
        assert has_critical_ambiguity(commitment) is False


# ---------------------------------------------------------------------------
# TestClassify (end-to-end)
# ---------------------------------------------------------------------------

class TestClassify:
    def test_external_deadline_produces_high_scores(self):
        from datetime import datetime, timezone
        commitment = make_commitment(
            context_type="external",
            resolved_deadline=datetime.now(timezone.utc),
            confidence_commitment=Decimal("0.85"),
            confidence_owner=Decimal("0.80"),
        )
        result = classify(commitment)
        assert result.is_external is True
        assert result.timing_strength == 8
        assert result.business_consequence >= 8

    def test_internal_no_timing_produces_low_scores(self):
        commitment = make_commitment(
            context_type="internal",
            resolved_deadline=None,
            vague_time_phrase=None,
            timing_ambiguity="missing",
            confidence_commitment=Decimal("0.3"),
        )
        result = classify(commitment)
        assert result.is_external is False
        assert result.timing_strength == 0
        assert result.business_consequence <= 6

    def test_returns_classifier_result_dataclass(self):
        from app.services.commitment_classifier import ClassifierResult
        commitment = make_commitment()
        result = classify(commitment)
        assert isinstance(result, ClassifierResult)
        assert 0 <= result.timing_strength <= 10
        assert 0 <= result.business_consequence <= 10
        assert 0 <= result.cognitive_burden <= 10
        assert 0.0 <= result.confidence_for_surfacing <= 1.0

    def test_source_type_included_in_result(self):
        commitment = make_commitment(
            candidate_commitments=make_candidate_chain("meeting_external")
        )
        result = classify(commitment)
        assert result.source_type == "meeting_external"
