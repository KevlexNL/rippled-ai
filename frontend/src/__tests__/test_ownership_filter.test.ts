import { describe, it, expect } from 'vitest'
import type { CommitmentRead } from '../types'
import {
  classifyOwnership,
  filterMineAndTriage,
  filterMine,
  filterOthers,
} from '../utils/ownershipFilter'

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

const userEmail = 'kevin@kevlex.digital'
const userName = 'Kevin Beeftink'

describe('classifyOwnership — server-side user_relationship', () => {
  it('uses server-side user_relationship when present', () => {
    const c = makeCommitment({ user_relationship: 'mine' })
    expect(classifyOwnership(c, userName, userEmail)).toBe('mine')
  })

  it('returns contributing when user_relationship is contributing', () => {
    const c = makeCommitment({ user_relationship: 'contributing' })
    expect(classifyOwnership(c, userName, userEmail)).toBe('contributing')
  })

  it('returns watching when user_relationship is watching', () => {
    const c = makeCommitment({ user_relationship: 'watching' })
    expect(classifyOwnership(c, userName, userEmail)).toBe('watching')
  })

  it('falls back to heuristic when user_relationship is null', () => {
    const c = makeCommitment({ user_relationship: null, resolved_owner: 'Kevin' })
    expect(classifyOwnership(c, userName, userEmail)).toBe('mine')
  })
})

describe('classifyOwnership — heuristic fallback', () => {
  it('returns "mine" when resolved_owner contains user name (case-insensitive)', () => {
    const c = makeCommitment({ resolved_owner: 'Kevin' })
    expect(classifyOwnership(c, userName, userEmail)).toBe('mine')
  })

  it('returns "mine" when resolved_owner contains user email', () => {
    const c = makeCommitment({ resolved_owner: 'kevin@kevlex.digital' })
    expect(classifyOwnership(c, userName, userEmail)).toBe('mine')
  })

  it('returns "mine" when suggested_owner matches user name', () => {
    const c = makeCommitment({ resolved_owner: null, suggested_owner: 'Kevin Beeftink' })
    expect(classifyOwnership(c, userName, userEmail)).toBe('mine')
  })

  it('returns "triage" when resolved_owner is null and no suggested_owner', () => {
    const c = makeCommitment({ resolved_owner: null, suggested_owner: null })
    expect(classifyOwnership(c, userName, userEmail)).toBe('triage')
  })

  it('returns "watching" when resolved_owner is someone else', () => {
    const c = makeCommitment({ resolved_owner: 'Alice Johnson' })
    expect(classifyOwnership(c, userName, userEmail)).toBe('watching')
  })

  it('returns "mine" for partial name match (first name only)', () => {
    const c = makeCommitment({ resolved_owner: 'kevin' })
    expect(classifyOwnership(c, userName, userEmail)).toBe('mine')
  })

  it('returns "watching" when suggested_owner is someone else and resolved_owner is null', () => {
    const c = makeCommitment({ resolved_owner: null, suggested_owner: 'Alice' })
    expect(classifyOwnership(c, userName, userEmail)).toBe('watching')
  })

  it('handles null userName gracefully — falls back to email match', () => {
    const c = makeCommitment({ resolved_owner: 'kevin@kevlex.digital' })
    expect(classifyOwnership(c, null, userEmail)).toBe('mine')
  })

  it('handles null userName — no match when owner is name only', () => {
    const c = makeCommitment({ resolved_owner: 'Kevin' })
    expect(classifyOwnership(c, null, userEmail)).toBe('watching')
  })

  it('handles null userEmail gracefully', () => {
    const c = makeCommitment({ resolved_owner: 'kevin@kevlex.digital' })
    expect(classifyOwnership(c, userName, null)).toBe('mine')
  })
})

describe('filterMineAndTriage', () => {
  it('returns mine + contributing + triage commitments', () => {
    const mine = makeCommitment({ id: '1', user_relationship: 'mine' })
    const contributing = makeCommitment({ id: '2', user_relationship: 'contributing' })
    const triage = makeCommitment({ id: '3', resolved_owner: null, suggested_owner: null })
    const watching = makeCommitment({ id: '4', user_relationship: 'watching' })

    const result = filterMineAndTriage([mine, contributing, triage, watching], userName, userEmail)
    expect(result.map(c => c.id)).toEqual(['1', '2', '3'])
  })

  it('returns empty array when all are watching', () => {
    const c1 = makeCommitment({ id: '1', user_relationship: 'watching' })
    const c2 = makeCommitment({ id: '2', user_relationship: 'watching' })
    expect(filterMineAndTriage([c1, c2], userName, userEmail)).toEqual([])
  })
})

describe('filterMine', () => {
  it('returns only mine + triage commitments (Active tab)', () => {
    const mine = makeCommitment({ id: '1', user_relationship: 'mine' })
    const contributing = makeCommitment({ id: '2', user_relationship: 'contributing' })
    const triage = makeCommitment({ id: '3', resolved_owner: null, suggested_owner: null })
    const watching = makeCommitment({ id: '4', user_relationship: 'watching' })

    const result = filterMine([mine, contributing, triage, watching], userName, userEmail)
    expect(result.map(c => c.id)).toEqual(['1', '3'])
  })
})

describe('filterOthers', () => {
  it('returns only watching commitments', () => {
    const mine = makeCommitment({ id: '1', user_relationship: 'mine' })
    const triage = makeCommitment({ id: '2', resolved_owner: null, suggested_owner: null })
    const watching = makeCommitment({ id: '3', user_relationship: 'watching' })

    const result = filterOthers([mine, triage, watching], userName, userEmail)
    expect(result.map(c => c.id)).toEqual(['3'])
  })
})
