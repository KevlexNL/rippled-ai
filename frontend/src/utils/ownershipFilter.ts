import type { CommitmentRead } from '../types'

export type OwnershipCategory = 'mine' | 'contributing' | 'watching' | 'triage'

/**
 * Case-insensitive check: does `haystack` contain any part of the user's
 * name or email?  We check each word of the name separately so
 * "Kevin" matches "Kevin Beeftink" and vice-versa.
 */
function ownerMatchesUser(
  owner: string,
  userName: string | null | undefined,
  userEmail: string | null | undefined,
): boolean {
  const lower = owner.toLowerCase()

  // Check email match
  if (userEmail && lower.includes(userEmail.toLowerCase())) return true

  // Check name match — split into words for partial matching
  if (userName) {
    const nameParts = userName.toLowerCase().split(/\s+/).filter(Boolean)
    // Match if the owner contains any name part (e.g. first name)
    // or if any name part contains the owner string
    for (const part of nameParts) {
      if (lower.includes(part) || part.includes(lower)) return true
    }
  }

  return false
}

/**
 * Classify a commitment's relationship to the current user.
 *
 * Uses server-side user_relationship when available (v3 detection).
 * Falls back to heuristic owner matching for pre-backfill commitments.
 */
export function classifyOwnership(
  c: CommitmentRead,
  userName: string | null | undefined,
  userEmail: string | null | undefined,
): OwnershipCategory {
  // Prefer server-side classification when available
  if (c.user_relationship) {
    return c.user_relationship
  }

  // Fallback: heuristic owner matching (pre-backfill commitments)
  const resolved = c.resolved_owner?.trim() || null
  const suggested = c.suggested_owner?.trim() || null

  // Check resolved_owner first
  if (resolved) {
    return ownerMatchesUser(resolved, userName, userEmail) ? 'mine' : 'watching'
  }

  // No resolved_owner — check suggested_owner
  if (suggested) {
    return ownerMatchesUser(suggested, userName, userEmail) ? 'mine' : 'watching'
  }

  // No owner at all — triage
  return 'triage'
}

/** Return commitments that are mine, contributing, or triage (default Commitments tab view). */
export function filterMineAndTriage(
  commitments: CommitmentRead[],
  userName: string | null | undefined,
  userEmail: string | null | undefined,
): CommitmentRead[] {
  return commitments.filter(c => {
    const cat = classifyOwnership(c, userName, userEmail)
    return cat === 'mine' || cat === 'contributing' || cat === 'triage'
  })
}

/** Return commitments that are mine only (Active tab view). */
export function filterMine(
  commitments: CommitmentRead[],
  userName: string | null | undefined,
  userEmail: string | null | undefined,
): CommitmentRead[] {
  return commitments.filter(c => {
    const cat = classifyOwnership(c, userName, userEmail)
    return cat === 'mine' || cat === 'triage'
  })
}

/** Return commitments that belong to others (watching). */
export function filterOthers(
  commitments: CommitmentRead[],
  userName: string | null | undefined,
  userEmail: string | null | undefined,
): CommitmentRead[] {
  return commitments.filter(c => classifyOwnership(c, userName, userEmail) === 'watching')
}
