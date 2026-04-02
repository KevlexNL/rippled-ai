import { useQuery, useQueryClient } from '@tanstack/react-query'
import type { CommitmentRead, CommitmentSignalRead } from '../types'
import { getSignals, patchCommitment, skipCommitment } from '../api/commitments'
import { getContexts } from '../api/contexts'
import type { CommitmentContextRead } from '../api/contexts'
import { confidenceLabel, ownerLabel } from '../utils/suggestionLanguage'

// ─── Helpers ──────────────────────────────────────────────────────────────

function badgeFromState(c: CommitmentRead): { label: string; classes: string } {
  const state = c.lifecycle_state
  if (state === 'delivered') return { label: 'Delivered', classes: 'bg-[#f0fdf4] text-[#15803d]' }
  if (state === 'discarded' || state === 'closed') return { label: 'Dismissed', classes: 'bg-[#f9fafb] text-[#6b7280] border border-[#e8e8e6]' }

  const conf = c.confidence_commitment ? parseFloat(c.confidence_commitment) : 0
  if (conf >= 0.85) return { label: 'Likely needs attention', classes: 'bg-[#fee2e2] text-[#991b1b]' }
  if (conf >= 0.65) return { label: 'May need a look', classes: 'bg-[#fef3c7] text-[#92400e]' }
  if (conf >= 0.55) return { label: 'Worth confirming', classes: 'bg-[#eff6ff] text-[#1d4ed8]' }
  return { label: 'Low signal', classes: 'bg-[#f9fafb] text-[#6b7280] border border-[#e8e8e6]' }
}

function sourceLabel(contextType: string | null | undefined): string {
  if (!contextType) return 'Unknown'
  switch (contextType) {
    case 'email': return 'Email'
    case 'slack': return 'Slack'
    case 'meeting': return 'Meetings'
    default: return contextType
  }
}

function signalRoleLabel(role: string): string {
  switch (role) {
    case 'origin': return 'Origin'
    case 'clarification': return 'Clarification'
    case 'progress': return 'Progress'
    case 'delivery': return 'Delivery'
    case 'closure': return 'Closure'
    case 'conflict': return 'Conflict'
    case 'reopening': return 'Reopening'
    default: return role
  }
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return ''
  const d = new Date(iso)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  const days = Math.floor(diff / 86400000)
  if (days === 0) return 'Today'
  if (days === 1) return 'Yesterday'
  if (days < 7) return `${days} days ago`
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

// ─── Icons ────────────────────────────────────────────────────────────────

function IconMail() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="4" width="20" height="16" rx="2" />
      <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7" />
    </svg>
  )
}

function IconHash() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="4" x2="20" y1="9" y2="9" /><line x1="4" x2="20" y1="15" y2="15" />
      <line x1="10" x2="8" y1="3" y2="21" /><line x1="16" x2="14" y1="3" y2="21" />
    </svg>
  )
}

function IconVideo() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="m22 8-6 4 6 4V8z" /><rect x="2" y="6" width="14" height="12" rx="2" />
    </svg>
  )
}

function IconCheck() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  )
}

function IconX() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" x2="6" y1="6" y2="18" />
      <line x1="6" x2="18" y1="6" y2="18" />
    </svg>
  )
}

function IconSkip() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="5 4 15 12 5 20" /><line x1="19" x2="19" y1="5" y2="19" />
    </svg>
  )
}

function IconClose() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" x2="6" y1="6" y2="18" />
      <line x1="6" x2="18" y1="6" y2="18" />
    </svg>
  )
}

// ─── DetailPanel ──────────────────────────────────────────────────────────

interface DetailPanelProps {
  commitment: CommitmentRead | null
  allCommitments?: CommitmentRead[]
  onClose: () => void
  onAction?: () => void
}

