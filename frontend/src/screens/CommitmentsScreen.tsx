import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { getCommitments, patchCommitment } from '../api/commitments'
import { getStats } from '../api/stats'
import type { StatsRead } from '../api/stats'
import { listSources } from '../api/sources'
import type { CommitmentRead } from '../types'
import { useAuth } from '../lib/auth'
import DetailPanel from './DetailPanel'
import LogCommitmentModal from './LogCommitmentModal'
import SettingsModal from './SettingsModal'

// ─── Helpers ──────────────────────────────────────────────────────────────

type GroupMode = 'status' | 'client' | 'source' | 'context'
type Tab = 'active' | 'commitments'

function badgeFromState(c: CommitmentRead): { label: string; classes: string; status: string } {
  const state = c.lifecycle_state
  if (state === 'delivered') return { label: 'Delivered', classes: 'bg-[#f0fdf4] text-[#15803d]', status: 'delivered' }
  if (state === 'discarded' || state === 'closed') return { label: 'Dismissed', classes: 'bg-[#f9fafb] text-[#6b7280] border border-[#e8e8e6]', status: 'dismissed' }
  const conf = c.confidence_commitment ? parseFloat(c.confidence_commitment) : 0
  if (conf >= 0.85) return { label: 'At risk', classes: 'bg-[#fee2e2] text-[#991b1b]', status: 'at-risk' }
  if (conf >= 0.70) return { label: 'Needs review', classes: 'bg-[#fef3c7] text-[#92400e]', status: 'needs-review' }
  if (conf >= 0.55) return { label: 'Worth confirming', classes: 'bg-[#eff6ff] text-[#1d4ed8]', status: 'worth-confirming' }
  return { label: 'Low signal', classes: 'bg-[#f9fafb] text-[#6b7280] border border-[#e8e8e6]', status: 'default' }
}

function accentColor(status: string): string {
  switch (status) {
    case 'at-risk': return '#dc2626'
    case 'needs-review': return '#d97706'
    case 'worth-confirming': return '#2563eb'
    case 'delivered': return '#16a34a'
    case 'dismissed': return '#d1d1cf'
    default: return '#e8e8e6'
  }
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

function IconGear() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  )
}

function sourceIcon(contextType: string | null | undefined) {
  switch (contextType) {
    case 'email': return <IconMail />
    case 'slack': return <IconHash />
    case 'meeting': return <IconVideo />
    default: return <IconMail />
  }
}

// ─── Sub-components ───────────────────────────────────────────────────────

