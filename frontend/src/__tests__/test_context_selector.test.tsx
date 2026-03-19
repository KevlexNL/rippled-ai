import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import ContextSelector from '../components/ContextSelector'
import type { CommitmentRead } from '../types'
import type { CommitmentContextRead } from '../api/contexts'

// Mock patchCommitment
const mockPatchCommitment = vi.fn()
vi.mock('../api/commitments', () => ({
  patchCommitment: (...args: unknown[]) => mockPatchCommitment(...args),
}))

function makeCommitment(overrides: Partial<CommitmentRead> = {}): CommitmentRead {
  return {
    id: 'c-1',
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

function makeContexts(): CommitmentContextRead[] {
  return [
    {
      id: 'ctx-1',
      user_id: 'user-1',
      name: 'Project Alpha',
      summary: null,
      commitment_count: 3,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    },
    {
      id: 'ctx-2',
      user_id: 'user-1',
      name: 'Q1 Planning',
      summary: 'Quarterly planning',
      commitment_count: 5,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    },
  ]
}

describe('ContextSelector', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('1. renders "No context" when commitment has no context assigned', () => {
    const commitment = makeCommitment({ context_id: null })
    render(
      <ContextSelector
        commitment={commitment}
        contexts={makeContexts()}
        onUpdate={vi.fn()}
      />
    )

    const select = screen.getByRole('combobox') as HTMLSelectElement
    expect(select.value).toBe('')
  })

  it('2. shows current context name when context is assigned', () => {
    const commitment = makeCommitment({ context_id: 'ctx-1' })
    render(
      <ContextSelector
        commitment={commitment}
        contexts={makeContexts()}
        onUpdate={vi.fn()}
      />
    )

    const select = screen.getByRole('combobox') as HTMLSelectElement
    expect(select.value).toBe('ctx-1')
  })

  it('3. dropdown shows all available contexts plus "No context" option', () => {
    const commitment = makeCommitment()
    const contexts = makeContexts()
    render(
      <ContextSelector
        commitment={commitment}
        contexts={contexts}
        onUpdate={vi.fn()}
      />
    )

    const options = screen.getAllByRole('option')
    expect(options).toHaveLength(3) // "No context" + 2 contexts
    expect(options[0].textContent).toBe('No context')
    expect(options[1].textContent).toBe('Project Alpha')
    expect(options[2].textContent).toBe('Q1 Planning')
  })

  it('4. selecting a context calls patchCommitment with context_id', async () => {
    mockPatchCommitment.mockResolvedValueOnce({})
    const onUpdate = vi.fn()
    const commitment = makeCommitment({ context_id: null })

    render(
      <ContextSelector
        commitment={commitment}
        contexts={makeContexts()}
        onUpdate={onUpdate}
      />
    )

    const select = screen.getByRole('combobox')
    fireEvent.change(select, { target: { value: 'ctx-1' } })

    await waitFor(() => {
      expect(mockPatchCommitment).toHaveBeenCalledWith('c-1', { context_id: 'ctx-1' })
    })
  })

  it('5. clearing context calls patchCommitment with null context_id', async () => {
    mockPatchCommitment.mockResolvedValueOnce({})
    const onUpdate = vi.fn()
    const commitment = makeCommitment({ context_id: 'ctx-1' })

    render(
      <ContextSelector
        commitment={commitment}
        contexts={makeContexts()}
        onUpdate={onUpdate}
      />
    )

    const select = screen.getByRole('combobox')
    fireEvent.change(select, { target: { value: '' } })

    await waitFor(() => {
      expect(mockPatchCommitment).toHaveBeenCalledWith('c-1', { context_id: null })
    })
  })

  it('6. calls onUpdate after successful patch', async () => {
    mockPatchCommitment.mockResolvedValueOnce({})
    const onUpdate = vi.fn()
    const commitment = makeCommitment()

    render(
      <ContextSelector
        commitment={commitment}
        contexts={makeContexts()}
        onUpdate={onUpdate}
      />
    )

    const select = screen.getByRole('combobox')
    fireEvent.change(select, { target: { value: 'ctx-2' } })

    await waitFor(() => {
      expect(onUpdate).toHaveBeenCalled()
    })
  })

  it('7. shows error message when patch fails', async () => {
    mockPatchCommitment.mockRejectedValueOnce(new Error('API error 500'))
    const commitment = makeCommitment()

    render(
      <ContextSelector
        commitment={commitment}
        contexts={makeContexts()}
        onUpdate={vi.fn()}
      />
    )

    const select = screen.getByRole('combobox')
    fireEvent.change(select, { target: { value: 'ctx-1' } })

    await waitFor(() => {
      expect(screen.getByText(/failed to update context/i)).toBeTruthy()
    })
  })

  it('8. renders empty message when no contexts available', () => {
    const commitment = makeCommitment()
    render(
      <ContextSelector
        commitment={commitment}
        contexts={[]}
        onUpdate={vi.fn()}
      />
    )

    expect(screen.getByText(/no contexts available/i)).toBeTruthy()
  })
})
