import { describe, it, expect } from 'vitest'
import {
  isOwnerConfirmed,
  ownerLabel,
  confidenceLabel,
  deadlinePrefix,
  dueDateLabel,
  overdueLabel,
} from '../utils/suggestionLanguage'

describe('isOwnerConfirmed', () => {
  it('returns true when resolved_owner is set and differs from suggested', () => {
    expect(isOwnerConfirmed('Kevin', 'Alice')).toBe(true)
  })

  it('returns false when resolved_owner equals suggested_owner', () => {
    expect(isOwnerConfirmed('Kevin', 'Kevin')).toBe(false)
  })

  it('returns false when resolved_owner is null', () => {
    expect(isOwnerConfirmed(null, 'Kevin')).toBe(false)
  })

  it('returns false when both are null', () => {
    expect(isOwnerConfirmed(null, null)).toBe(false)
  })
})

describe('ownerLabel', () => {
  it('returns null when no owner available', () => {
    expect(ownerLabel(null, null, '0.90')).toBeNull()
  })

  it('shows direct name when user-confirmed (resolved differs from suggested)', () => {
    const result = ownerLabel('Kevin', 'Alice', '0.90')
    expect(result).toEqual({ text: 'Kevin', isSuggested: false })
  })

  it('shows "Looks like" prefix for high confidence suggested owner', () => {
    const result = ownerLabel(null, 'Alice', '0.90')
    expect(result).toEqual({ text: 'Looks like Alice', isSuggested: true })
  })

  it('shows "Seems like" prefix for medium confidence suggested owner', () => {
    const result = ownerLabel(null, 'Alice', '0.72')
    expect(result).toEqual({ text: 'Seems like Alice', isSuggested: true })
  })

  it('shows "Possibly" prefix for low confidence suggested owner', () => {
    const result = ownerLabel(null, 'Alice', '0.50')
    expect(result).toEqual({ text: 'Possibly Alice', isSuggested: true })
  })

  it('resolves "recipient" to sender fallback', () => {
    const result = ownerLabel(null, 'recipient', '0.90', 'Bob')
    expect(result).toEqual({ text: 'Looks like Bob', isSuggested: true })
  })

  it('resolves "recipient" to "You" when no fallback', () => {
    const result = ownerLabel(null, 'Recipient', '0.90')
    expect(result).toEqual({ text: 'Looks like You', isSuggested: true })
  })

  it('treats resolved_owner same as suggested when they match (AI-suggested, not user-confirmed)', () => {
    const result = ownerLabel('Alice', 'Alice', '0.80')
    expect(result!.isSuggested).toBe(true)
    expect(result!.text).toBe('Seems like Alice')
  })

  it('handles null confidence as low', () => {
    const result = ownerLabel(null, 'Alice', null)
    expect(result).toEqual({ text: 'Possibly Alice', isSuggested: true })
  })
})

describe('confidenceLabel', () => {
  it('returns tentative label for high confidence', () => {
    expect(confidenceLabel('0.90')).toBe('Looks like a commitment')
  })

  it('returns tentative label for medium confidence', () => {
    expect(confidenceLabel('0.75')).toBe('Seems like a commitment')
  })

  it('returns tentative label for low confidence', () => {
    expect(confidenceLabel('0.50')).toBe('Possibly a commitment')
  })

  it('returns tentative label for null', () => {
    expect(confidenceLabel(null)).toBe('Possibly a commitment')
  })

  it('returns tentative label for undefined', () => {
    expect(confidenceLabel(undefined)).toBe('Possibly a commitment')
  })
})

describe('deadlinePrefix', () => {
  it('returns confirmed when lifecycle is active', () => {
    expect(deadlinePrefix('2026-04-10', 'active')).toBe('confirmed')
  })

  it('returns confirmed when lifecycle is confirmed', () => {
    expect(deadlinePrefix('2026-04-10', 'confirmed')).toBe('confirmed')
  })

  it('returns suggested when lifecycle is proposed', () => {
    expect(deadlinePrefix('2026-04-10', 'proposed')).toBe('suggested')
  })

  it('returns suggested when lifecycle is null', () => {
    expect(deadlinePrefix('2026-04-10', null)).toBe('suggested')
  })
})

describe('dueDateLabel', () => {
  it('returns direct "Due in" for confirmed deadlines', () => {
    expect(dueDateLabel(2, 'confirmed')).toBe('Due in 2 days')
  })

  it('returns "Seems due" for suggested deadlines', () => {
    expect(dueDateLabel(2, 'suggested')).toBe('Seems due in ~2 days')
  })

  it('handles singular day', () => {
    expect(dueDateLabel(1, 'confirmed')).toBe('Due in 1 day')
    expect(dueDateLabel(1, 'suggested')).toBe('Seems due in ~1 day')
  })
})

describe('overdueLabel', () => {
  it('returns direct "Overdue" for confirmed deadlines', () => {
    expect(overdueLabel(-3, 'confirmed')).toBe('Overdue · 3 days')
  })

  it('returns "Likely overdue" for suggested deadlines', () => {
    expect(overdueLabel(-3, 'suggested')).toBe('Likely overdue · ~3 days')
  })

  it('handles singular day', () => {
    expect(overdueLabel(-1, 'confirmed')).toBe('Overdue · 1 day')
    expect(overdueLabel(-1, 'suggested')).toBe('Likely overdue · ~1 day')
  })
})
