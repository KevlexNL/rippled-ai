import { describe, it, expect } from 'vitest'
import type { CommitmentRead } from '../types'
import {
  dedupById,
  groupByContextType,
  getGroupStatusColor,
  getSourceLabel,
} from '../utils/grouping'

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

describe('dedupById', () => {
  it('3. removes duplicate commitments with the same id', () => {
    const c1 = makeCommitment({ id: 'abc', title: 'First' })
    const c2 = makeCommitment({ id: 'abc', title: 'Duplicate' })
    const c3 = makeCommitment({ id: 'xyz', title: 'Unique' })

    const result = dedupById([c1, c2, c3])
    expect(result).toHaveLength(2)
    expect(result[0].id).toBe('abc')
    expect(result[0].title).toBe('First') // first occurrence wins
    expect(result[1].id).toBe('xyz')
  })

  it('returns empty array when given empty input', () => {
    expect(dedupById([])).toEqual([])
  })

  it('returns all items when no duplicates', () => {
    const commitments = [
      makeCommitment({ id: 'a' }),
      makeCommitment({ id: 'b' }),
      makeCommitment({ id: 'c' }),
    ]
    expect(dedupById(commitments)).toHaveLength(3)
  })
})

describe('groupByContextType', () => {
  it('1. groups commitments by context_type correctly', () => {
    const meeting = makeCommitment({ id: 'm1', context_type: 'meeting' })
    const slack = makeCommitment({ id: 's1', context_type: 'slack' })
    const email = makeCommitment({ id: 'e1', context_type: 'email' })

    const groups = groupByContextType([meeting, slack, email])
    expect(groups.meeting).toHaveLength(1)
    expect(groups.meeting[0].id).toBe('m1')
    expect(groups.slack).toHaveLength(1)
    expect(groups.slack[0].id).toBe('s1')
    expect(groups.email).toHaveLength(1)
    expect(groups.email[0].id).toBe('e1')
  })

  it('2. null context_type is assigned to unknown group', () => {
    const c = makeCommitment({ id: 'u1', context_type: null })
    const groups = groupByContextType([c])
    expect(groups.unknown).toHaveLength(1)
    expect(groups.unknown[0].id).toBe('u1')
    expect(groups.meeting).toHaveLength(0)
    expect(groups.slack).toHaveLength(0)
    expect(groups.email).toHaveLength(0)
  })

  it('all groups start empty', () => {
    const groups = groupByContextType([])
    expect(groups.meeting).toHaveLength(0)
    expect(groups.slack).toHaveLength(0)
    expect(groups.email).toHaveLength(0)
    expect(groups.unknown).toHaveLength(0)
  })

  it('handles multiple items in same group', () => {
    const m1 = makeCommitment({ id: 'm1', context_type: 'meeting' })
    const m2 = makeCommitment({ id: 'm2', context_type: 'meeting' })
    const groups = groupByContextType([m1, m2])
    expect(groups.meeting).toHaveLength(2)
  })
})

describe('getGroupStatusColor', () => {
  it('4. returns worst (red) status for a group with mixed colors', () => {
    const red = makeCommitment({ id: 'r1', lifecycle_state: 'needs_clarification' })
    const yellow = makeCommitment({ id: 'y1', lifecycle_state: 'proposed' })
    const green = makeCommitment({ id: 'g1', lifecycle_state: 'active', confidence_commitment: '0.9' })
    expect(getGroupStatusColor([red, yellow, green])).toBe('red')
  })

  it('returns yellow when no red but has yellow', () => {
    const yellow = makeCommitment({ id: 'y1', lifecycle_state: 'proposed' })
    const green = makeCommitment({ id: 'g1', lifecycle_state: 'active', confidence_commitment: '0.9' })
    expect(getGroupStatusColor([yellow, green])).toBe('yellow')
  })

  it('returns green when all are green', () => {
    const g1 = makeCommitment({ id: 'g1', lifecycle_state: 'active', confidence_commitment: '0.9' })
    const g2 = makeCommitment({ id: 'g2', lifecycle_state: 'closed', confidence_commitment: null })
    expect(getGroupStatusColor([g1, g2])).toBe('green')
  })
})

describe('getSourceLabel', () => {
  it('5. returns correct label for meeting', () => {
    expect(getSourceLabel('meeting')).toBe("From today's meeting")
  })

  it('returns correct label for slack', () => {
    expect(getSourceLabel('slack')).toBe('From Slack today')
  })

  it('returns correct label for email', () => {
    expect(getSourceLabel('email')).toBe('From your email')
  })

  it('returns Other for unknown source type', () => {
    expect(getSourceLabel('unknown')).toBe('Other')
  })

  it('returns Other for unrecognized source type', () => {
    expect(getSourceLabel('discord')).toBe('Other')
  })
})
