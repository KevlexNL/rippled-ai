import { useRef, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useQueries, useQuery, useQueryClient } from '@tanstack/react-query'
import { getSurface } from '../api/surface'
import { postCommitment, patchCommitment } from '../api/commitments'
import { getClarifications } from '../api/clarifications'
import { listSources } from '../api/sources'
import { getStats } from '../api/stats'
import { getUpcomingEvents } from '../api/events'
import type { CommitmentRead, CommitmentCreate } from '../types'
import type { ClarificationRead } from '../api/clarifications'
import type { StatsRead } from '../api/stats'
import type { EventRead } from '../api/events'
import { dedupById, buildDashboardGroups, getGroupStatusColor } from '../utils/grouping'
import { getContexts } from '../api/contexts'
import type { CommitmentContextRead } from '../api/contexts'
import SourceGroup from '../components/SourceGroup'
import BottomBar from '../components/BottomBar'
import LoadingSpinner from '../components/LoadingSpinner'
import ErrorBanner from '../components/ErrorBanner'

interface UndoEntry {
  id: string
  previousState: string
}

interface OverviewCounts {
  main: number
  shortlist: number
  clarifications: number
}

function formatRelativeTime(isoString: string): string {
  const date = new Date(isoString)
  const now = new Date()
  const diffMs = date.getTime() - now.getTime()
  const diffMin = Math.round(diffMs / 60000)
  const diffHrs = Math.round(diffMs / 3600000)
  const diffDays = Math.round(diffMs / 86400000)

  if (diffMin < 0) return 'In progress'
  if (diffMin < 60) return `in ${diffMin}m`
  if (diffHrs < 24) return `in ${diffHrs}h`
  if (diffDays === 1) return 'tomorrow'
  return `in ${diffDays}d`
}

