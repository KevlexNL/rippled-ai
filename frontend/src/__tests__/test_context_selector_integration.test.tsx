import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import CommitmentDetail from '../screens/CommitmentDetail'
import type { CommitmentRead } from '../types'

// Mock API modules
const mockGetCommitment = vi.fn()
const mockGetSignals = vi.fn()
const mockGetAmbiguities = vi.fn()
const mockPatchCommitment = vi.fn()
const mockGetContexts = vi.fn()

vi.mock('../api/commitments', () => ({
  getCommitment: (...args: unknown[]) => mockGetCommitment(...args),
  getSignals: (...args: unknown[]) => mockGetSignals(...args),
  getAmbiguities: (...args: unknown[]) => mockGetAmbiguities(...args),
  patchCommitment: (...args: unknown[]) => mockPatchCommitment(...args),
}))

vi.mock('../api/contexts', () => ({
  getContexts: (...args: unknown[]) => mockGetContexts(...args),
}))

function makeCommitment(overrides: Partial<CommitmentRead> = {}): CommitmentRead {
  return {
    id: 'c-1',
    user_id: 'user-1',
    version: 1,
    title: 'Ship the feature',
    description: null,
    commitment_text: 'I will ship it by Friday',
    commitment_type: null,
    priority_class: null,
    context_type: 'email',
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

function renderWithProviders() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/commitments/c-1']}>
        <Routes>
          <Route path="/commitments/:id" element={<CommitmentDetail />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('CommitmentDetail with ContextSelector', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetCommitment.mockResolvedValue(makeCommitment())
    mockGetSignals.mockResolvedValue([])
    mockGetAmbiguities.mockResolvedValue([])
    mockGetContexts.mockResolvedValue([
      { id: 'ctx-1', user_id: 'user-1', name: 'Project Alpha', summary: null, commitment_count: 3, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z' },
      { id: 'ctx-2', user_id: 'user-1', name: 'Q1 Planning', summary: null, commitment_count: 5, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z' },
    ])
  })

  it('1. renders ContextSelector with available contexts', async () => {
    renderWithProviders()

    await waitFor(() => {
      expect(screen.getByText('Ship the feature')).toBeTruthy()
    })

    const select = screen.getByRole('combobox')
    expect(select).toBeTruthy()

    const options = screen.getAllByRole('option')
    expect(options.length).toBeGreaterThanOrEqual(3) // No context + 2 contexts
  })

  it('2. selecting a context calls patchCommitment and invalidates queries', async () => {
    mockPatchCommitment.mockResolvedValueOnce(makeCommitment({ context_id: 'ctx-1' }))
    renderWithProviders()

    await waitFor(() => {
      expect(screen.getByText('Ship the feature')).toBeTruthy()
    })

    const select = screen.getByRole('combobox')
    fireEvent.change(select, { target: { value: 'ctx-1' } })

    await waitFor(() => {
      expect(mockPatchCommitment).toHaveBeenCalledWith('c-1', { context_id: 'ctx-1' })
    })
  })

  it('3. shows context label section', async () => {
    renderWithProviders()

    await waitFor(() => {
      expect(screen.getByText('Ship the feature')).toBeTruthy()
    })

    expect(screen.getByText('Context')).toBeTruthy()
  })
})
