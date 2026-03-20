import { describe, it, expect } from 'vitest'
import type { CommitmentRead } from '../types'
import { groupByContextId } from '../utils/grouping'

function makeCommitment(overrides: Partial<CommitmentRead> = {}): CommitmentRead {
  return {
    id: 'test-id',
    user_id: 'user-1',
    version: 1,
    title: 'Test commitment',
    description: null,
    commitment_text: null,
    commitment_type: null,
    priority_class: null,
    context_type: null,
    resolved_owner: null,
    suggested_owner: null,
    ownership_ambiguity: null,
    resolved_deadline: null,
    vague_time_phrase: null,
    suggested_due_date: null,
    timing_ambiguity: null,
    deliverable: null,
    target_entity: null,
    suggested_next_step: null,
    deliverable_ambiguity: null,
    lifecycle_state: 'active',
    state_changed_at: '2026-01-01T00:00:00Z',
    confidence_commitment: '0.9',
    confidence_owner: null,
    confidence_deadline: null,
    confidence_delivery: null,
    confidence_closure: null,
    confidence_actionability: null,
    commitment_explanation: null,
    missing_pieces_explanation: null,
    is_surfaced: true,
    surfaced_at: null,
    observe_until: null,
    observation_window_hours: null,
    surfaced_as: null,
    priority_score: null,
    timing_strength: null,
    business_consequence: null,
    cognitive_burden: null,
    confidence_for_surfacing: null,
    surfacing_reason: null,
    owner_candidates: null,
    deadline_candidates: null,
    delivery_state: null,
    counterparty_type: null,
    counterparty_email: null,
    counterparty_name: null,
    counterparty_resolved: null,
    user_relationship: null,
    structure_complete: false,
    post_event_reviewed: false,
    context_id: null,
    linked_events: null,
    source_sender_name: null,
    source_sender_email: null,
    source_occurred_at: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    skipped_at: null,
    skip_reason: null,
    ...overrides,
  }
}

describe('groupByContextId', () => {
  it('groups commitments by context_id', () => {
    const c1 = makeCommitment({ id: 'c1', context_id: 'ctx-1' })
    const c2 = makeCommitment({ id: 'c2', context_id: 'ctx-1' })
    const c3 = makeCommitment({ id: 'c3', context_id: 'ctx-2' })

    const result = groupByContextId([c1, c2, c3])
    expect(result.groups).toEqual({
      'ctx-1': [c1, c2],
      'ctx-2': [c3],
    })
    expect(result.ungrouped).toEqual([])
  })

  it('separates commitments without context_id into ungrouped', () => {
    const c1 = makeCommitment({ id: 'c1', context_id: 'ctx-1' })
    const c2 = makeCommitment({ id: 'c2', context_id: null })
    const c3 = makeCommitment({ id: 'c3', context_id: null })

    const result = groupByContextId([c1, c2, c3])
    expect(result.groups).toEqual({ 'ctx-1': [c1] })
    expect(result.ungrouped).toEqual([c2, c3])
  })

  it('returns empty groups and ungrouped for empty input', () => {
    const result = groupByContextId([])
    expect(result.groups).toEqual({})
    expect(result.ungrouped).toEqual([])
  })

  it('all commitments ungrouped when none have context_id', () => {
    const c1 = makeCommitment({ id: 'c1' })
    const c2 = makeCommitment({ id: 'c2' })

    const result = groupByContextId([c1, c2])
    expect(result.groups).toEqual({})
    expect(result.ungrouped).toEqual([c1, c2])
  })

  it('hasContexts is true when at least one commitment has context_id', () => {
    const c1 = makeCommitment({ id: 'c1', context_id: 'ctx-1' })
    const c2 = makeCommitment({ id: 'c2' })

    const result = groupByContextId([c1, c2])
    expect(result.hasContexts).toBe(true)
  })

  it('hasContexts is false when no commitments have context_id', () => {
    const c1 = makeCommitment({ id: 'c1' })
    const result = groupByContextId([c1])
    expect(result.hasContexts).toBe(false)
  })
})
