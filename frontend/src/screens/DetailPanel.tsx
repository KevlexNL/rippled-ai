import { useQuery, useQueryClient } from '@tanstack/react-query'
import type { CommitmentRead, CommitmentSignalRead } from '../types'
import { getSignals } from '../api/commitments'
import { patchCommitment } from '../api/commitments'

// ─── Helpers ──────────────────────────────────────────────────────────────

function confidenceLabel(score: string | null | undefined): string {
  if (!score) return 'Some uncertainty'
  const n = parseFloat(score)
  if (n >= 0.85) return 'High confidence'
  if (n >= 0.70) return 'Medium confidence'
  return 'Some uncertainty'
}

function badgeFromState(c: CommitmentRead): { label: string; classes: string } {
  const state = c.lifecycle_state
  if (state === 'delivered') return { label: 'Delivered', classes: 'bg-[#f0fdf4] text-[#15803d]' }
  if (state === 'discarded' || state === 'closed') return { label: 'Dismissed', classes: 'bg-[#f9fafb] text-[#6b7280] border border-[#e8e8e6]' }

  const conf = c.confidence_commitment ? parseFloat(c.confidence_commitment) : 0
  if (conf >= 0.85) return { label: 'At risk', classes: 'bg-[#fee2e2] text-[#991b1b]' }
  if (conf >= 0.70) return { label: 'Needs review', classes: 'bg-[#fef3c7] text-[#92400e]' }
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

  async function handleConfirm() {
    if (!commitment) return
    await patchCommitment(commitment.id, { lifecycle_state: 'delivered' })
    queryClient.invalidateQueries({ queryKey: ['surface'] })
    queryClient.invalidateQueries({ queryKey: ['commitments'] })
    onAction?.()
    onClose()
  }

  async function handleDismiss() {
    if (!commitment) return
    await patchCommitment(commitment.id, { lifecycle_state: 'discarded' })
    queryClient.invalidateQueries({ queryKey: ['surface'] })
    queryClient.invalidateQueries({ queryKey: ['commitments'] })
    onAction?.()
    onClose()
  }

  const badge = commitment ? badgeFromState(commitment) : { label: '', classes: '' }
  const person = commitment?.resolved_owner || commitment?.suggested_owner || null

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
          {commitment.context_id && contextRelated.length > 0 && (
            <div className="px-5 py-3 border-b border-[#f0f0ef]">
              <div className="text-[11px] font-semibold uppercase tracking-wide text-[#9ca3af] mb-1.5">Context</div>
              <div className="text-[12px] text-[#6b7280] mb-2">
                {contextRelated.length + 1} related commitment{contextRelated.length + 1 !== 1 ? 's' : ''} in this context
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

          {/* Related person */}
          <div className="px-5 py-3 border-b border-[#f0f0ef]">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-[#9ca3af] mb-1.5">Related</div>
            <div className="text-[13px] text-[#191919]">
              {person ? (
                <>{person} <span className="text-[#9ca3af]">· {sourceLabel(commitment.context_type)}</span></>
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
              <div className="text-[11px] font-semibold uppercase tracking-wide text-[#9ca3af] mb-1.5">Suggested next move</div>
              <div className="text-[13px] text-[#191919] leading-relaxed">{commitment.suggested_next_step}</div>
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
