/**
 * Tests for LogCommitmentModal component.
 *
 * Verifies:
 * - Empty description submit shows validation error (not silent exit)
 * - Auth errors show actionable message
 * - Successful submit shows success banner
 * - Error is rendered above the form fields (visible without scrolling)
 */
import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import LogCommitmentModal from '../screens/LogCommitmentModal'

// Polyfill scrollIntoView for jsdom
beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn()
})

// Mock commitments API
vi.mock('../api/commitments', () => ({
  postCommitment: vi.fn(),
}))

import { postCommitment } from '../api/commitments'
const mockPostCommitment = vi.mocked(postCommitment)

describe('LogCommitmentModal', () => {
  const onCancel = vi.fn()
  const onSuccess = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('disables submit button when description is empty', () => {
    render(<LogCommitmentModal onCancel={onCancel} onSuccess={onSuccess} />)
    const submitBtn = screen.getByRole('button', { name: /log commitment/i })
    expect((submitBtn as HTMLButtonElement).disabled).toBe(true)
  })

  it('disables submit button when description is whitespace only', async () => {
    const user = userEvent.setup()
    render(<LogCommitmentModal onCancel={onCancel} onSuccess={onSuccess} />)

    const textarea = screen.getByPlaceholderText(/describe the commitment/i)
    await user.type(textarea, '   ')

    const submitBtn = screen.getByRole('button', { name: /log commitment/i })
    expect((submitBtn as HTMLButtonElement).disabled).toBe(true)
  })

  it('shows auth error with actionable message when not authenticated', async () => {
    const user = userEvent.setup()
    mockPostCommitment.mockRejectedValueOnce(new Error('Not authenticated'))

    render(<LogCommitmentModal onCancel={onCancel} onSuccess={onSuccess} />)

    const textarea = screen.getByPlaceholderText(/describe the commitment/i)
    await user.type(textarea, 'Deliver the report by Friday')

    const submitBtn = screen.getByRole('button', { name: /log commitment/i })
    await user.click(submitBtn)

    await waitFor(() => {
      // Should show user-friendly auth error, not raw "Not authenticated"
      screen.getByText(/session expired/i)
    })
  })

  it('shows generic API error for non-auth failures', async () => {
    const user = userEvent.setup()
    mockPostCommitment.mockRejectedValueOnce(new Error('API error 500: /api/v1/commitments'))

    render(<LogCommitmentModal onCancel={onCancel} onSuccess={onSuccess} />)

    const textarea = screen.getByPlaceholderText(/describe the commitment/i)
    await user.type(textarea, 'Deliver the report by Friday')

    const submitBtn = screen.getByRole('button', { name: /log commitment/i })
    await user.click(submitBtn)

    await waitFor(() => {
      screen.getByText(/API error 500/i)
    })
  })

  it('shows success banner after successful submit', async () => {
    const user = userEvent.setup()
    mockPostCommitment.mockResolvedValueOnce({} as any)

    render(<LogCommitmentModal onCancel={onCancel} onSuccess={onSuccess} />)

    const textarea = screen.getByPlaceholderText(/describe the commitment/i)
    await user.type(textarea, 'Deliver the report by Friday')

    const submitBtn = screen.getByRole('button', { name: /log commitment/i })
    await user.click(submitBtn)

    await waitFor(() => {
      screen.getByText(/commitment logged/i)
    })
  })

  it('renders error above form fields in DOM order', async () => {
    const user = userEvent.setup()
    mockPostCommitment.mockRejectedValueOnce(new Error('Not authenticated'))

    render(<LogCommitmentModal onCancel={onCancel} onSuccess={onSuccess} />)

    const textarea = screen.getByPlaceholderText(/describe the commitment/i)
    await user.type(textarea, 'Deliver the report by Friday')

    const submitBtn = screen.getByRole('button', { name: /log commitment/i })
    await user.click(submitBtn)

    await waitFor(() => {
      const errorEl = screen.getByTestId('modal-error')
      expect(errorEl).toBeTruthy()
      // Error should appear before the fields div in DOM order
      const card = errorEl.closest('[data-testid="modal-card"]')
      expect(card).toBeTruthy()
      const children = Array.from(card!.children)
      const errorIdx = children.indexOf(errorEl)
      const fieldsEl = card!.querySelector('[data-testid="modal-fields"]')
      const fieldsIdx = children.indexOf(fieldsEl as Element)
      expect(errorIdx).toBeLessThan(fieldsIdx)
    })
  })

  it('scrolls error into view when error appears', async () => {
    const user = userEvent.setup()
    mockPostCommitment.mockRejectedValueOnce(new Error('API error 500: /api/v1/commitments'))

    render(<LogCommitmentModal onCancel={onCancel} onSuccess={onSuccess} />)

    const textarea = screen.getByPlaceholderText(/describe the commitment/i)
    await user.type(textarea, 'Deliver the report by Friday')

    const submitBtn = screen.getByRole('button', { name: /log commitment/i })
    await user.click(submitBtn)

    await waitFor(() => {
      screen.getByTestId('modal-error')
      expect(Element.prototype.scrollIntoView).toHaveBeenCalled()
    })
  })
})
