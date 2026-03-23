import type { CommitmentRead } from '../types'
import { getStatusColor, getGroupStatusColor } from '../types'

export type SourceType = 'meeting' | 'slack' | 'email' | 'unknown'

export const SOURCE_LABELS: Record<SourceType, string> = {
  meeting: "From today's meeting",
  slack: 'From Slack today',
  email: 'From your email',
  unknown: 'Other',
}

export function getSourceLabel(sourceType: string): string {
  return SOURCE_LABELS[sourceType as SourceType] ?? 'Other'
}

/**
 * Deduplicate commitments by id, keeping the first occurrence.
 */
export function dedupById(commitments: CommitmentRead[]): CommitmentRead[] {
  const seen = new Set<string>()
  return commitments.filter((c) => {
    if (seen.has(c.id)) return false
    seen.add(c.id)
    return true
  })
}

/**
 * Group commitments by context_type. null context_type maps to 'unknown'.
 */
export function groupByContextType(
  commitments: CommitmentRead[]
): Record<SourceType, CommitmentRead[]> {
  const groups: Record<SourceType, CommitmentRead[]> = {
    meeting: [],
    slack: [],
    email: [],
    unknown: [],
  }

  for (const c of commitments) {
    const key = (c.context_type as SourceType) ?? 'unknown'
    if (key in groups) {
      groups[key].push(c)
    } else {
      groups.unknown.push(c)
    }
  }

  return groups
}

/**
 * Group commitments by target_entity. null target_entity maps to 'Other'.
 */
export function groupByTargetEntity(
  commitments: CommitmentRead[]
): Record<string, CommitmentRead[]> {
  const groups: Record<string, CommitmentRead[]> = {}

  for (const c of commitments) {
    const key = c.target_entity ?? 'Other'
    if (!groups[key]) groups[key] = []
    groups[key].push(c)
  }

  return groups
}

/**
 * Group commitments by context_id. Returns groups keyed by context_id,
 * ungrouped commitments (no context_id), and a flag indicating whether
 * any commitments have a context_id.
 */
export function groupByContextId(
  commitments: CommitmentRead[]
): {
  groups: Record<string, CommitmentRead[]>
  ungrouped: CommitmentRead[]
  hasContexts: boolean
} {
  const groups: Record<string, CommitmentRead[]> = {}
  const ungrouped: CommitmentRead[] = []
  let hasContexts = false

  for (const c of commitments) {
    if (c.context_id) {
      hasContexts = true
      if (!groups[c.context_id]) groups[c.context_id] = []
      groups[c.context_id].push(c)
    } else {
      ungrouped.push(c)
    }
  }

  return { groups, ungrouped, hasContexts }
}

export interface DashboardGroup {
  key: string
  label: string
  commitments: CommitmentRead[]
}

export interface DashboardGroupResult {
  mode: 'context' | 'source'
  groups: DashboardGroup[]
  ungrouped: CommitmentRead[]
}

/**
 * Build dashboard display groups. Uses context grouping when any commitment
 * has a context_id assigned; falls back to source-type grouping otherwise.
 */
export function buildDashboardGroups(
  commitments: CommitmentRead[],
  contextMap: Map<string, string>,
): DashboardGroupResult {
  const hasAnyContext = commitments.some((c) => c.context_id)

  if (hasAnyContext) {
    const { groups: ctxGroups, ungrouped } = groupByContextId(commitments)
    const groups: DashboardGroup[] = Object.entries(ctxGroups)
      .map(([ctxId, items]) => ({
        key: ctxId,
        label: contextMap.get(ctxId) ?? ctxId.slice(0, 8),
        commitments: items,
      }))
      .sort((a, b) => b.commitments.length - a.commitments.length)

    return { mode: 'context', groups, ungrouped }
  }

  // Fallback: group by source type
  const sourceGroups = groupByContextType(commitments)
  const sourceTypes: SourceType[] = ['meeting', 'slack', 'email', 'unknown']
  const groups: DashboardGroup[] = sourceTypes
    .filter((st) => sourceGroups[st].length > 0)
    .map((st) => ({
      key: st,
      label: SOURCE_LABELS[st],
      commitments: sourceGroups[st],
    }))

  return { mode: 'source', groups, ungrouped: [] }
}

/**
 * Compute the worst status color for a group of commitments.
 * Re-exports getGroupStatusColor for convenience.
 */
export { getStatusColor, getGroupStatusColor }