function StatusBadge({ label, classes }: { label: string; classes: string }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ${classes}`}>{label}</span>
  )
}

function IconCheck() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  )
}

function IconXMark() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" x2="6" y1="6" y2="18" /><line x1="6" x2="18" y1="6" y2="18" />
    </svg>
  )
}

function confidenceLabel(score: string | null | undefined): string {
  if (!score) return 'Some uncertainty'
  const n = parseFloat(score)
  if (n >= 0.85) return 'High confidence'
  if (n >= 0.70) return 'Medium confidence'
  return 'Some uncertainty'
}

function CompactCommitmentRow({ commitment, selected, onClick, onConfirm, onDismiss }: {
  commitment: CommitmentRead
  selected: boolean
  onClick: () => void
  onConfirm: (id: string) => void
  onDismiss: (id: string) => void
}) {
  const badge = badgeFromState(commitment)
  const isDelivered = commitment.lifecycle_state === 'delivered'
  const isDismissed = commitment.lifecycle_state === 'discarded' || commitment.lifecycle_state === 'closed'
  const isClosed = isDelivered || isDismissed
  const person = commitment.resolved_owner || commitment.suggested_owner || null

  return (
    <div
      className={`rounded-lg border overflow-hidden transition-colors cursor-pointer ${
        isDelivered ? 'bg-[#f0fdf4] border-[#bbf0bb]' : isDismissed ? 'bg-[#fafafa] border-[#ececec] opacity-50' : 'bg-white'
      } ${
        selected ? 'border-[#d1d1cf] ring-1 ring-[#d1d1cf]' : 'border-[#e8e8e6] hover:border-[#d1d1cf]'
      }`}
      onClick={onClick}
    >
      <div className="flex">
        <div className="w-[3px] self-stretch flex-shrink-0" style={{ borderLeftWidth: '3px', borderLeftStyle: 'solid', borderLeftColor: accentColor(badge.status) }} />
        <div className="flex-1 px-4 py-2.5">
          <div className="flex items-center gap-3 flex-wrap">
            <StatusBadge label={badge.label} classes={badge.classes} />
            <span className={`text-[13px] font-medium flex-1 min-w-0 ${isDelivered ? 'line-through text-[#9ca3af]' : isDismissed ? 'text-[#9ca3af]' : 'text-[#191919]'}`}>
              {commitment.title}
            </span>
            <div className="flex items-center gap-1.5 text-[11px] text-[#9ca3af] flex-shrink-0">
              <span>{sourceIcon(commitment.context_type)}</span>
              <span>{sourceLabel(commitment.context_type)}</span>
              <span>·</span>
              <span>{formatDate(commitment.created_at)}</span>
              {person && (
                <>
                  <span>·</span>
                  <span>{person}</span>
                </>
              )}
            </div>
          </div>
          {/* Selected row: show description + confidence + inline actions */}
          {selected && (
            <div className="mt-2 pt-2 border-t border-[#f0f0ef]">
              {commitment.description && (
                <div className="text-[12px] text-[#6b7280] leading-relaxed mb-1.5">{commitment.description}</div>
              )}
              <div className="flex items-center justify-between">
                <span className="text-[11px] text-[#b0b0ae]">{confidenceLabel(commitment.confidence_commitment)}</span>
                {!isClosed && (
                  <div className="flex items-center gap-2">
                    <button
                      className="flex items-center gap-1.5 bg-[#191919] text-white text-[12px] px-3 py-1 rounded-md font-medium hover:bg-[#333] transition-colors"
                      onClick={(e) => { e.stopPropagation(); onConfirm(commitment.id) }}
                    >
                      <IconCheck />
                      Confirm
                    </button>
                    <button
                      className="flex items-center gap-1.5 bg-[#f0f0ef] text-[#191919] text-[12px] px-3 py-1 rounded-md font-medium hover:bg-[#e8e8e6] transition-colors"
                      onClick={(e) => { e.stopPropagation(); onDismiss(commitment.id) }}
                    >
                      <IconXMark />
                      Dismiss
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function StatusBar({ sources }: { sources: { source_type: string; is_active: boolean }[] }) {
  const types = [
    { key: 'email', label: 'Email' },
    { key: 'slack', label: 'Slack' },
    { key: 'meeting', label: 'Meetings' },
    { key: 'calendar', label: 'Calendar' },
  ]
  return (
    <div className="bg-[#fafaf9] border-b border-[#e8e8e6] h-[22px] flex items-center px-4 md:px-5">
      <div className="flex items-center gap-1.5 flex-1">
        {types.map((t, i) => {
          const connected = sources.some(s => s.source_type === t.key && s.is_active)
          return (
            <span key={t.key} className="flex items-center gap-1">
              {i > 0 && <span className="w-px h-2.5 bg-[#e8e8e6] mr-1" />}
              <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${connected ? 'bg-[#16a34a]' : 'bg-[#d1d1cf]'}`} />
              <span className="text-[11px] text-[#6b7280]">{t.label}</span>
            </span>
          )
        })}
      </div>
    </div>
  )
}

