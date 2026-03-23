import { describe, it, expect } from 'vitest'
import type { CommitmentRead } from '../types'
import { buildDashboardGroups } from '../utils/grouping'

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

describe('buildDashboardGroups', () => {
  it('returns context groups when commitments have context_ids', () => {
    const contextMap = new Map([
      ['ctx-1', 'Acme Corp'],
      ['ctx-2', 'Project Beta'],
    ])
    const commitments = [
      makeCommitment({ id: 'c1', context_id: 'ctx-1', context_type: 'email' }),
      makeCommitment({ id: 'c2', context_id: 'ctx-1', context_type: 'slack' }),
      makeCommitment({ id: 'c3', context_id: 'ctx-2', context_type: 'meeting' }),
    ]

    const result = buildDashboardGroups(commitments, contextMap)
    expect(result.mode).toBe('context')
    expect(result.groups).toHaveLength(2)
    expect(result.groups[0].label).toBe('Acme Corp')
    expect(result.groups[0].commitments).toHaveLength(2)
    expect(result.groups[1].label).toBe('Project Beta')
    expect(result.groups[1].commitments).toHaveLength(1)
    expect(result.ungrouped).toHaveLength(0)
  })

  it('falls back to source grouping when no commitments have context_ids', () => {
    const contextMap = new Map<string, string>()
    const commitments = [
      makeCommitment({ id: 'c1', context_type: 'email' }),
      makeCommitment({ id: 'c2', context_type: 'slack' }),
    ]

    const result = buildDashboardGroups(commitments, contextMap)
    expect(result.mode).toBe('source')
    expect(result.groups).toHaveLength(2)
    expect(result.groups.some(g => g.label === 'From your email')).toBe(true)
    expect(result.groups.some(g => g.label === 'From Slack today')).toBe(true)
  })

  it('includes ungrouped commitments when some lack context_id', () => {
    const contextMap = new Map([['ctx-1', 'Acme Corp']])
    const commitments = [
      makeCommitment({ id: 'c1', context_id: 'ctx-1' }),
      makeCommitment({ id: 'c2', context_id: null, context_type: 'email' }),
    ]

    const result = buildDashboardGroups(commitments, contextMap)
    expect(result.mode).toBe('context')
    expect(result.groups).toHaveLength(1)
    expect(result.groups[0].label).toBe('Acme Corp')
    expect(result.ungrouped).toHaveLength(1)
    expect(result.ungrouped[0].id).toBe('c2')
  })

  it('uses context mode when at least one commitment has context_id', () => {
    const contextMap = new Map([['ctx-1', 'Acme Corp']])
    const commitments = [
      makeCommitment({ id: 'c1', context_id: 'ctx-1' }),
      makeCommitment({ id: 'c2' }),
      makeCommitment({ id: 'c3' }),
    ]

    const result = buildDashboardGroups(commitments, contextMap)
    expect(result.mode).toBe('context')
    expect(result.ungrouped).toHaveLength(2)
  })

  it('sorts context groups by commitment count descending', () => {
    const contextMap = new Map([
      ['ctx-1', 'Small'],
      ['ctx-2', 'Big'],
    ])
    const commitments = [
      makeCommitment({ id: 'c1', context_id: 'ctx-1' }),
      makeCommitment({ id: 'c2', context_id: 'ctx-2' }),
      makeCommitment({ id: 'c3', context_id: 'ctx-2' }),
      makeCommitment({ id: 'c4', context_id: 'ctx-2' }),
    ]

    const result = buildDashboardGroups(commitments, contextMap)
    expect(result.groups[0].label).toBe('Big')
    expect(result.groups[1].label).toBe('Small')
  })

  it('returns empty groups for empty commitments', () => {
    const result = buildDashboardGroups([], new Map())
    expect(result.groups).toHaveLength(0)
    expect(result.ungrouped).toHaveLength(0)
  })

  it('falls back to context_id prefix when context name is not in map', () => {
    const contextMap = new Map<string, string>()
    const commitments = [
      makeCommitment({ id: 'c1', context_id: 'abcdef12-3456-7890' }),
    ]

    const result = buildDashboardGroups(commitments, contextMap)
    expect(result.mode).toBe('context')
    expect(result.groups[0].label).toBe('abcdef12')
  })
})
