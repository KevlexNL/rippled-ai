"""Model-Assisted Detection Service — Phase C1.

Calls OpenAI (GPT-4.1-mini) to classify a CommitmentCandidate as
commitment / not-commitment with confidence and explanation.

Public API:
    service = ModelDetectionService(api_key="...", model="gpt-4.1-mini")
    result = service.classify(candidate)   # returns ModelDetectionResult | None

Error contract:
    classify() NEVER raises. Returns None on any failure (API error,
    malformed response, rate limit exhaustion, missing API key).
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any

from openai import OpenAI, RateLimitError

from app.connectors.shared.normalized_signal import NormalizedSignal

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a commitment extraction engine for a workplace intelligence system.

A commitment is a statement where someone obligates themselves or others to a specific
future action, deliverable, or outcome. This includes:
- Explicit: "I will", "I'll", "We will", "I promise", "I commit to"
- Implicit: "Consider it done", "Leave it with me", "I'll look into that"
- Follow-ups: "Follow up on [topic]", "Need to follow up", "Will follow up with [person]", "follow up on budget", "follow up on headcount"
- Bare follow-ups (ALWAYS a commitment): "need to follow up", "will follow up", "should follow up"
- Check-ins on a topic: "Checking in on the budget", "checking in on the project" — these imply a follow-up obligation
- Collective: "We need to get this done", "Someone should handle this"

NOT a commitment (NEVER extract these):
- Greetings and salutations: "Hi", "Hello", "Hey", "Good morning", "Good afternoon", "Dear team"
- Pleasantries and well-wishes: "Hope you're doing well", "Hope this finds you well", "Hope all is well", "Trust you are well", "Happy Friday"
- Sign-offs and closings: "Best regards", "Thanks", "Cheers", "Talk soon", "Warm regards", "Kind regards"
- Social niceties: "Looking forward to connecting", "Thank you for your time"
- Casual acknowledgments: "OK", "Sounds good", "Got it"
- Questions or hypotheticals: "Should we...?", "What if we..."
- Past-tense descriptions: "I already did X"
- Filler phrases: "By the way", "Just checking in" (but NOT "checking in on [topic]" — that IS a follow-up)
- Classification labels or meta-references: "greeting", "pleasantry", "filler" — these are labels, not commitments

IMPORTANT: The word "greeting" itself is NEVER a commitment. Social pleasantries are NOT commitments. Do NOT extract classification labels (e.g. "greeting", "acknowledgment") as commitments.

CRITICAL RULE — FOLLOW-UPS: ANY form of "follow up" is ALWAYS a commitment. This includes "follow up on [topic]", "need to follow up", "will follow up", "should follow up", "follow up on budget", "follow up on headcount", etc. Never skip these.

## Canonical commitment structure

Every commitment must be extracted in this form:
  [Owner] promised [Deliverable] to [Counterparty] [by Deadline]

You MUST extract all five fields:
1. owner — who made the promise (name or "unknown")
2. deliverable — what was promised (concise, action-oriented)
3. counterparty — who it was promised to (name, role, or "team")
4. deadline — explicit or inferred deadline (ISO date or text), or null if none
5. user_relationship — the logged-in user's relationship to this commitment:
   - "mine": the commitment owner IS the current user (by name, email, or known alias)
   - "contributing": the current user is mentioned as a participant but not the primary owner
   - "watching": the commitment is between two other parties; current user is cc'd, facilitated, or just present

## Completeness validation

If owner AND deliverable AND counterparty cannot ALL be populated with reasonable confidence,
set structure_complete=false. Only set structure_complete=true when all three are present.

Given a communication fragment, its surrounding context, and the current user's identity,
classify and extract the commitment.

## Speech act classification

speech_act: Classify what the speaker is doing:
- "request": asking someone else to do something ("can you send me X?", "please handle this")
- "self_commitment": speaker commits to doing something themselves ("I'll send it", "I will handle this")
- "acceptance": speaker accepts ownership of a prior request ("sure, I'll take care of it", "on it")
- "status_update": progress report with no new obligation ("we're halfway through", "update: still working on it")
- "completion": signals delivery or done ("sent", "done", "uploaded the file", "delivered above")
- "cancellation": withdrawing a prior commitment ("actually I can't make it", "disregard my earlier message")
- "decline": refusing a request ("I can't take this on", "not able to commit to this")
- "reassignment": transferring ownership ("passing this to John", "can you take this instead?")
- "informational": no commitment content at all

BEFORE YOU RESPOND — mandatory two-pass self-check:

PASS 1 — REJECT check (run first, immediately return false if ANY match):
- Is the text purely a greeting/salutation word? (e.g. "Hi", "Hello", "Dear team", "Good morning") → is_commitment=false
- Is the text purely a pleasantry or well-wish? (e.g. "Hope you're doing well", "Happy Friday") → is_commitment=false
- Is the text purely a sign-off? (e.g. "Best regards", "Cheers", "Talk soon") → is_commitment=false
- Is the text a classification label or meta-reference? (e.g. "greeting", "pleasantry", "acknowledgment") → is_commitment=false
- Is the text a casual acknowledgment with no future action? (e.g. "OK", "Sounds good", "Got it") → is_commitment=false
If PASS 1 matched: set is_commitment=false and skip to output. Do NOT proceed to PASS 2.

PASS 2 — COMMIT check (run only if PASS 1 did NOT match):
- Does the text contain ANY form of "follow up"? ("follow up on X", "need to follow up", "will follow up", "should follow up", "follow up on budget", "follow up on headcount") → is_commitment=true, HIGH confidence
- Does the text contain an explicit future obligation? ("I will", "I'll", "We will", "I promise", "Consider it done", "Leave it with me") → is_commitment=true
- Does the text describe a future action, deliverable, or outcome someone is accountable for? → is_commitment=true
- Otherwise → is_commitment=false

## Email input format

The input may include two sections:
[CURRENT MESSAGE]: The author's new content. Detect commitment candidates from this.
[PRIOR CONTEXT]: Quoted history from earlier in the thread. Do NOT create new commitment candidates from this section. Use it only to understand context, resolve references, or identify completion of existing commitments.

FINAL sanity check: if your answer is is_commitment=true but the text is just a social phrase with no future action, correct it to false. If your answer is is_commitment=false but the text contains "follow up", correct it to true.

You must respond with valid JSON only, exactly this structure:
{
  "is_commitment": <boolean>,
  "speech_act": "<request|self_commitment|acceptance|status_update|completion|cancellation|decline|reassignment|informational>",
  "confidence": <float 0.0 to 1.0>,
  "explanation": "<1-2 sentence explanation>",
  "suggested_owner": "<name of who made the commitment, or null>",
  "suggested_deadline": "<deadline as text or ISO date, or null>",
  "deliverable": "<what was promised, concise action-oriented phrase, or null>",
  "counterparty": "<who it was promised to, or null>",
  "user_relationship": "<mine|contributing|watching>",
  "structure_complete": <boolean>
}"""

