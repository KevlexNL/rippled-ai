/**
 * Confidence-aware suggestion language utilities.
 *
 * Renders commitment fields with tentative language scaled to confidence:
 * - High confidence (>= 0.85): more direct ("Likely owner: Kevin")
 * - Medium confidence (>= 0.70): moderate hedging ("May be owned by Kevin")
 * - Low confidence (< 0.70): full hedging ("Possibly owned by Kevin")
 *
 * Suggested (AI-inferred) values use tentative language.
 * Confirmed (user-set) values display directly.
 */

/** Whether the owner was explicitly confirmed (resolved) vs AI-suggested. */
export function isOwnerConfirmed(
  resolvedOwner: string | null | undefined,
  suggestedOwner: string | null | undefined,
): boolean {
  return !!resolvedOwner && resolvedOwner !== suggestedOwner
}

/** Format an owner name with appropriate tentative language. */
export function ownerLabel(
  resolvedOwner: string | null | undefined,
  suggestedOwner: string | null | undefined,
  confidence: string | null | undefined,
  senderFallback?: string | null,
): { text: string; isSuggested: boolean } | null {
  const raw = resolvedOwner || suggestedOwner || null
  if (!raw) return null

  // Resolve "recipient" to sender fallback
  const name = raw.toLowerCase() === 'recipient' ? (senderFallback || 'You') : raw

  // If resolved_owner is set and differs from suggested, it's user-confirmed
  if (resolvedOwner && resolvedOwner !== suggestedOwner) {
    return { text: name, isSuggested: false }
  }

  // AI-suggested: apply confidence-scaled hedging
  const conf = confidence ? parseFloat(confidence) : 0
  if (conf >= 0.85) {
    return { text: `Likely ${name}`, isSuggested: true }
  }
  if (conf >= 0.70) {
    return { text: `May be ${name}`, isSuggested: true }
  }
  return { text: `Possibly ${name}`, isSuggested: true }
}

/** Confidence label with tentative language. */
export function confidenceLabel(score: string | null | undefined): string {
  if (!score) return 'Possible commitment'
  const n = parseFloat(score)
  if (n >= 0.85) return 'Likely a commitment'
  if (n >= 0.70) return 'May be a commitment'
  return 'Possible commitment'
}

/** Format a deadline with tentative language when not user-confirmed. */
export function deadlinePrefix(
  resolvedDeadline: string | null | undefined,
  lifecycleState: string | null | undefined,
): 'suggested' | 'confirmed' {
  // User has confirmed the commitment itself
  if (lifecycleState === 'active' || lifecycleState === 'confirmed') {
    return 'confirmed'
  }
  return 'suggested'
}

/** Get the tentative deadline text for "due in X days" style. */
export function dueDateLabel(
  days: number,
  deadlineType: 'suggested' | 'confirmed',
): string {
  if (deadlineType === 'confirmed') {
    const d = Math.ceil(days)
    return `Due in ${d} day${d !== 1 ? 's' : ''}`
  }
  const d = Math.ceil(days)
  return `Seems due in ~${d} day${d !== 1 ? 's' : ''}`
}

/** Get the tentative overdue text. */
export function overdueLabel(
  days: number,
  deadlineType: 'suggested' | 'confirmed',
): string {
  const absDays = Math.round(Math.abs(days))
  if (deadlineType === 'confirmed') {
    return `Overdue · ${absDays} day${absDays !== 1 ? 's' : ''}`
  }
  return `Likely overdue · ~${absDays} day${absDays !== 1 ? 's' : ''}`
}
