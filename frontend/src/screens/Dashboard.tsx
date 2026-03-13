import { useRef, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useQueries, useQueryClient } from '@tanstack/react-query'
import { getSurface } from '../api/surface'
import { postCommitment, patchCommitment } from '../api/commitments'
import type { CommitmentRead, CommitmentCreate } from '../types'
import { dedupById, groupByContextType, getGroupStatusColor, getSourceLabel } from '../utils/grouping'
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
      { queryKey: ['surface', 'main'], queryFn: () => getSurface('main') },
      { queryKey: ['surface', 'shortlist'], queryFn: () => getSurface('shortlist') },
      { queryKey: ['surface', 'clarifications'], queryFn: () => getSurface('clarifications') },
    ],
  })

  const [mainResult, shortlistResult, clarificationsResult] = results

  const isLoading = results.some((r) => r.isLoading)
  const hasError = results.some((r) => r.isError)

  const allCommitments: CommitmentRead[] = dedupById([
    ...(mainResult.data ?? []),
    ...(shortlistResult.data ?? []),
    ...(clarificationsResult.data ?? []),
  ])

  const groups = groupByContextType(allCommitments)
  const sourceTypes = (['meeting', 'slack', 'email', 'unknown'] as const).filter(
    (st) => groups[st].length > 0
  )

  const overviewCounts: OverviewCounts = {
    main: mainResult.data?.length ?? 0,
    shortlist: shortlistResult.data?.length ?? 0,
    clarifications: clarificationsResult.data?.length ?? 0,
  }

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
      <div className="px-4 pt-8 pb-4">
        <h1 className="text-2xl font-bold text-black">Ripples</h1>
        <p className="text-sm text-gray-500 mt-0.5">Your commitments, tracked.</p>
      </div>

      {/* Source groups */}
      <div className="px-4">
        {sourceTypes.length === 0 && (
          <div className="mt-4 p-6 rounded-2xl border border-gray-100 bg-gray-50 text-center">
            <p className="text-sm font-medium text-black mb-1">Rippled has no signals yet.</p>
            <p className="text-sm text-gray-500 mb-4">
              Connect your first source to start capturing commitments.
            </p>
            <Link
              to="/settings/sources"
              className="inline-block px-4 py-2 rounded-lg bg-black text-white text-sm font-medium hover:bg-gray-900 transition-colors"
            >
              Connect a source →
            </Link>
          </div>
        )}
        {sourceTypes.map((st) => {
          const groupCommitments = groups[st]
          const color = getGroupStatusColor(groupCommitments)
          const label = getSourceLabel(st)
          return (
            <SourceGroup
              key={st}
              label={label}
              color={color}
              commitments={groupCommitments}
              onPress={() => navigate(`/source/${st}`)}
            />
          )
        })}
      </div>

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
