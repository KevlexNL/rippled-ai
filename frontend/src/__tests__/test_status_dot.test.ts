import { describe, it, expect } from 'vitest'
import { getStatusColor, getGroupStatusColor } from '../types'
import type { CommitmentRead } from '../types'

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
    post_event_reviewed: false,
    context_id: null,
    linked_events: null,
    source_sender_name: null,
    source_sender_email: null,
    source_occurred_at: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

describe('getStatusColor', () => {
  it('1. returns red for needs_clarification lifecycle state', () => {
    const c = makeCommitment({ lifecycle_state: 'needs_clarification' })
    expect(getStatusColor(c)).toBe('red')
  })

  it('2. returns red when ownership_ambiguity is missing', () => {
    const c = makeCommitment({ ownership_ambiguity: 'missing', lifecycle_state: 'active' })
    expect(getStatusColor(c)).toBe('red')
  })

  it('3. returns red when timing_ambiguity is missing', () => {
    const c = makeCommitment({ timing_ambiguity: 'missing', lifecycle_state: 'active' })
    expect(getStatusColor(c)).toBe('red')
  })

  it('4. returns yellow for proposed lifecycle state', () => {
    const c = makeCommitment({ lifecycle_state: 'proposed', confidence_commitment: '0.9' })
    expect(getStatusColor(c)).toBe('yellow')
  })

  it('5. returns yellow when ownership_ambiguity is vague', () => {
    const c = makeCommitment({ ownership_ambiguity: 'vague', lifecycle_state: 'active' })
    expect(getStatusColor(c)).toBe('yellow')
  })

  it('6. returns yellow when timing_ambiguity is vague', () => {
    const c = makeCommitment({ timing_ambiguity: 'vague', lifecycle_state: 'active' })
    expect(getStatusColor(c)).toBe('yellow')
  })

  it('7. returns yellow when confidence_commitment < 0.5 and no other flags', () => {
    const c = makeCommitment({
      lifecycle_state: 'active',
      confidence_commitment: '0.3',
      ownership_ambiguity: null,
      timing_ambiguity: null,
    })
    expect(getStatusColor(c)).toBe('yellow')
  })

  it('8. returns green when active with no ambiguity and high confidence', () => {
    const c = makeCommitment({
      lifecycle_state: 'active',
      confidence_commitment: '0.9',
      ownership_ambiguity: null,
      timing_ambiguity: null,
    })
    expect(getStatusColor(c)).toBe('green')
  })

  it('9. returns green when closed with no ambiguity', () => {
    const c = makeCommitment({
      lifecycle_state: 'closed',
      confidence_commitment: null,
      ownership_ambiguity: null,
      timing_ambiguity: null,
    })
    expect(getStatusColor(c)).toBe('green')
  })

  it('10. confidence_commitment exactly 0.5 is not < 0.5, returns green', () => {
    const c = makeCommitment({
      lifecycle_state: 'active',
      confidence_commitment: '0.5',
      ownership_ambiguity: null,
      timing_ambiguity: null,
    })
    expect(getStatusColor(c)).toBe('green')
  })
})

describe('getGroupStatusColor', () => {
  it('10. returns red when group contains at least one red commitment', () => {
    const red = makeCommitment({ lifecycle_state: 'needs_clarification' })
    const green = makeCommitment({ lifecycle_state: 'active', confidence_commitment: '0.9' })
    expect(getGroupStatusColor([red, green])).toBe('red')
  })

  it('11. returns yellow when group has yellow + green but no red', () => {
    const yellow = makeCommitment({ lifecycle_state: 'proposed', confidence_commitment: '0.9' })
    const green = makeCommitment({ lifecycle_state: 'active', confidence_commitment: '0.9' })
    expect(getGroupStatusColor([yellow, green])).toBe('yellow')
  })

  it('12. returns green when group has only green commitments', () => {
    const g1 = makeCommitment({ lifecycle_state: 'active', confidence_commitment: '0.9' })
    const g2 = makeCommitment({ lifecycle_state: 'closed', confidence_commitment: null })
    expect(getGroupStatusColor([g1, g2])).toBe('green')
  })

  it('returns green for an empty group', () => {
    expect(getGroupStatusColor([])).toBe('green')
  })
})