function ProofOfWork({ stats }: { stats: StatsRead | undefined }) {
  if (!stats) return null
  const parts: string[] = []
  if (stats.emails_captured > 0) parts.push(`${stats.emails_captured} emails captured`)
  if (stats.messages_processed > 0) parts.push(`${stats.messages_processed} messages processed`)
  if (stats.meetings_analyzed > 0) parts.push(`${stats.meetings_analyzed} meetings logged`)
  if (stats.people_identified > 0) parts.push(`${stats.people_identified} people identified`)
  if (parts.length === 0) return null
  return (
    <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-[#e8e8e6] z-10">
      <div className="flex justify-center py-3 px-6">
        <span className="text-[12px] text-[#9ca3af]">{parts.join(' · ')}</span>
      </div>
    </div>
  )
}

// ─── CommitmentsScreen ────────────────────────────────────────────────────

interface CommitmentsScreenProps {
  activeTab: Tab
  onTabChange: (t: Tab) => void
}

export default function CommitmentsScreen({ activeTab, onTabChange }: CommitmentsScreenProps) {
  const { user } = useAuth()
  const navigate = useNavigate()
  const isAdmin = user?.id === '441f9c1f-9428-477e-a04f-fb8d5e654ec2'
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [groupMode, setGroupMode] = useState<GroupMode>('status')
  const [showDismissed, setShowDismissed] = useState(false)
  const [showLog, setShowLog] = useState(false)
  const [showSettings, setShowSettings] = useState(false)
  const queryClient = useQueryClient()

  const { data: commitments, isLoading } = useQuery({
    queryKey: ['commitments'],
    queryFn: () => getCommitments({ limit: 200 }),
    refetchInterval: 30_000,
    staleTime: 25_000,
  })

  const { data: stats } = useQuery<StatsRead>({
    queryKey: ['stats'],
    queryFn: getStats,
    refetchInterval: 60_000,
    staleTime: 55_000,
  })

  const { data: sources } = useQuery({
    queryKey: ['sources'],
    queryFn: listSources,
    refetchInterval: 30_000,
    staleTime: 25_000,
  })

  const allCommitments = commitments ?? []
  const selectedCommitment = selectedId ? allCommitments.find(c => c.id === selectedId) ?? null : null

  const dismissedCount = allCommitments.filter(c => c.lifecycle_state === 'discarded' || c.lifecycle_state === 'closed').length

  async function handleConfirm(id: string) {
    await patchCommitment(id, { lifecycle_state: 'delivered' })
    queryClient.invalidateQueries({ queryKey: ['commitments'] })
    queryClient.invalidateQueries({ queryKey: ['surface'] })
  }

  async function handleDismiss(id: string) {
    await patchCommitment(id, { lifecycle_state: 'discarded' })
    queryClient.invalidateQueries({ queryKey: ['commitments'] })
    queryClient.invalidateQueries({ queryKey: ['surface'] })
  }

  const groupModes: { id: GroupMode; label: string }[] = [
    { id: 'status', label: 'Status' },
    { id: 'client', label: 'Client' },
    { id: 'source', label: 'Source' },
    { id: 'context', label: 'Context' },
  ]

  // ─── Grouping logic ──────────────────────────────────────────────────

  function filterDismissed(items: CommitmentRead[]): CommitmentRead[] {
    if (showDismissed) return items
    return items.filter(c => c.lifecycle_state !== 'discarded' && c.lifecycle_state !== 'closed')
  }

  function renderGrouped() {
    if (groupMode === 'status') {
      const statusOrder: { label: string; filter: (c: CommitmentRead) => boolean }[] = [
        { label: 'Needs review', filter: c => { const b = badgeFromState(c); return b.label === 'Needs review' } },
        { label: 'Worth confirming', filter: c => { const b = badgeFromState(c); return b.label === 'Worth confirming' } },
        { label: 'At risk', filter: c => { const b = badgeFromState(c); return b.label === 'At risk' } },
        { label: 'Delivered', filter: c => c.lifecycle_state === 'delivered' },
        { label: 'Dismissed', filter: c => c.lifecycle_state === 'discarded' || c.lifecycle_state === 'closed' },
      ]
      return (
        <>
          {statusOrder.map(({ label, filter }) => {
            const items = allCommitments.filter(filter)
            if (items.length === 0) return null
            if (label === 'Dismissed' && !showDismissed) return null
            return (
              <div key={label}>
                <div className="text-[16px] font-bold text-[#111827] mt-8 mb-3 flex items-center gap-2 border-b border-[#f0f0ef] pb-2">
                  <span>{label}</span>
                  <span className="text-[13px] font-medium text-[#9ca3af]">· {items.length}</span>
                </div>
                <div className="flex flex-col gap-2">
                  {items.map(c => (
                    <CompactCommitmentRow key={c.id} commitment={c} selected={selectedId === c.id} onClick={() => setSelectedId(selectedId === c.id ? null : c.id)} onConfirm={handleConfirm} onDismiss={handleDismiss} />
                  ))}
                </div>
              </div>
            )
          })}
        </>
      )
    }

    if (groupMode === 'client') {
      const groups: Record<string, CommitmentRead[]> = {}
      for (const c of allCommitments) {
        const key = c.counterparty_name || 'Internal'
        if (!groups[key]) groups[key] = []
        groups[key].push(c)
      }
      return Object.entries(groups).map(([client, items]) => {
        const filtered = filterDismissed(items)
        if (filtered.length === 0) return null
        return (
          <div key={client}>
            <div className="text-[16px] font-bold text-[#111827] mt-10 mb-3 flex items-center gap-2 border-b border-[#f0f0ef] pb-2">
              <span>{client}</span>
              <span className="text-[13px] font-medium text-[#9ca3af]">· {filtered.length}</span>
            </div>
            <div className="flex flex-col gap-2">
              {filtered.map(c => (
                <CompactCommitmentRow key={c.id} commitment={c} selected={selectedId === c.id} onClick={() => setSelectedId(selectedId === c.id ? null : c.id)} onConfirm={handleConfirm} onDismiss={handleDismiss} />
              ))}
            </div>
          </div>
        )
      })
    }

    if (groupMode === 'source') {
      const sourceTypes = ['email', 'slack', 'meeting'] as const
      const labels: Record<string, string> = { email: 'Email', slack: 'Slack', meeting: 'Meetings' }
      return sourceTypes.map(st => {
        const items = filterDismissed(allCommitments.filter(c => c.context_type === st))
        if (items.length === 0) return null
        return (
          <div key={st}>
            <div className="text-[16px] font-bold text-[#111827] mt-10 mb-3 flex items-center gap-2 border-b border-[#f0f0ef] pb-2">
              <span>{labels[st]}</span>
              <span className="text-[13px] font-medium text-[#9ca3af]">· {items.length}</span>
            </div>
            <div className="flex flex-col gap-2">
              {items.map(c => (
                <CompactCommitmentRow key={c.id} commitment={c} selected={selectedId === c.id} onClick={() => setSelectedId(selectedId === c.id ? null : c.id)} onConfirm={handleConfirm} onDismiss={handleDismiss} />
              ))}
            </div>
          </div>
        )
      })
    }

    if (groupMode === 'context') {
      const contextGroups: Record<string, CommitmentRead[]> = {}
      const noContext: CommitmentRead[] = []
      for (const c of allCommitments) {
        if (c.context_id) {
          const key = c.context_id
          if (!contextGroups[key]) contextGroups[key] = []
          contextGroups[key].push(c)
        } else {
          noContext.push(c)
        }
      }
      return (
        <>
          {Object.entries(contextGroups).map(([ctxId, items]) => {
            const filtered = filterDismissed(items)
            if (filtered.length === 0) return null
            const openCount = filtered.filter(c => c.lifecycle_state !== 'delivered' && c.lifecycle_state !== 'discarded' && c.lifecycle_state !== 'closed').length
            const atRiskCount = filtered.filter(c => badgeFromState(c).status === 'at-risk').length
            const summaryParts: string[] = []
            if (openCount > 0) summaryParts.push(`${openCount} open`)
            if (atRiskCount > 0) summaryParts.push(`${atRiskCount} at risk`)
            const contextLabel = ctxId.slice(0, 8)
            return (
              <div key={ctxId}>
                <div className="mt-8 mb-3 border-b border-[#f0f0ef] pb-2">
                  <div className="text-[16px] font-bold text-[#111827] flex items-center gap-2">
                    <span>Context {contextLabel}</span>
                    <span className="text-[13px] font-medium text-[#9ca3af]">· {filtered.length}</span>
                  </div>
                  {summaryParts.length > 0 && (
                    <div className="text-[11px] text-[#9ca3af] mt-0.5">{summaryParts.join(' · ')}</div>
                  )}
                </div>
                <div className="flex flex-col gap-2">
                  {filtered.map(c => (
                    <CompactCommitmentRow key={c.id} commitment={c} selected={selectedId === c.id} onClick={() => setSelectedId(selectedId === c.id ? null : c.id)} onConfirm={handleConfirm} onDismiss={handleDismiss} />
                  ))}
                </div>
              </div>
            )
          })}
          {(() => {
            const filtered = filterDismissed(noContext)
            if (filtered.length === 0) return null
            return (
              <div>
                <div className="text-[16px] font-bold text-[#111827] mt-8 mb-3 flex items-center gap-2 border-b border-[#f0f0ef] pb-2">
                  <span>No context</span>
                  <span className="text-[13px] font-medium text-[#9ca3af]">· {filtered.length}</span>
                </div>
                <div className="flex flex-col gap-2">
                  {filtered.map(c => (
                    <CompactCommitmentRow key={c.id} commitment={c} selected={selectedId === c.id} onClick={() => setSelectedId(selectedId === c.id ? null : c.id)} onConfirm={handleConfirm} onDismiss={handleDismiss} />
                  ))}
                </div>
              </div>
            )
          })()}
        </>
      )
    }
    return null
  }

  const tabs: { id: Tab; label: string }[] = [
    { id: 'active', label: 'Active' },
    { id: 'commitments', label: 'Commitments' },
  ]

  return (
    <div className="min-h-screen bg-[#f9f9f8]">
      {/* Header */}
      <div className="bg-white border-b border-[#e8e8e6] h-[52px] flex items-center px-4 md:px-6">
        <div className="flex items-center flex-shrink-0">
          <span className="font-semibold text-[16px] text-[#191919] tracking-tight">rippled</span>
        </div>
        <div className="flex items-center gap-1 mx-3 md:mx-auto">
          {tabs.map((t) =>
            activeTab === t.id ? (
              <button key={t.id} onClick={() => onTabChange(t.id)} className="bg-[#191919] text-white rounded-full px-3 md:px-4 py-1 text-[13px] font-medium">{t.label}</button>
            ) : (
              <button key={t.id} onClick={() => onTabChange(t.id)} className="text-[#6b7280] hover:text-[#191919] px-3 md:px-4 py-1 text-[13px] transition-colors">{t.label}</button>
            )
          )}
        </div>
        <div className="flex items-center gap-3 ml-auto flex-shrink-0">
          <button onClick={() => setShowLog(true)} className="hidden md:inline-flex text-[#6b7280] hover:text-[#191919] border border-[#e8e8e6] hover:border-[#d1d1cf] rounded-md px-3 py-1 text-[12px] font-medium transition-colors">
            + Log commitment
          </button>
          <div className="hidden md:block w-px h-4 bg-[#e8e8e6]" />
          {isAdmin && (
            <>
              <button onClick={() => navigate('/admin')} className="hidden md:inline-flex text-[#9ca3af] hover:text-[#191919] text-[12px] font-medium transition-colors">
                Admin
              </button>
              <div className="hidden md:block w-px h-4 bg-[#e8e8e6]" />
            </>
          )}
          <button onClick={() => setShowSettings(true)} className="text-[#9ca3af] hover:text-[#191919] transition-colors">
            <IconGear />
          </button>
        </div>
      </div>

      <StatusBar sources={sources ?? []} />

      <main className="max-w-[1100px] mx-auto px-6 pt-0 pb-14">
        {isLoading ? (
          <div className="flex items-center justify-center py-20">
            <div className="w-8 h-8 border-2 border-[#191919] border-t-transparent rounded-full animate-spin" />
          </div>
        ) : (
          <div className="max-w-[720px] mx-auto">
            <div className="pt-0.5 pb-2 max-w-[480px] mx-auto text-center">
              <div className="font-semibold text-[22px] text-[#191919]">All commitments</div>
              <div className="text-[13px] text-[#6b7280] mt-1">A broader view of likely commitments Rippled is tracking across your connected sources.</div>
            </div>
            <div className="flex items-center mb-5">
              <span className="text-[13px] text-[#4b5563] font-semibold mr-3">Group by:</span>
              <div className="inline-flex rounded-lg border border-[#e8e8e6] overflow-hidden">
                {groupModes.map((g) => (
                  <button
                    key={g.id}
                    onClick={() => setGroupMode(g.id)}
                    className={`px-3.5 py-1.5 text-[13px] font-medium transition-colors border-r border-[#e8e8e6] last:border-r-0 ${
                      groupMode === g.id
                        ? 'bg-[#191919] text-white'
                        : 'bg-white text-[#6b7280] hover:text-[#191919] hover:bg-[#f5f5f4]'
                    }`}
                  >
                    {g.label}
                  </button>
                ))}
              </div>
            </div>
            <div>
              {allCommitments.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-16 text-center">
                  <div className="text-[#d1d1cf] mb-4">
                    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="22 12 16 12 14 15 10 15 8 12 2 12" />
                      <path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z" />
                    </svg>
                  </div>
                  <div className="text-[14px] text-[#6b7280] mb-1.5">No commitments tracked yet.</div>
                  <div className="text-[13px] text-[#9ca3af]">Rippled will surface items as they're detected from your connected sources.</div>
                </div>
              ) : renderGrouped()}
              {dismissedCount > 0 && (
                <span
                  className="text-[12px] text-[#9ca3af] hover:text-[#6b7280] cursor-pointer mt-4 inline-block hover:underline underline-offset-2"
                  onClick={() => setShowDismissed(!showDismissed)}
                >
                  {showDismissed ? 'Hide dismissed' : `Show dismissed (${dismissedCount})`}
                </span>
              )}
            </div>
          </div>
        )}
      </main>

      {/* Mobile FAB for Log commitment */}
      <button
        onClick={() => setShowLog(true)}
        className="md:hidden fixed bottom-20 right-4 z-40 w-12 h-12 rounded-full bg-[#191919] text-white shadow-lg flex items-center justify-center text-[22px] hover:bg-[#333] transition-colors"
        aria-label="Log commitment"
      >
        +
      </button>

      <ProofOfWork stats={stats} />
      <DetailPanel commitment={selectedCommitment} allCommitments={allCommitments} onClose={() => setSelectedId(null)} />

      {showLog && (
        <div className="fixed inset-0 bg-black/30 z-50 flex items-center justify-center" onClick={() => setShowLog(false)}>
          <div className="bg-[#f9f9f8] rounded-xl shadow-2xl w-full max-w-[560px] max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <LogCommitmentModal onCancel={() => setShowLog(false)} onSuccess={() => { setShowLog(false); queryClient.invalidateQueries({ queryKey: ['commitments'] }) }} />
          </div>
        </div>
      )}

      {showSettings && (
        <div className="fixed inset-0 bg-black/30 z-50 flex items-start justify-center md:pt-16 md:pb-16" onClick={() => setShowSettings(false)}>
          <div className="bg-[#f9f9f8] md:rounded-xl shadow-2xl w-full max-w-[760px] h-full md:h-auto md:max-h-[80vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-6 md:px-8 pt-6 pb-4 border-b border-[#e8e8e6] sticky top-0 bg-[#f9f9f8] z-10">
              <span className="font-semibold text-[16px] text-[#191919]">Settings</span>
              <button onClick={() => setShowSettings(false)} className="w-8 h-8 flex items-center justify-center text-[#9ca3af] hover:text-[#191919] hover:bg-[#f0f0ef] rounded-md transition-colors text-[18px]">×</button>
            </div>
            <SettingsModal />
          </div>
        </div>
      )}
    </div>
  )
}
