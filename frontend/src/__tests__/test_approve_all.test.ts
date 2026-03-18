import { describe, it, expect, vi, beforeEach } from 'vitest'
import type { CommitmentRead } from '../types'

// Mock the commitments API module
vi.mock('../api/commitments', () => ({
  patchCommitment: vi.fn(),
}))

import { approveAll, revertApproval } from '../utils/approveAll'
import { patchCommitment } from '../api/commitments'

const mockPatch = patchCommitment as ReturnType<typeof vi.fn>

function makeCommitment(
  id: string,
  lifecycle_state: CommitmentRead['lifecycle_state']
): CommitmentRead {
  return {
    id,
    user_id: 'user-1',
    version: 1,
    title: `Commitment ${id}`,
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
    lifecycle_state,
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
  }
}

beforeEach(() => {
  mockPatch.mockClear()
  mockPatch.mockResolvedValue({ id: 'patched' })
})

describe('approveAll', () => {
  it('1. only patches proposed commitments, skips active and delivered', async () => {
    const proposed1 = makeCommitment('p1', 'proposed')
    const proposed2 = makeCommitment('p2', 'proposed')
    const active = makeCommitment('a1', 'active')
    const delivered = makeCommitment('d1', 'delivered')
    const closed = makeCommitment('c1', 'closed')

    const undoBuffer = await approveAll([proposed1, proposed2, active, delivered, closed])

    // Should only patch the 2 proposed ones
    expect(mockPatch).toHaveBeenCalledTimes(2)
    expect(mockPatch).toHaveBeenCalledWith('p1', { lifecycle_state: 'active' })
    expect(mockPatch).toHaveBeenCalledWith('p2', { lifecycle_state: 'active' })

    // Active/delivered/closed are NOT patched
    const calledIds = mockPatch.mock.calls.map((call: unknown[]) => call[0])
    expect(calledIds).not.toContain('a1')
    expect(calledIds).not.toContain('d1')
    expect(calledIds).not.toContain('c1')

    // Undo buffer contains only proposed items
    expect(undoBuffer).toHaveLength(2)
  })

  it('2. undo buffer is populated with correct ids and previous states', async () => {
    const p1 = makeCommitment('p1', 'proposed')
    const p2 = makeCommitment('p2', 'proposed')

    const undoBuffer = await approveAll([p1, p2])

    expect(undoBuffer).toHaveLength(2)
    expect(undoBuffer[0]).toEqual({ id: 'p1', previousState: 'proposed' })
    expect(undoBuffer[1]).toEqual({ id: 'p2', previousState: 'proposed' })
  })

  it('returns empty undo buffer when no proposed commitments', async () => {
    const active = makeCommitment('a1', 'active')
    const undoBuffer = await approveAll([active])
    expect(undoBuffer).toHaveLength(0)
    expect(mockPatch).not.toHaveBeenCalled()
  })

  it('returns empty undo buffer for empty array', async () => {
    const undoBuffer = await approveAll([])
    expect(undoBuffer).toHaveLength(0)
    expect(mockPatch).not.toHaveBeenCalled()
  })
})

describe('revertApproval', () => {
  it('3. patches each entry back to its previous state', async () => {
    const undoBuffer = [
      { id: 'p1', previousState: 'proposed' },
      { id: 'p2', previousState: 'proposed' },
    ]

    await revertApproval(undoBuffer)

    expect(mockPatch).toHaveBeenCalledTimes(2)
    expect(mockPatch).toHaveBeenCalledWith('p1', { lifecycle_state: 'proposed' })
    expect(mockPatch).toHaveBeenCalledWith('p2', { lifecycle_state: 'proposed' })
  })

  it('does nothing with empty undo buffer', async () => {
    await revertApproval([])
    expect(mockPatch).not.toHaveBeenCalled()
  })

  it('can revert mixed previous states', async () => {
    const undoBuffer = [
      { id: 'x1', previousState: 'proposed' },
      { id: 'x2', previousState: 'needs_clarification' },
    ]

    await revertApproval(undoBuffer)

    expect(mockPatch).toHaveBeenCalledWith('x1', { lifecycle_state: 'proposed' })
    expect(mockPatch).toHaveBeenCalledWith('x2', { lifecycle_state: 'needs_clarification' })
  })
})
