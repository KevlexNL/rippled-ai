import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { getSurface, getBestNextMoves } from '../api/surface'
import type { BestNextMovesGroup } from '../api/surface'
import { getStats } from '../api/stats'
import type { StatsRead } from '../api/stats'
import { listSources } from '../api/sources'
import { getUpcomingEvents } from '../api/events'
import type { EventRead } from '../api/events'
import { patchCommitment, skipCommitment } from '../api/commitments'
import { apiGet } from '../lib/apiClient'
import { useAuth } from '../lib/auth'
import { filterMine } from '../utils/ownershipFilter'
import { confidenceLabel as getConfidenceLabel, ownerLabel } from '../utils/suggestionLanguage'
import type { CommitmentRead } from '../types'
import DetailPanel from './DetailPanel'
import LogCommitmentModal from './LogCommitmentModal'
import SettingsModal from './SettingsModal'

// ─── Helpers ──────────────────────────────────────────────────────────────

function confidenceLabel(score: string | null | undefined): string {
  return getConfidenceLabel(score)
}

function badgeFromState(c: CommitmentRead): { label: string; classes: string; status: string } {
  const state = c.lifecycle_state
  if (state === 'delivered') return { label: 'Delivered', classes: 'bg-[#f0fdf4] text-[#15803d]', status: 'delivered' }
  if (state === 'confirmed') return { label: 'Confirmed', classes: 'bg-[#f0fdf4] text-[#15803d]', status: 'confirmed' }
  if (state === 'dormant') return { label: 'Not Now', classes: 'bg-[#f9fafb] text-[#9ca3af] border border-[#e8e8e6]', status: 'dormant' }
  if (state === 'discarded' || state === 'closed') return { label: 'Dismissed', classes: 'bg-[#f9fafb] text-[#6b7280] border border-[#e8e8e6]', status: 'dismissed' }
  const conf = c.confidence_commitment ? parseFloat(c.confidence_commitment) : 0
  if (conf >= 0.85) return { label: 'At risk', classes: 'bg-[#fee2e2] text-[#991b1b]', status: 'at-risk' }
  if (conf >= 0.70) return { label: 'Needs review', classes: 'bg-[#fef3c7] text-[#92400e]', status: 'needs-review' }
  if (conf >= 0.55) return { label: 'Worth confirming', classes: 'bg-[#eff6ff] text-[#1d4ed8]', status: 'worth-confirming' }
  return { label: 'Low signal', classes: 'bg-[#f9fafb] text-[#6b7280] border border-[#e8e8e6]', status: 'default' }
}

