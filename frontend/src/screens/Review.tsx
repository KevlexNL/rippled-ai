import { useNavigate, useParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { getCommitments, patchCommitment } from '../api/commitments'
import type { CommitmentRead } from '../types'
import { groupByTargetEntity, getSourceLabel } from '../utils/grouping'
import CommitmentRow from '../components/CommitmentRow'
import LoadingSpinner from '../components/LoadingSpinner'
import ErrorBanner from '../components/ErrorBanner'

export default function Review() {
  const { sourceType } = useParams<{ sourceType: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const { data, isLoading, isError } = useQuery({
    queryKey: ['commitments', 'active', sourceType],
    queryFn: () => getCommitments({ lifecycle_state: 'active', limit: 50 }),
  })

  if (isLoading) return <LoadingSpinner />
  if (isError) return <ErrorBanner message="Failed to load commitments." />

  const filtered = (data ?? []).filter((c) => c.context_type === sourceType)
  const groups = groupByTargetEntity(filtered)
  const groupEntries = Object.entries(groups)

  const proposed = (data ?? []).filter(
    (c) => c.context_type === sourceType && c.lifecycle_state === 'proposed'
  )

  async function handleApproveAll() {
    if (!proposed.length) return
    await Promise.all(
      proposed.map((c) => patchCommitment(c.id, { lifecycle_state: 'active' }))
    )
    await queryClient.invalidateQueries({ queryKey: ['commitments', 'active', sourceType] })
  }

  const label = getSourceLabel(sourceType ?? 'unknown')

  return (
    <div className="min-h-screen bg-white pb-24">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 pt-8 pb-4">
        <button
          type="button"
          onClick={() => navigate(-1)}
          className="text-sm text-gray-500 hover:text-black transition-colors"
        >
          ‹ Back
        </button>
        <h1 className="text-lg font-semibold text-black">{label}</h1>
      </div>

      {/* Groups */}
      <div className="px-4">
        {groupEntries.length === 0 && (
          <p className="text-sm text-gray-400 text-center py-12">
            No commitments from this source.
          </p>
        )}
        {groupEntries.map(([entity, commitments]) => (
          <div key={entity} className="mb-5">
            <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">
              {entity}
            </h2>
            <div className="rounded-xl border border-gray-100 overflow-hidden shadow-sm">
              {commitments.map((c: CommitmentRead) => (
                <CommitmentRow
                  key={c.id}
                  commitment={c}
                  onClick={() => navigate(`/commitment/${c.id}`)}
                />
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Bottom action bar */}
      <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-100 px-4 py-2 pb-safe flex items-center gap-2 z-10">
        <button
          type="button"
          onClick={handleApproveAll}
          disabled={proposed.length === 0}
          className="flex-1 py-2.5 rounded-lg bg-black text-white text-sm font-medium hover:bg-gray-900 active:bg-gray-800 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Approve all ({proposed.length})
        </button>
        <button
          type="button"
          disabled
          className="flex-1 py-2.5 rounded-lg border border-gray-100 text-sm font-medium text-gray-300 cursor-not-allowed"
        >
          Share update
        </button>
      </div>
    </div>
  )
}