export default function Dashboard() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const undoBufferRef = useRef<UndoEntry[]>([])
  const [canRevert, setCanRevert] = useState(false)
  const [showOverview, setShowOverview] = useState(false)
  const [showAddForm, setShowAddForm] = useState(false)
  const [addTitle, setAddTitle] = useState('')
  const [addOwner, setAddOwner] = useState('')
  const [addDeadline, setAddDeadline] = useState('')
  const [addError, setAddError] = useState<string | null>(null)
  const [addLoading, setAddLoading] = useState(false)

  const results = useQueries({
    queries: [
      {
        queryKey: ['surface', 'main'],
        queryFn: () => getSurface('main'),
        refetchInterval: 30_000,
        staleTime: 25_000,
      },
      {
        queryKey: ['surface', 'shortlist'],
        queryFn: () => getSurface('shortlist'),
        refetchInterval: 30_000,
        staleTime: 25_000,
      },
      {
        queryKey: ['surface', 'clarifications'],
        queryFn: () => getSurface('clarifications'),
        refetchInterval: 30_000,
        staleTime: 25_000,
      },
    ],
  })

  const [mainResult, shortlistResult, clarificationsResult] = results

  const isLoading = results.some((r) => r.isLoading)
  const hasError = results.some((r) => r.isError)

  // Contexts query — for showing context names inline
  const { data: contexts } = useQuery<CommitmentContextRead[]>({
    queryKey: ['contexts'],
    queryFn: getContexts,
    refetchInterval: 60_000,
    staleTime: 55_000,
  })

  const contextMap = new Map((contexts ?? []).map(c => [c.id, c.name]))

  // Sources query — needed for 3-state empty state
  const { data: sources } = useQuery({
    queryKey: ['sources'],
    queryFn: listSources,
    refetchInterval: 30_000,
    staleTime: 25_000,
  })

  // Stats query
  const { data: stats } = useQuery<StatsRead>({
    queryKey: ['stats'],
    queryFn: getStats,
    refetchInterval: 60_000,
    staleTime: 55_000,
  })

  // Google calendar status (for Upcoming section)
  const { data: googleStatus } = useQuery<{ connected: boolean; expiry: string | null }>({
    queryKey: ['google-status'],
    queryFn: () =>
      fetch('/api/v1/integrations/google/status', {
        headers: { 'Content-Type': 'application/json' },
      }).then((r) => (r.ok ? r.json() : { connected: false, expiry: null })),
    staleTime: 60_000,
  })

  // Upcoming events — only fetch when calendar connected
  const { data: upcomingEvents } = useQuery<EventRead[]>({
    queryKey: ['events'],
    queryFn: getUpcomingEvents,
    enabled: googleStatus?.connected === true,
    refetchInterval: 60_000,
    staleTime: 55_000,
  })

  const allCommitments: CommitmentRead[] = dedupById([
    ...(mainResult.data ?? []),
    ...(shortlistResult.data ?? []),
    ...(clarificationsResult.data ?? []),
  ])

  const hasConnectedSources = (sources ?? []).some((s) => s.is_active)

  // Pre-fetch clarifications for needs_clarification commitments
  const clarificationCommitments = allCommitments.filter(
    (c) => c.lifecycle_state === 'needs_clarification'
  )
  const clarificationResults = useQueries({
    queries: clarificationCommitments.map((c) => ({
      queryKey: ['clarification', c.id],
      queryFn: () => getClarifications(c.id),
      enabled: !isLoading,
    })),
  })

  // Build clarificationMap: commitment_id → first open clarification
  const clarificationMap: Record<string, ClarificationRead> = {}
  clarificationCommitments.forEach((c, i) => {
    const result = clarificationResults[i]
    if (result?.data && result.data.length > 0) {
      clarificationMap[c.id] = result.data[0]
    }
  })

  const dashboardGroups = buildDashboardGroups(allCommitments, contextMap)

  const overviewCounts: OverviewCounts = {
    main: mainResult.data?.length ?? 0,
    shortlist: shortlistResult.data?.length ?? 0,
    clarifications: clarificationsResult.data?.length ?? 0,
  }

  const statsAllZero =
    !stats ||
    (stats.meetings_analyzed === 0 &&
      stats.messages_processed === 0 &&
      stats.emails_captured === 0 &&
      stats.commitments_detected === 0 &&
      stats.sources_connected === 0)

  const showUpcoming =
    googleStatus?.connected === true &&
    upcomingEvents != null &&
    upcomingEvents.length > 0

  async function handleRevert() {
    const buffer = undoBufferRef.current
    if (!buffer.length) return
    await Promise.all(
      buffer.map((entry) => patchCommitment(entry.id, { lifecycle_state: entry.previousState }))
    )
    undoBufferRef.current = []
    setCanRevert(false)
    await queryClient.invalidateQueries({ queryKey: ['surface'] })
  }

  async function handleAddCommitment(e: React.FormEvent) {
    e.preventDefault()
    setAddError(null)
    setAddLoading(true)
    try {
      const body: CommitmentCreate = {
        title: addTitle,
        resolved_owner: addOwner || null,
        resolved_deadline: addDeadline || null,
      }
      await postCommitment(body)
      setAddTitle('')
      setAddOwner('')
      setAddDeadline('')
      setShowAddForm(false)
      await queryClient.invalidateQueries({ queryKey: ['surface'] })
    } catch (err) {
      setAddError(err instanceof Error ? err.message : 'Failed to log commitment')
    } finally {
      setAddLoading(false)
    }
  }

  if (isLoading) return <LoadingSpinner />
  if (hasError)
    return <ErrorBanner message="Failed to load commitments. Please try again." />

  return (
    <div className="min-h-screen bg-white pb-24">
      {/* Header */}
      <div className="px-4 pt-8 pb-4 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-black">Ripples</h1>
          <p className="text-sm text-gray-500 mt-0.5">Your commitments, tracked.</p>
        </div>
        <Link
          to="/settings/integrations"
          className="p-2 rounded-lg text-gray-400 hover:text-black hover:bg-gray-50 transition-colors"
          aria-label="Settings"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="3"/>
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
          </svg>
        </Link>
      </div>

      {/* Source groups */}
      <div className="px-4">
        {allCommitments.length === 0 && (
          <>
            {!hasConnectedSources ? (
              /* No sources connected */
              <div className="mt-4 p-6 rounded-2xl border border-gray-100 bg-gray-50 text-center">
                <p className="text-sm font-medium text-black mb-1">Connect your first source.</p>
                <p className="text-sm text-gray-500 mb-4">
                  Rippled needs a source to watch before it can surface commitments.
                </p>
                <Link
                  to="/settings/sources"
                  className="inline-block px-4 py-2 rounded-lg bg-black text-white text-sm font-medium hover:bg-gray-900 transition-colors"
                >
                  Connect a source →
                </Link>
              </div>
            ) : (
              /* Sources connected but no commitments yet */
              <div className="mt-4 p-6 rounded-2xl border border-gray-100 bg-gray-50 text-center">
                <p className="text-sm font-medium text-black mb-1">Scanning your sources…</p>
                <p className="text-sm text-gray-500">
                  Rippled is scanning your recent messages and meetings. This usually takes a few
                  minutes.
                </p>
                <p className="text-xs text-gray-400 mt-2">
                  New signals will appear here automatically.
                </p>
              </div>
            )}
          </>
        )}
        {allCommitments.length > 0 && (
          <>
            {dashboardGroups.groups.map((group) => {
              const color = getGroupStatusColor(group.commitments)
              return (
                <SourceGroup
                  key={group.key}
                  label={group.label}
                  color={color}
                  commitments={group.commitments}
                  onPress={() =>
                    dashboardGroups.mode === 'source'
                      ? navigate(`/source/${group.key}`)
                      : navigate(`/commitments?context=${group.key}`)
                  }
                  contextMap={contextMap}
                />
              )
            })}
            {dashboardGroups.ungrouped.length > 0 && (
              <SourceGroup
                key="ungrouped"
                label="Other commitments"
                color={getGroupStatusColor(dashboardGroups.ungrouped)}
                commitments={dashboardGroups.ungrouped}
                onPress={() => navigate('/commitments')}
                contextMap={contextMap}
              />
            )}
          </>
        )}
      </div>

      {/* Upcoming events section */}
      {showUpcoming && (
        <div className="px-4 mt-6">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">
            Upcoming
          </p>
          <div className="space-y-2">
            {(upcomingEvents ?? []).slice(0, 5).map((event) => (
              <div
                key={event.id}
                className="flex items-center justify-between px-4 py-3 rounded-xl border border-gray-100 bg-gray-50"
              >
                <div className="min-w-0">
                  <p className="text-sm font-medium text-black truncate">{event.title}</p>
                  {event.location && (
                    <p className="text-xs text-gray-400 truncate">{event.location}</p>
                  )}
                </div>
                <span className="ml-3 shrink-0 text-xs text-gray-400 tabular-nums">
                  {formatRelativeTime(event.starts_at)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Stats row */}
      {!statsAllZero && (
        <div className="px-4 mt-6">
          <div className="flex gap-4 justify-center flex-wrap">
            {stats && stats.meetings_analyzed > 0 && (
              <div className="text-center">
                <p className="text-lg font-bold text-black">{stats.meetings_analyzed}</p>
                <p className="text-xs text-gray-400">meetings</p>
              </div>
            )}
            {stats && stats.messages_processed > 0 && (
              <div className="text-center">
                <p className="text-lg font-bold text-black">{stats.messages_processed}</p>
                <p className="text-xs text-gray-400">messages</p>
              </div>
            )}
            {stats && stats.emails_captured > 0 && (
              <div className="text-center">
                <p className="text-lg font-bold text-black">{stats.emails_captured}</p>
                <p className="text-xs text-gray-400">emails</p>
              </div>
            )}
            {stats && stats.commitments_detected > 0 && (
              <div className="text-center">
                <p className="text-lg font-bold text-black">{stats.commitments_detected}</p>
                <p className="text-xs text-gray-400">detected</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Log commitment button */}
      <div className="px-4 mt-2">
        <button
          type="button"
          onClick={() => setShowAddForm(true)}
          className="w-full py-3 rounded-xl border border-dashed border-gray-200 text-sm text-gray-500 hover:bg-gray-50 active:bg-gray-100 transition-colors"
        >
          + Log commitment
        </button>
      </div>

      {/* Add commitment modal */}
      {showAddForm && (
        <div className="fixed inset-0 bg-black/40 z-20 flex items-end">
          <div className="w-full bg-white rounded-t-2xl p-6">
            <h2 className="text-base font-semibold text-black mb-4">Log a commitment</h2>
            <form onSubmit={handleAddCommitment} className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Title *</label>
                <input
                  type="text"
                  required
                  value={addTitle}
                  onChange={(e) => setAddTitle(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm text-black placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-black"
                  placeholder="What was committed to?"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Owner</label>
                <input
                  type="text"
                  value={addOwner}
                  onChange={(e) => setAddOwner(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm text-black placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-black"
                  placeholder="Who is responsible?"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Deadline</label>
                <input
                  type="date"
                  value={addDeadline}
                  onChange={(e) => setAddDeadline(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm text-black focus:outline-none focus:ring-2 focus:ring-black"
                />
              </div>
              {addError && (
                <p className="text-xs text-red-600">{addError}</p>
              )}
              <div className="flex gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => { setShowAddForm(false); setAddError(null) }}
                  className="flex-1 py-2.5 rounded-lg border border-gray-200 text-sm font-medium text-gray-600"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={addLoading}
                  className="flex-1 py-2.5 rounded-lg bg-black text-white text-sm font-medium disabled:opacity-50"
                >
                  {addLoading ? 'Saving…' : 'Log it'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Overview modal */}
      {showOverview && (
        <div
          className="fixed inset-0 bg-black/40 z-20 flex items-center justify-center px-4"
          onClick={() => setShowOverview(false)}
        >
          <div
            className="w-full max-w-sm bg-white rounded-2xl p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="text-base font-semibold text-black mb-4">Overview</h2>
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-600">Main surface</span>
                <span className="text-sm font-semibold text-black">{overviewCounts.main}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-600">Shortlist</span>
                <span className="text-sm font-semibold text-black">{overviewCounts.shortlist}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-600">Need clarification</span>
                <span className="text-sm font-semibold text-black">{overviewCounts.clarifications}</span>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setShowOverview(false)}
              className="mt-5 w-full py-2.5 rounded-lg bg-black text-white text-sm font-medium"
            >
              Done
            </button>
          </div>
        </div>
      )}

      <BottomBar
        onOverview={() => setShowOverview(true)}
        onRevert={handleRevert}
        canRevert={canRevert}
      />
    </div>
  )
}