function accentClass(status: string): string {
  switch (status) {
    case 'at-risk': return '#dc2626'
    case 'needs-review': return '#d97706'
    case 'worth-confirming': return '#2563eb'
    case 'likely-missing': return '#6d28d9'
    case 'delivered': return '#16a34a'
    case 'confirmed': return '#16a34a'
    case 'dismissed': return '#d1d1cf'
    case 'dormant': return '#d1d1cf'
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

function formatRelativeTime(iso: string): string {
  const d = new Date(iso)
  const now = new Date()
  const diffMs = d.getTime() - now.getTime()
  const diffMins = Math.round(diffMs / 60000)
  const diffHours = Math.round(diffMs / 3600000)
  const diffDays = Math.round(diffMs / 86400000)

  if (diffMins < 0) return 'Past'
  if (diffMins < 60) return `In ${diffMins} min`
  if (diffHours < 24) return `In ${diffHours} hour${diffHours !== 1 ? 's' : ''}`
  if (diffDays === 1) {
    return `Tomorrow at ${d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}`
  }
  if (diffDays < 7) {
    return `${d.toLocaleDateString('en-US', { weekday: 'long' })} at ${d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}`
  }
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function IconCalendar() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
      <line x1="16" y1="2" x2="16" y2="6" /><line x1="8" y1="2" x2="8" y2="6" />
      <line x1="3" y1="10" x2="21" y2="10" />
    </svg>
  )
}

function UpcomingSection({ events }: { events: EventRead[] }) {
  if (events.length === 0) return null
  return (
    <div className="mt-6">
      <h2 className="text-[13px] font-semibold text-[#6b7280] mb-2">Upcoming</h2>
      <div className="flex flex-col gap-1.5">
        {events.map((ev) => {
          const attendeeCount = ev.attendees?.length ?? 0
          return (
            <div
              key={ev.id}
              className="bg-[#fafaf9] rounded-lg border border-[#e8e8e6] overflow-hidden"
            >
              <div className="flex">
                <div className="w-[3px] self-stretch flex-shrink-0 bg-[#d1d1cf]" />
                <div className="flex-1 px-4 py-2.5">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="text-[#9ca3af] flex-shrink-0"><IconCalendar /></span>
                      <span className="text-[13px] font-medium text-[#191919] truncate">{ev.title}</span>
                    </div>
                    <div className="flex items-center gap-2 text-[11px] text-[#9ca3af] flex-shrink-0 ml-3">
                      <span>{formatRelativeTime(ev.starts_at)}</span>
                      {attendeeCount > 0 && (
                        <>
                          <span>·</span>
                          <span>{attendeeCount} attendee{attendeeCount !== 1 ? 's' : ''}</span>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function groupPillClasses(label: string): string {
  switch (label) {
    case 'Quick wins': return 'bg-[#d1fae5] text-[#065f46]'
    case 'Likely blockers': return 'bg-[#fef3c7] text-[#92400e]'
    case 'Needs focus': return 'bg-[#ede9fe] text-[#5b21b6]'
    default: return 'bg-[#f0f0ef] text-[#6b7280]'
  }
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

function IconXMark() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" x2="6" y1="6" y2="18" /><line x1="6" x2="18" y1="6" y2="18" />
    </svg>
  )
}

function IconClock() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" />
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

function IconArrow() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M5 12h14" /><path d="m12 5 7 7-7 7" />
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

function IconInbox() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="22 12 16 12 14 15 10 15 8 12 2 12" />
      <path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z" />
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

/** Resolve display owner with tentative language (C1 suggestion language pass). */
function resolveOwner(c: CommitmentRead): { text: string; isSuggested: boolean } | null {
  return ownerLabel(
    c.resolved_owner,
    c.suggested_owner,
    c.confidence_commitment,
    c.source_sender_name || c.counterparty_name,
  )
}

/** Get the source attribution line: who sent it + when (Fix 3 & 4). */
function sourceAttribution(c: CommitmentRead): string {
  const parts: string[] = []
  // Source sender or meeting title
  if (c.source_sender_name) {
    parts.push(c.source_sender_name)
  } else if (c.source_sender_email) {
    parts.push(c.source_sender_email)
  }
  // Use occurred_at (original signal date) instead of created_at (processing date)
  const dateStr = formatDate(c.source_occurred_at || c.created_at)
  if (dateStr) parts.push(dateStr)
  return parts.join(' · ')
}

// ─── Sub-components ───────────────────────────────────────────────────────

function StatusBadge({ label, classes }: { label: string; classes: string }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ${classes}`}>
      {label}
    </span>
  )
}

function CommitmentCard({ commitment, onOpen, onConfirm, onDismiss, onNotNow, onSkip, isFirst }: {
  commitment: CommitmentRead
  onOpen: (id: string) => void
  onConfirm: (id: string) => void
  onDismiss: (id: string) => void
  onNotNow: (id: string) => void
  onSkip: (id: string) => void
  isFirst?: boolean
}) {
  const badge = badgeFromState(commitment)
  const isConfirmed = commitment.lifecycle_state === 'confirmed'
  const color = accentClass(badge.status)

  return (
    <div
      className="bg-white rounded-lg border border-[#e8e8e6] overflow-hidden hover:border-[#d1d1cf] transition-all duration-200 cursor-pointer"
      onClick={() => onOpen(commitment.id)}
    >
      <div className="flex">
        <div className="w-[3px] self-stretch flex-shrink-0" style={{ borderLeftWidth: '3px', borderLeftStyle: 'solid', borderLeftColor: color }} />
        <div className="flex-1 px-4 py-2.5">
          <div className="flex justify-between items-start mb-1">
            <div className="flex items-center gap-2">
              <StatusBadge label={badge.label} classes={badge.classes} />
              <span className="text-[11px] text-[#b0b0ae]">{confidenceLabel(commitment.confidence_commitment)}</span>
            </div>
            <div className="flex items-center gap-1 text-[11px] text-[#9ca3af] text-right flex-shrink-0 ml-3">
              <span>{sourceIcon(commitment.context_type)}</span>
              <span>{sourceLabel(commitment.context_type)}</span>
              {(commitment.source_sender_name || commitment.source_sender_email) && (
                <>
                  <span>·</span>
                  <span>{commitment.source_sender_name || commitment.source_sender_email}</span>
                </>
              )}
              <span>·</span>
              <span>{formatDate(commitment.source_occurred_at || commitment.created_at)}</span>
            </div>
          </div>
          <div className="font-semibold text-[14px] text-[#191919] mb-0.5">
            {commitment.title}
            {isConfirmed && (
              <span className="ml-1.5 inline-flex items-center text-[#16a34a]" title="Confirmed">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
              </span>
            )}
          </div>
          {commitment.description && (
            <div className="text-[12px] text-[#6b7280] leading-relaxed mb-1">{commitment.description}</div>
          )}
          <div className="flex items-center gap-2 pt-1 border-t border-[#f0f0ef]" {...(isFirst ? { 'data-onboard': 'action-buttons' } : {})}>
            <button
              className="flex items-center gap-1.5 bg-[#191919] text-white text-[12px] px-3 py-1 rounded-md font-medium hover:bg-[#333] transition-colors"
              onClick={(e) => { e.stopPropagation(); onConfirm(commitment.id) }}
            >
              <IconCheck />
              Confirm
            </button>
            <button
              className="flex items-center gap-1.5 bg-[#f0f0ef] text-[#4b5563] text-[12px] px-3 py-1 rounded-md font-medium hover:bg-[#e8e8e6] transition-colors"
              onClick={(e) => { e.stopPropagation(); onNotNow(commitment.id) }}
            >
              <IconClock />
              Not Now
            </button>
            <button
              className="flex items-center gap-1.5 bg-[#f0f0ef] text-[#191919] text-[12px] px-3 py-1 rounded-md font-medium hover:bg-[#e8e8e6] transition-colors"
              onClick={(e) => { e.stopPropagation(); onDismiss(commitment.id) }}
            >
              <IconXMark />
              Dismiss
            </button>
            <button
              className="flex items-center gap-1.5 text-[#9ca3af] text-[12px] px-2 py-1 rounded-md hover:text-[#6b7280] hover:bg-[#f5f5f4] transition-colors"
              onClick={(e) => { e.stopPropagation(); onSkip(commitment.id) }}
              title="Can't assess — skip for now"
            >
              <IconSkip />
              Skip
            </button>
            <button
              className="flex items-center gap-1.5 border border-[#e8e8e6] text-[#6b7280] hover:text-[#191919] text-[12px] px-3 py-1 rounded-md transition-colors ml-auto"
              onClick={(e) => { e.stopPropagation(); onOpen(commitment.id) }}
            >
              Details <IconArrow />
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function BestNextMovesRail({ groups, onOpen }: { groups: BestNextMovesGroup[]; onOpen: (id: string) => void }) {
  if (groups.length === 0) return null
  return (
    <div>
      <div className="text-[15px] font-semibold text-[#191919]">Best next moves</div>
      <div className="text-[12px] text-[#9ca3af] mt-0.5 mb-1">Unblock work or move commitments forward.</div>
      <div className="flex flex-col gap-1">
        {groups.map((group, gi) => (
          <div key={gi}>
            <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-medium mb-1 mt-0 ${groupPillClasses(group.label)}`}>
              {group.label} | {group.items.length}
            </span>
            <div className="bg-white border border-[#e8e8e6] rounded-lg overflow-hidden">
              {group.items.map((item, i) => (
                <div
                  key={item.id}
                  className={`px-3.5 py-1.5 hover:bg-[#f5f5f4] cursor-pointer transition-colors ${i > 0 ? 'border-t border-[#f0f0ef]' : ''}`}
                  onClick={() => onOpen(item.id)}
                >
                  <div className="text-[13px] font-semibold text-[#191919] mb-0.5">{item.title}</div>
                  <div className="text-[11px] text-[#9ca3af]">{sourceLabel(item.context_type)} · {formatDate(item.source_occurred_at || item.created_at)}</div>
                  {item.surfacing_reason && (
                    <div className="text-[11px] text-[#9ca3af] italic mt-0.5">{item.surfacing_reason}</div>
                  )}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function StatusBar({ sources, stats }: { sources: { source_type: string; is_active: boolean }[]; stats?: StatsRead }) {
  const types = [
    { key: 'email', label: 'Email' },
    { key: 'slack', label: 'Slack' },
    { key: 'meeting', label: 'Meetings' },
    { key: 'calendar', label: 'Calendar' },
  ]
  const signalsCount = stats ? (stats.emails_captured + stats.messages_processed + stats.meetings_analyzed) : 0
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
      <div className="hidden md:flex items-center gap-2 text-[11px] text-[#9ca3af]">
        {signalsCount > 0 && <span>{signalsCount} signals reviewed in the last 24 hours</span>}
        {signalsCount > 0 && <span className="w-px h-2.5 bg-[#e8e8e6]" />}
        <span>Watching {stats?.people_identified ?? 0} active threads</span>
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

// ─── ActiveScreen ─────────────────────────────────────────────────────────

type Tab = 'active' | 'commitments'

interface ActiveScreenProps {
  activeTab: Tab
  onTabChange: (t: Tab) => void
}

export default function ActiveScreen({ activeTab, onTabChange }: ActiveScreenProps) {
  const { user } = useAuth()
  const navigate = useNavigate()
  const isAdmin = user?.id === '441f9c1f-9428-477e-a04f-fb8d5e654ec2'
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [showLog, setShowLog] = useState(false)
  const [showSettings, setShowSettings] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const queryClient = useQueryClient()

  // Data queries
  const { data: mainItems, isLoading: mainLoading } = useQuery({
    queryKey: ['surface', 'main'],
    queryFn: () => getSurface('main'),
    refetchInterval: 30_000,
    staleTime: 25_000,
  })

  const { data: bestNextMoves } = useQuery({
    queryKey: ['surface', 'best-next-moves'],
    queryFn: getBestNextMoves,
    refetchInterval: 30_000,
    staleTime: 25_000,
  })

  const { data: stats } = useQuery<StatsRead>({
    queryKey: ['stats'],
    queryFn: getStats,
    refetchInterval: 60_000,
    staleTime: 55_000,
  })

  const { data: sources, isLoading: sourcesLoading } = useQuery({
    queryKey: ['sources'],
    queryFn: listSources,
    refetchInterval: 30_000,
    staleTime: 25_000,
  })

  const { data: googleStatus } = useQuery<{ connected: boolean }>({
    queryKey: ['google-status'],
    queryFn: () => apiGet<{ connected: boolean }>('/api/v1/integrations/google/status'),
    refetchInterval: 60_000,
    staleTime: 55_000,
  })

  const { data: upcomingEvents } = useQuery({
    queryKey: ['events'],
    queryFn: getUpcomingEvents,
    refetchInterval: 60_000,
    staleTime: 55_000,
    enabled: googleStatus?.connected === true,
  })

  // Ownership filtering — only show mine + triage on Active tab
  const userName = user?.user_metadata?.full_name ?? user?.user_metadata?.name ?? null
  const userEmail = user?.email ?? null
  const surfaced = filterMine((mainItems ?? []), userName, userEmail).slice(0, 3)
  const groups = bestNextMoves?.groups ?? []
  const allCommitments = [...surfaced, ...groups.flatMap(g => g.items)]

  const selectedCommitment = selectedId
    ? allCommitments.find(c => c.id === selectedId) ?? null
    : null

  async function handleConfirm(id: string) {
    try {
      setError(null)
      setSelectedId(prev => prev === id ? null : prev)
      // Optimistic: remove from surface cache immediately
      queryClient.setQueryData<CommitmentRead[]>(['surface', 'main'], (old) => old?.filter(c => c.id !== id))
      queryClient.setQueryData(['surface', 'best-next-moves'], (old: { groups: BestNextMovesGroup[] } | undefined) =>
        old ? { groups: old.groups.map(g => ({ ...g, items: g.items.filter(c => c.id !== id) })).filter(g => g.items.length > 0) } : old
      )
      await patchCommitment(id, { lifecycle_state: 'active' })
      queryClient.invalidateQueries({ queryKey: ['surface'] })
    } catch {
      setError('Failed to confirm commitment')
      queryClient.invalidateQueries({ queryKey: ['surface'] })
    }
  }

  async function handleDismiss(id: string) {
    try {
      setError(null)
      setSelectedId(prev => prev === id ? null : prev)
      // Optimistic: remove from surface cache immediately
      queryClient.setQueryData<CommitmentRead[]>(['surface', 'main'], (old) => old?.filter(c => c.id !== id))
      queryClient.setQueryData(['surface', 'best-next-moves'], (old: { groups: BestNextMovesGroup[] } | undefined) =>
        old ? { groups: old.groups.map(g => ({ ...g, items: g.items.filter(c => c.id !== id) })).filter(g => g.items.length > 0) } : old
      )
      await patchCommitment(id, { lifecycle_state: 'discarded' })
      queryClient.invalidateQueries({ queryKey: ['surface'] })
    } catch {
      setError('Failed to dismiss commitment')
      queryClient.invalidateQueries({ queryKey: ['surface'] })
    }
  }

  async function handleNotNow(id: string) {
    try {
      setError(null)
      setSelectedId(prev => prev === id ? null : prev)
      // Optimistic: remove from surface cache immediately
      queryClient.setQueryData<CommitmentRead[]>(['surface', 'main'], (old) => old?.filter(c => c.id !== id))
      queryClient.setQueryData(['surface', 'best-next-moves'], (old: { groups: BestNextMovesGroup[] } | undefined) =>
        old ? { groups: old.groups.map(g => ({ ...g, items: g.items.filter(c => c.id !== id) })).filter(g => g.items.length > 0) } : old
      )
      await patchCommitment(id, { lifecycle_state: 'dormant' })
      queryClient.invalidateQueries({ queryKey: ['surface'] })
    } catch {
      setError('Failed to snooze commitment')
      queryClient.invalidateQueries({ queryKey: ['surface'] })
    }
  }

  async function handleSkip(id: string) {
    try {
      setError(null)
      setSelectedId(prev => prev === id ? null : prev)
      // Optimistic: remove from surface cache immediately
      queryClient.setQueryData<CommitmentRead[]>(['surface', 'main'], (old) => old?.filter(c => c.id !== id))
      queryClient.setQueryData(['surface', 'best-next-moves'], (old: { groups: BestNextMovesGroup[] } | undefined) =>
        old ? { groups: old.groups.map(g => ({ ...g, items: g.items.filter(c => c.id !== id) })).filter(g => g.items.length > 0) } : old
      )
      await skipCommitment(id)
      queryClient.invalidateQueries({ queryKey: ['surface'] })
    } catch {
      setError('Failed to skip commitment')
      queryClient.invalidateQueries({ queryKey: ['surface'] })
    }
  }

  const tabs: { id: Tab; label: string }[] = [
    { id: 'active', label: 'Active' },
    { id: 'commitments', label: 'Commitments' },
  ]

  const hasConnectedSources = sourcesLoading || (sources ?? []).some(s => s.is_active)

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
              <button key={t.id} onClick={() => onTabChange(t.id)} data-onboard={t.id === 'active' ? 'active-tab' : 'commitments-tab'} className="bg-[#191919] text-white rounded-full px-3 md:px-4 py-1 text-[13px] font-medium">{t.label}</button>
            ) : (
              <button key={t.id} onClick={() => onTabChange(t.id)} data-onboard={t.id === 'active' ? 'active-tab' : 'commitments-tab'} className="text-[#6b7280] hover:text-[#191919] px-3 md:px-4 py-1 text-[13px] transition-colors">{t.label}</button>
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
          <button onClick={() => setShowSettings(true)} data-onboard="settings-button" className="text-[#9ca3af] hover:text-[#191919] transition-colors">
            <IconGear />
          </button>
        </div>
      </div>

      <StatusBar sources={sources ?? []} stats={stats} />

      <main className="max-w-[1100px] mx-auto px-6 pt-0 pb-12">
        {error && (
          <div className="mb-4 rounded-md bg-[#fee2e2] border border-[#fca5a5] px-4 py-3 text-[13px] text-[#991b1b] font-medium">
            {error}
          </div>
        )}

        {mainLoading ? (
          <div className="flex items-center justify-center py-20">
            <div className="w-8 h-8 border-2 border-[#191919] border-t-transparent rounded-full animate-spin" />
          </div>
        ) : surfaced.length === 0 ? (
          /* Empty state */
          <div className="flex flex-col items-center justify-center py-20 text-center">
            {!hasConnectedSources ? (
              <>
                <div className="text-[#d1d1cf] mb-4"><IconInbox /></div>
                <div className="text-[14px] text-[#6b7280] mb-1.5">Connect your first source.</div>
                <div className="text-[13px] text-[#9ca3af]">Rippled needs a source to watch before it can surface commitments.</div>
              </>
            ) : (
              <>
                <div className="text-[#d1d1cf] mb-4"><IconInbox /></div>
                <div className="text-[14px] text-[#6b7280] mb-1.5">Nothing needs your attention right now.</div>
                <div className="text-[13px] text-[#9ca3af]">Rippled is watching — we'll surface items when something deserves it.</div>
              </>
            )}
          </div>
        ) : (
          <>
            <div className="pt-4 pb-2 max-w-[480px] mx-auto text-center">
              <div className="font-semibold text-[22px] text-[#191919]">What deserves your attention</div>
              <div className="text-[13px] text-[#6b7280] mt-0.5">Rippled is only surfacing the highest-priority items right now.</div>
              <div className="text-[12px] text-[#9ca3af] mt-0.5">Showing {surfaced.length} highest-priority item{surfaced.length !== 1 ? 's' : ''}</div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-[1fr_320px] gap-2">
              <div>
                <h2 className="text-[15px] font-semibold text-[#191919] mb-1">Surfaced for review</h2>
                <div className="flex flex-col gap-2" data-onboard="detail-panel-area">
                  {surfaced.map((c, i) => (
                    <CommitmentCard key={c.id} commitment={c} onOpen={setSelectedId} onConfirm={handleConfirm} onDismiss={handleDismiss} onNotNow={handleNotNow} onSkip={handleSkip} isFirst={i === 0} />
                  ))}
                </div>
              </div>
              <div>
                <BestNextMovesRail groups={groups} onOpen={setSelectedId} />
              </div>
            </div>
          </>
        )}

        {googleStatus?.connected && (upcomingEvents ?? []).length > 0 && (
          <UpcomingSection events={upcomingEvents!} />
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
            <LogCommitmentModal onCancel={() => setShowLog(false)} onSuccess={() => { setShowLog(false); queryClient.invalidateQueries({ queryKey: ['surface'] }) }} />
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
