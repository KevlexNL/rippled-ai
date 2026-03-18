import type { CommitmentRead } from '../types'

export type OwnershipCategory = 'mine' | 'triage' | 'others'

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
 * Classify a commitment as mine / triage / others relative to the current user.
 *
 * Rules (from WO-RIPPLED-LIST-FILTERING):
 *  - mine:   resolved_owner matches user, OR suggested_owner matches user
 *  - triage: resolved_owner is null/unresolved AND no suggested_owner
 *  - others: resolved_owner resolved to someone else
 */
export function classifyOwnership(
  c: CommitmentRead,
  userName: string | null | undefined,
  userEmail: string | null | undefined,
): OwnershipCategory {
  const resolved = c.resolved_owner?.trim() || null
  const suggested = c.suggested_owner?.trim() || null

  // Check resolved_owner first
  if (resolved) {
    return ownerMatchesUser(resolved, userName, userEmail) ? 'mine' : 'others'
  }

  // No resolved_owner — check suggested_owner
  if (suggested) {
    return ownerMatchesUser(suggested, userName, userEmail) ? 'mine' : 'others'
  }

  // No owner at all — triage
  return 'triage'
}

/** Return commitments that are mine or triage (default view). */
export function filterMineAndTriage(
  commitments: CommitmentRead[],
  userName: string | null | undefined,
  userEmail: string | null | undefined,
): CommitmentRead[] {
  return commitments.filter(c => {
    const cat = classifyOwnership(c, userName, userEmail)
    return cat === 'mine' || cat === 'triage'
  })
}

/** Return commitments that belong to others. */
export function filterOthers(
  commitments: CommitmentRead[],
  userName: string | null | undefined,
  userEmail: string | null | undefined,
): CommitmentRead[] {
  return commitments.filter(c => classifyOwnership(c, userName, userEmail) === 'others')
}