export default function DetailPanel({ commitment, allCommitments = [], onClose, onAction }: DetailPanelProps) {
  const isOpen = commitment !== null
  const queryClient = useQueryClient()

  const { data: signals } = useQuery({
    queryKey: ['signals', commitment?.id],
    queryFn: () => getSignals(commitment!.id),
    enabled: !!commitment?.id,
  })

  const { data: contexts } = useQuery<CommitmentContextRead[]>({
    queryKey: ['contexts'],
    queryFn: getContexts,
    staleTime: 60_000,
  })

  async function handleConfirm() {
    if (!commitment) return
    // Optimistic: update in both caches
    queryClient.setQueryData<CommitmentRead[]>(['surface', 'main'], (old) =>
      old?.map(c => c.id === commitment.id ? { ...c, lifecycle_state: 'active' as const } : c)
    )
    queryClient.setQueryData<CommitmentRead[]>(['commitments'], (old) =>
      old?.map(c => c.id === commitment.id ? { ...c, lifecycle_state: 'active' as const } : c)
    )
    onClose()
    onAction?.()
    await patchCommitment(commitment.id, { lifecycle_state: 'active' })
    queryClient.invalidateQueries({ queryKey: ['surface'] })
    queryClient.invalidateQueries({ queryKey: ['commitments'] })
  }

  async function handleDismiss() {
    if (!commitment) return
    // Optimistic: remove from surface, update in commitments
    queryClient.setQueryData<CommitmentRead[]>(['surface', 'main'], (old) =>
      old?.filter(c => c.id !== commitment.id)
    )
    queryClient.setQueryData<CommitmentRead[]>(['commitments'], (old) =>
      old?.filter(c => c.id !== commitment.id)
    )
    onClose()
    onAction?.()
    await patchCommitment(commitment.id, { lifecycle_state: 'discarded' })
    queryClient.invalidateQueries({ queryKey: ['surface'] })
    queryClient.invalidateQueries({ queryKey: ['commitments'] })
  }

  async function handleSkip() {
    if (!commitment) return
    // Optimistic: remove from surface cache
    queryClient.setQueryData<CommitmentRead[]>(['surface', 'main'], (old) =>
      old?.filter(c => c.id !== commitment.id)
    )
    queryClient.setQueryData<CommitmentRead[]>(['commitments'], (old) =>
      old?.map(c => c.id === commitment.id ? { ...c, skipped_at: new Date().toISOString() } : c)
    )
    onClose()
    onAction?.()
    await skipCommitment(commitment.id)
    queryClient.invalidateQueries({ queryKey: ['surface'] })
    queryClient.invalidateQueries({ queryKey: ['commitments'] })
  }

  const badge = commitment ? badgeFromState(commitment) : { label: '', classes: '' }
  const personInfo = (() => {
    if (!commitment) return null
    return ownerLabel(
      commitment.resolved_owner,
      commitment.suggested_owner,
      commitment.confidence_commitment,
      commitment.source_sender_name || commitment.counterparty_name,
    )
  })()

  // Context: find related commitments sharing the same context_id
  const contextRelated = commitment?.context_id
    ? allCommitments.filter(c => c.context_id === commitment.context_id && c.id !== commitment.id)
    : []

  return (
    <div
      className={`fixed top-0 right-0 h-full w-[400px] bg-white border-l border-[#e8e8e6] shadow-xl z-50 flex flex-col overflow-y-auto transition-transform duration-200 ease-in-out ${isOpen ? 'translate-x-0' : 'translate-x-full'}`}
    >
      {commitment && (
        <>
          {/* Header */}
          <div className="flex items-start justify-between px-5 pt-5 pb-4 border-b border-[#f0f0ef]">
            <div className="flex-1 min-w-0">
              <div className="mb-2">
                <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ${badge.classes}`}>{badge.label}</span>
              </div>
              <div className="font-semibold text-[15px] leading-snug text-[#191919]">{commitment.title}</div>
            </div>
            <button onClick={onClose} className="w-8 h-8 flex items-center justify-center text-[#9ca3af] hover:text-[#191919] hover:bg-[#f0f0ef] rounded-md transition-colors ml-3 mt-0.5 flex-shrink-0">
              <IconClose />
            </button>
          </div>

          {/* Status & confidence */}
          <div className="px-5 py-3 border-b border-[#f0f0ef]">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-[#9ca3af] mb-1.5">Status</div>
            <div className="flex items-center gap-2">
              <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ${badge.classes}`}>{badge.label}</span>
              <span className="text-[12px] text-[#6b7280]">{confidenceLabel(commitment.confidence_commitment)}</span>
            </div>
          </div>

          {/* Source origin */}
          {(commitment.source_sender_name || commitment.source_sender_email || commitment.context_type) && (
            <div className="px-5 py-3 border-b border-[#f0f0ef]">
              <div className="text-[11px] font-semibold uppercase tracking-wide text-[#9ca3af] mb-1.5">Source</div>
              <div className="flex items-center gap-2 text-[13px] text-[#191919]">
                <span className="text-[#9ca3af]">
                  {commitment.context_type === 'email' ? <IconMail /> : commitment.context_type === 'meeting' ? <IconVideo /> : commitment.context_type === 'slack' ? <IconHash /> : <IconMail />}
                </span>
                <span>{sourceLabel(commitment.context_type)}</span>
                {(commitment.source_sender_name || commitment.source_sender_email) && (
                  <>
                    <span className="text-[#d1d1cf]">·</span>
                    <span>{commitment.source_sender_name || commitment.source_sender_email}</span>
                  </>
                )}
                {(commitment.source_occurred_at || commitment.created_at) && (
                  <>
                    <span className="text-[#d1d1cf]">·</span>
                    <span className="text-[#6b7280]">{formatDate(commitment.source_occurred_at || commitment.created_at)}</span>
                  </>
                )}
              </div>
            </div>
          )}

          {/* Why surfaced */}
          {commitment.surfacing_reason && (
            <div className="px-5 py-3 border-b border-[#f0f0ef]">
              <div className="text-[11px] font-semibold uppercase tracking-wide text-[#9ca3af] mb-1.5">Why Rippled surfaced this</div>
              <div className="text-[13px] text-[#6b7280] leading-relaxed italic">{commitment.surfacing_reason}</div>
            </div>
          )}

          {/* Source signals */}
          {signals && signals.length > 0 && (
            <div className="px-5 py-3 border-b border-[#f0f0ef]">
              <div className="text-[11px] font-semibold uppercase tracking-wide text-[#9ca3af] mb-1.5">Source signals</div>
              <div className="flex flex-col gap-2">
                {signals.map((s: CommitmentSignalRead) => (
                  <div key={s.id} className="flex items-start gap-2 text-[13px] text-[#6b7280]">
                    <span className="text-[11px] text-[#9ca3af] mt-0.5 flex-shrink-0 font-medium">{signalRoleLabel(s.signal_role)}</span>
                    <span>{s.interpretation_note || '—'}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Context */}
          <div className="px-5 py-3 border-b border-[#f0f0ef]">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-[#9ca3af] mb-1.5">Context</div>
            {contexts && contexts.length > 0 ? (
              <select
                value={commitment.context_id ?? ''}
                onChange={async (e) => {
                  const newContextId = e.target.value || null
                  queryClient.setQueryData<CommitmentRead[]>(['commitments'], (old) =>
                    old?.map(c => c.id === commitment.id ? { ...c, context_id: newContextId } : c)
                  )
                  await patchCommitment(commitment.id, { context_id: newContextId })
                  queryClient.invalidateQueries({ queryKey: ['commitments'] })
                  queryClient.invalidateQueries({ queryKey: ['contexts'] })
                }}
                className="w-full text-[13px] text-[#191919] bg-[#f9f9f8] border border-[#e8e8e6] rounded-md px-2.5 py-1.5 focus:outline-none focus:border-[#191919] transition-colors"
              >
                <option value="">No context</option>
                {contexts.map((ctx) => (
                  <option key={ctx.id} value={ctx.id}>{ctx.name}</option>
                ))}
              </select>
            ) : (
              <span className="text-[12px] text-[#9ca3af]">No contexts available</span>
            )}
            {commitment.context_id && contextRelated.length > 0 && (
              <div className="mt-2">
                <div className="text-[12px] text-[#6b7280] mb-1">
                  {contextRelated.length} related commitment{contextRelated.length !== 1 ? 's' : ''}
                </div>
                <div className="flex flex-col gap-1">
                  {contextRelated.slice(0, 3).map((c) => (
                    <div key={c.id} className="text-[12px] text-[#6b7280] flex items-center gap-1.5">
                      <span className="text-[#d1d1cf]">·</span>
                      <span>{c.title}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Related person */}
          <div className="px-5 py-3 border-b border-[#f0f0ef]">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-[#9ca3af] mb-1.5">Related</div>
            <div className="text-[13px] text-[#191919]">
              {personInfo ? (
                <>
                  <span className={personInfo.isSuggested ? 'italic text-[#6b7280]' : ''}>{personInfo.text}</span>
                  {' '}<span className="text-[#9ca3af]">· {sourceLabel(commitment.context_type)}</span>
                  {personInfo.isSuggested && <span className="ml-1.5 text-[10px] text-[#9ca3af] bg-[#f5f5f4] rounded px-1 py-0.5">suggested</span>}
                </>
              ) : (
                <span className="text-[#9ca3af]">—</span>
              )}
            </div>
          </div>

          {/* Description */}
          {commitment.description && (
            <div className="px-5 py-3 border-b border-[#f0f0ef]">
              <div className="text-[11px] font-semibold uppercase tracking-wide text-[#9ca3af] mb-1.5">Description</div>
              <div className="text-[13px] text-[#6b7280] leading-relaxed">{commitment.description}</div>
            </div>
          )}

          {/* Suggested next step */}
          {commitment.suggested_next_step && (
            <div className="px-5 py-3 flex-1">
              <div className="text-[11px] font-semibold uppercase tracking-wide text-[#9ca3af] mb-1.5">
                Suggested next move
                <span className="ml-1.5 normal-case font-normal text-[10px] bg-[#f5f5f4] rounded px-1 py-0.5">suggested</span>
              </div>
              <div className="text-[13px] text-[#6b7280] leading-relaxed italic">{commitment.suggested_next_step}</div>
            </div>
          )}

          {/* Sticky bottom action bar */}
          {commitment.lifecycle_state !== 'delivered' && commitment.lifecycle_state !== 'discarded' && commitment.lifecycle_state !== 'closed' && (
            <div className="sticky bottom-0 bg-white border-t border-[#e8e8e6] px-5 py-3 flex items-center gap-2">
              <button
                onClick={handleConfirm}
                className="flex items-center gap-1.5 bg-[#191919] text-white text-[12px] px-3.5 py-1.5 rounded-md font-medium hover:bg-[#333] transition-colors"
              >
                <IconCheck />
                Confirm
              </button>
              <button
                onClick={handleDismiss}
                className="flex items-center gap-1.5 border border-[#e8e8e6] text-[#191919] text-[12px] px-3.5 py-1.5 rounded-md font-medium hover:bg-[#f5f5f4] transition-colors"
              >
                <IconX />
                Dismiss
              </button>
              <button
                onClick={handleSkip}
                className="flex items-center gap-1.5 text-[#9ca3af] text-[12px] px-2 py-1.5 rounded-md hover:text-[#6b7280] hover:bg-[#f5f5f4] transition-colors"
                title="Can't assess — skip for now"
              >
                <IconSkip />
                Skip
              </button>
              <span onClick={onClose} className="text-[12px] text-[#9ca3af] hover:text-[#191919] cursor-pointer transition-colors ml-auto">
                Close panel
              </span>
            </div>
          )}
        </>
      )}
    </div>
  )
}