_MAX_RETRIES = 3
_INITIAL_BACKOFF = 1.0  # seconds
_PROMPT_VERSION = "ongoing-v9"


@dataclass
class ModelDetectionResult:
    """Result from model classification."""
    is_commitment: bool
    confidence: float
    explanation: str
    suggested_owner: str | None
    suggested_deadline: str | None
    speech_act: str | None = None
    deliverable: str | None = None
    counterparty: str | None = None
    user_relationship: str | None = None
    structure_complete: bool = False
    # Audit metadata
    raw_prompt: str | None = None
    raw_response: str | None = None
    parsed_result: dict | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    model: str | None = None
    duration_ms: int | None = None
    prompt_version: str | None = None
    error_detail: str | None = None


class ModelDetectionService:
    """Classifies a CommitmentCandidate using OpenAI structured output.

    Args:
        api_key: OpenAI API key. Empty string disables the service.
        model: OpenAI model name. Defaults to "gpt-4.1-mini".
    """

    def __init__(self, api_key: str, model: str = "gpt-4.1-mini") -> None:
        self._model = model
        if api_key:
            self._client = OpenAI(api_key=api_key)
        else:
            self._client = None  # type: ignore[assignment]

    def classify(
        self,
        candidate: Any,
        user_name: str | None = None,
        user_email: str | None = None,
        signal: NormalizedSignal | None = None,
    ) -> ModelDetectionResult | None:
        """Classify a candidate as commitment / not-commitment.

        Args:
            candidate: CommitmentCandidate ORM object or compatible namespace.
                       Must have .context_window (dict or None) and .raw_text.
            user_name: Display name of the logged-in user (for relationship detection).
            user_email: Email of the logged-in user (for relationship detection).
            signal: Optional NormalizedSignal. When provided, uses its
                    latest_authored_text and prior_context_text instead of
                    raw context_window content.

        Returns:
            ModelDetectionResult on success, None on any failure.
        """
        if self._client is None:
            logger.debug("ModelDetectionService: no API key, skipping")
            return None

        # When a NormalizedSignal is provided, build context from it
        if signal is not None:
            context_window = self._signal_to_context_window(signal, candidate)
        else:
            context_window = candidate.context_window

        if not context_window:
            logger.debug(
                "Candidate %s has no context_window — skipping model call",
                getattr(candidate, "id", "?"),
            )
            return None

        user_message = self._build_user_message(context_window, user_name, user_email)
        full_prompt = f"[system]\n{_SYSTEM_PROMPT}\n\n[user]\n{user_message}"

        call_start = time.monotonic()

        for attempt in range(_MAX_RETRIES):
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": user_message},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.1,
                )

                duration_ms = int((time.monotonic() - call_start) * 1000)

                # Log token usage
                tokens_in = None
                tokens_out = None
                usage = response.usage
                if usage:
                    tokens_in = usage.prompt_tokens
                    tokens_out = usage.completion_tokens
                    logger.debug(
                        "OpenAI usage — model=%s prompt_tokens=%d completion_tokens=%d candidate=%s",
                        self._model,
                        tokens_in,
                        tokens_out,
                        getattr(candidate, "id", "?"),
                    )

                result = self._parse_response(response)
                if result is None:
                    raw_content = ""
                    try:
                        raw_content = response.choices[0].message.content
                    except (IndexError, AttributeError):
                        pass
                    return ModelDetectionResult(
                        is_commitment=False,
                        confidence=0.0,
                        explanation="",
                        suggested_owner=None,
                        suggested_deadline=None,
                        raw_prompt=full_prompt,
                        raw_response=raw_content,
                        parsed_result=None,
                        tokens_in=tokens_in,
                        tokens_out=tokens_out,
                        model=self._model,
                        duration_ms=duration_ms,
                        prompt_version=_PROMPT_VERSION,
                        error_detail="Failed to parse response",
                    )

                # Attach audit metadata
                raw_content = response.choices[0].message.content
                result.raw_prompt = full_prompt
                result.raw_response = raw_content
                result.parsed_result = json.loads(raw_content)
                result.tokens_in = tokens_in
                result.tokens_out = tokens_out
                result.model = self._model
                result.duration_ms = duration_ms
                result.prompt_version = _PROMPT_VERSION
                return result

            except RateLimitError as exc:
                if attempt < _MAX_RETRIES - 1:
                    backoff = _INITIAL_BACKOFF * (2 ** attempt)
                    logger.warning(
                        "OpenAI rate limit (attempt %d/%d), retrying in %.1fs: %s",
                        attempt + 1, _MAX_RETRIES, backoff, exc,
                    )
                    time.sleep(backoff)
                else:
                    logger.error(
                        "OpenAI rate limit exhausted after %d retries for candidate %s",
                        _MAX_RETRIES, getattr(candidate, "id", "?"),
                    )
                    return None

            except Exception as exc:
                duration_ms = int((time.monotonic() - call_start) * 1000)
                logger.error(
                    "OpenAI API error for candidate %s: %s",
                    getattr(candidate, "id", "?"), exc,
                )
                return None

        return None  # unreachable, but satisfies type checker

    @staticmethod
    def _signal_to_context_window(signal: NormalizedSignal, candidate: Any) -> dict:
        """Build a context_window dict from a NormalizedSignal.

        Uses latest_authored_text as trigger_text and prior_context_text
        as explicitly labelled prior context.
        """
        # Use candidate's trigger_text if available (more specific), fall back to signal
        cw = getattr(candidate, "context_window", None) or {}
        return {
            "trigger_text": cw.get("trigger_text", signal.latest_authored_text),
            "pre_context": cw.get("pre_context", ""),
            "post_context": cw.get("post_context", ""),
            "source_type": signal.source_type,
            "prior_context": signal.prior_context_text,
        }

    def _build_user_message(self, context_window: dict, user_name: str | None = None, user_email: str | None = None) -> str:
        trigger = context_window.get("trigger_text", "")
        pre = context_window.get("pre_context", "")
        post = context_window.get("post_context", "")
        source = context_window.get("source_type", "unknown")
        prior_context = context_window.get("prior_context")

        parts = []
        # Inject user identity for relationship detection
        identity_parts = []
        if user_name:
            identity_parts.append(f"name={user_name}")
        if user_email:
            identity_parts.append(f"email={user_email}")
        if identity_parts:
            parts.append(f"[Current user]: {', '.join(identity_parts)}")

        parts.append(f"Source type: {source}")
        parts.append("")

        # Use labeled sections when prior context is available
        if prior_context:
            parts.append("[CURRENT MESSAGE]")
        if pre:
            parts.append(f"[Before]: {pre}")
        parts.append(f"[Trigger]: {trigger}")
        if post:
            parts.append(f"[After]: {post}")
        if prior_context:
            parts.append(f"\n[PRIOR CONTEXT]\n{prior_context}")

        return "\n".join(parts)

    def _parse_response(self, response: Any) -> ModelDetectionResult | None:
        """Parse OpenAI response into ModelDetectionResult. Returns None on parse failure."""
        try:
            content = response.choices[0].message.content
            data = json.loads(content)

            # Validate required fields
            is_commitment = data["is_commitment"]
            confidence = float(data["confidence"])
            explanation = data["explanation"]

            # Validate user_relationship value
            raw_relationship = data.get("user_relationship")
            user_relationship = raw_relationship if raw_relationship in ("mine", "contributing", "watching") else None

            # Validate speech_act value
            _VALID_SPEECH_ACTS = {
                "request", "self_commitment", "acceptance", "status_update",
                "completion", "cancellation", "decline", "reassignment", "informational",
            }
            raw_speech_act = data.get("speech_act")
            speech_act = raw_speech_act if raw_speech_act in _VALID_SPEECH_ACTS else None

            return ModelDetectionResult(
                is_commitment=bool(is_commitment),
                confidence=confidence,
                explanation=str(explanation),
                suggested_owner=data.get("suggested_owner"),
                suggested_deadline=data.get("suggested_deadline"),
                speech_act=speech_act,
                deliverable=data.get("deliverable"),
                counterparty=data.get("counterparty"),
                user_relationship=user_relationship,
                structure_complete=bool(data.get("structure_complete", False)),
            )
        except (KeyError, ValueError, json.JSONDecodeError, IndexError) as exc:
            logger.warning("Failed to parse OpenAI response: %s", exc)
            return None
