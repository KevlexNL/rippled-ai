"""LLM Orchestration Layer — staged signal interpretation pipeline.

Replaces the monolithic interpretation step with a staged pipeline:
  Stage 0: Eligibility check (deterministic)
  Stage 1: Candidate gate (cheap LLM)
  Stage 2: Speech-act classification (cheap LLM)
  Stage 3: Commitment field extraction (LLM)
  Stage 4: Deterministic routing decision (code)
  Stage 5: Optional escalation pass (strong LLM)
  Stage 6: Persistence and logging (code)
"""
