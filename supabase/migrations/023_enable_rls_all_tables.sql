-- Enable Row Level Security on all public tables and deny anonymous access.
-- The FastAPI backend connects via service role / direct Postgres (bypasses RLS).
-- The frontend only uses Supabase Auth, never direct table access.
-- This migration closes the anon-key data exposure flagged by Supabase.

-- adhoc_signals
ALTER TABLE public.adhoc_signals ENABLE ROW LEVEL SECURITY;
CREATE POLICY "deny_anon" ON public.adhoc_signals FOR ALL TO anon USING (false);

-- alembic_version
ALTER TABLE public.alembic_version ENABLE ROW LEVEL SECURITY;
CREATE POLICY "deny_anon" ON public.alembic_version FOR ALL TO anon USING (false);

-- candidate_commitments
ALTER TABLE public.candidate_commitments ENABLE ROW LEVEL SECURITY;
CREATE POLICY "deny_anon" ON public.candidate_commitments FOR ALL TO anon USING (false);

-- candidate_signal_records
ALTER TABLE public.candidate_signal_records ENABLE ROW LEVEL SECURITY;
CREATE POLICY "deny_anon" ON public.candidate_signal_records FOR ALL TO anon USING (false);

-- clarifications
ALTER TABLE public.clarifications ENABLE ROW LEVEL SECURITY;
CREATE POLICY "deny_anon" ON public.clarifications FOR ALL TO anon USING (false);

-- commitment_ambiguities
ALTER TABLE public.commitment_ambiguities ENABLE ROW LEVEL SECURITY;
CREATE POLICY "deny_anon" ON public.commitment_ambiguities FOR ALL TO anon USING (false);

-- commitment_candidates
ALTER TABLE public.commitment_candidates ENABLE ROW LEVEL SECURITY;
CREATE POLICY "deny_anon" ON public.commitment_candidates FOR ALL TO anon USING (false);

-- commitment_contexts
ALTER TABLE public.commitment_contexts ENABLE ROW LEVEL SECURITY;
CREATE POLICY "deny_anon" ON public.commitment_contexts FOR ALL TO anon USING (false);

-- commitment_event_links
ALTER TABLE public.commitment_event_links ENABLE ROW LEVEL SECURITY;
CREATE POLICY "deny_anon" ON public.commitment_event_links FOR ALL TO anon USING (false);

-- commitment_signals
ALTER TABLE public.commitment_signals ENABLE ROW LEVEL SECURITY;
CREATE POLICY "deny_anon" ON public.commitment_signals FOR ALL TO anon USING (false);

-- commitments
ALTER TABLE public.commitments ENABLE ROW LEVEL SECURITY;
CREATE POLICY "deny_anon" ON public.commitments FOR ALL TO anon USING (false);

-- common_term_aliases
ALTER TABLE public.common_term_aliases ENABLE ROW LEVEL SECURITY;
CREATE POLICY "deny_anon" ON public.common_term_aliases FOR ALL TO anon USING (false);

-- common_terms
ALTER TABLE public.common_terms ENABLE ROW LEVEL SECURITY;
CREATE POLICY "deny_anon" ON public.common_terms FOR ALL TO anon USING (false);

-- detection_audit
ALTER TABLE public.detection_audit ENABLE ROW LEVEL SECURITY;
CREATE POLICY "deny_anon" ON public.detection_audit FOR ALL TO anon USING (false);

-- digest_log
ALTER TABLE public.digest_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY "deny_anon" ON public.digest_log FOR ALL TO anon USING (false);

-- eval_datasets
ALTER TABLE public.eval_datasets ENABLE ROW LEVEL SECURITY;
CREATE POLICY "deny_anon" ON public.eval_datasets FOR ALL TO anon USING (false);

-- eval_run_items
ALTER TABLE public.eval_run_items ENABLE ROW LEVEL SECURITY;
CREATE POLICY "deny_anon" ON public.eval_run_items FOR ALL TO anon USING (false);

-- eval_runs
ALTER TABLE public.eval_runs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "deny_anon" ON public.eval_runs FOR ALL TO anon USING (false);

-- events
ALTER TABLE public.events ENABLE ROW LEVEL SECURITY;
CREATE POLICY "deny_anon" ON public.events FOR ALL TO anon USING (false);

-- lifecycle_transitions
ALTER TABLE public.lifecycle_transitions ENABLE ROW LEVEL SECURITY;
CREATE POLICY "deny_anon" ON public.lifecycle_transitions FOR ALL TO anon USING (false);

-- llm_judge_runs
ALTER TABLE public.llm_judge_runs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "deny_anon" ON public.llm_judge_runs FOR ALL TO anon USING (false);

-- normalization_runs
ALTER TABLE public.normalization_runs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "deny_anon" ON public.normalization_runs FOR ALL TO anon USING (false);

-- normalized_signals
ALTER TABLE public.normalized_signals ENABLE ROW LEVEL SECURITY;
CREATE POLICY "deny_anon" ON public.normalized_signals FOR ALL TO anon USING (false);

-- outcome_feedback
ALTER TABLE public.outcome_feedback ENABLE ROW LEVEL SECURITY;
CREATE POLICY "deny_anon" ON public.outcome_feedback FOR ALL TO anon USING (false);

-- raw_signal_ingests
ALTER TABLE public.raw_signal_ingests ENABLE ROW LEVEL SECURITY;
CREATE POLICY "deny_anon" ON public.raw_signal_ingests FOR ALL TO anon USING (false);

-- schema_migrations
ALTER TABLE public.schema_migrations ENABLE ROW LEVEL SECURITY;
CREATE POLICY "deny_anon" ON public.schema_migrations FOR ALL TO anon USING (false);

-- signal_feedback
ALTER TABLE public.signal_feedback ENABLE ROW LEVEL SECURITY;
CREATE POLICY "deny_anon" ON public.signal_feedback FOR ALL TO anon USING (false);

-- signal_processing_runs
ALTER TABLE public.signal_processing_runs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "deny_anon" ON public.signal_processing_runs FOR ALL TO anon USING (false);

-- signal_processing_stage_runs
ALTER TABLE public.signal_processing_stage_runs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "deny_anon" ON public.signal_processing_stage_runs FOR ALL TO anon USING (false);

-- source_items
ALTER TABLE public.source_items ENABLE ROW LEVEL SECURITY;
CREATE POLICY "deny_anon" ON public.source_items FOR ALL TO anon USING (false);

-- sources
ALTER TABLE public.sources ENABLE ROW LEVEL SECURITY;
CREATE POLICY "deny_anon" ON public.sources FOR ALL TO anon USING (false);

-- surfacing_audit
ALTER TABLE public.surfacing_audit ENABLE ROW LEVEL SECURITY;
CREATE POLICY "deny_anon" ON public.surfacing_audit FOR ALL TO anon USING (false);

-- user_commitment_profiles
ALTER TABLE public.user_commitment_profiles ENABLE ROW LEVEL SECURITY;
CREATE POLICY "deny_anon" ON public.user_commitment_profiles FOR ALL TO anon USING (false);

-- user_identity_profiles
ALTER TABLE public.user_identity_profiles ENABLE ROW LEVEL SECURITY;
CREATE POLICY "deny_anon" ON public.user_identity_profiles FOR ALL TO anon USING (false);

-- user_settings
ALTER TABLE public.user_settings ENABLE ROW LEVEL SECURITY;
CREATE POLICY "deny_anon" ON public.user_settings FOR ALL TO anon USING (false);

-- users
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
CREATE POLICY "deny_anon" ON public.users FOR ALL TO anon USING (false);
