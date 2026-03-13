import { useNavigate, useParams } from 'react-router-dom'
import { useQuery, useQueries } from '@tanstack/react-query'
import { getCommitments, getAmbiguities } from '../api/commitments'
import type { CommitmentAmbiguityRead } from '../types'
import { groupByTargetEntity, getSourceLabel } from '../utils/grouping'
import CommitmentRow from '../components/CommitmentRow'
import StatusDot from '../components/StatusDot'
import LoadingSpinner from '../components/LoadingSpinner'
import ErrorBanner from '../components/ErrorBanner'

function getAmbiguityColor(ambiguityType: string, isResolved: boolean): 'red' | 'yellow' | 'green' {
  if (isResolved) return 'green'
  const redTypes = ['owner_missing', 'timing_missing', 'deliverable_unclear']
  const yellowTypes = ['timing_vague', 'owner_vague_collective']
  if (redTypes.includes(ambiguityType)) return 'red'
  if (yellowTypes.includes(ambiguityType)) return 'yellow'
  return 'yellow'
}

function formatAmbiguityType(type: string): string {
  return type
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}

export default function Log() {
  const { sourceType } = useParams<{ sourceType: string }>()
  const navigate = useNavigate()

  const { data, isLoading, isError } = useQuery({
    queryKey: ['commitments', 'log', sourceType],
    queryFn: () => getCommitments({ lifecycle_state: 'active', limit: 50 }),
  })

  const filtered = (data ?? []).filter((c) => c.context_type === sourceType)
  const groups = groupByTargetEntity(filtered)
  const groupEntries = Object.entries(groups)

  // Fetch ambiguities for all visible commitments
  const ambiguityResults = useQueries({
    queries: filtered.map((c) => ({
      queryKey: ['ambiguities', c.id],
      queryFn: () => getAmbiguities(c.id),
      enabled: !isLoading && !isError,
    })),
  })

  // Map commitment id → ambiguities
  const ambiguitiesMap: Record<string, CommitmentAmbiguityRead[]> = {}
  filtered.forEach((c, i) => {
    ambiguitiesMap[c.id] = ambiguityResults[i]?.data ?? []
  })

  if (isLoading) return <LoadingSpinner />
  if (isError) return <ErrorBanner message="Failed to load commitments." />

  const label = getSourceLabel(sourceType ?? 'unknown')

  return (
    <div className="min-h-screen bg-white pb-8">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 pt-8 pb-4">
        <button
          type="button"
          onClick={() => navigate(-1)}
          className="text-sm text-gray-500 hover:text-black transition-colors"
        >
          ‹ Back
        </button>
        <div>
          <h1 className="text-lg font-semibold text-black">{label}</h1>
          <p className="text-xs text-gray-400">Full reasoning log</p>
        </div>
      </div>

      {/* Groups with reasoning */}
      <div className="px-4">
        {groupEntries.length === 0 && (
          <p className="text-sm text-gray-400 text-center py-12">
            No commitments from this source.
          </p>
        )}
        {groupEntries.map(([entity, commitments]) => (
          <div key={entity} className="mb-6">
            <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">
              {entity}
            </h2>
            <div className="rounded-xl border border-gray-100 overflow-hidden shadow-sm">
              {commitments.map((c) => {
                const ambiguities = ambiguitiesMap[c.id] ?? []
                return (
                  <div key={c.id} className="border-b border-gray-100 last:border-b-0">
                    <CommitmentRow
                      commitment={c}
                      onClick={() => navigate(`/commitment/${c.id}`)}
                      showReasoning
                    />
                    {ambiguities.length > 0 && (
                      <div className="px-4 pb-3 space-y-2">
                        <p className="text-xs font-medium text-gray-400 uppercase tracking-wide">
                          Ambiguities
                        </p>
                        {ambiguities.map((a) => (
                          <div key={a.id} className="flex items-start gap-2">
                            <div className="mt-0.5">
                              <StatusDot
                                color={getAmbiguityColor(a.ambiguity_type, a.is_resolved)}
                                size="sm"
                              />
                            </div>
                            <div className="flex-1 min-w-0">
                              <span className="text-xs font-medium text-gray-600">
                                {formatAmbiguityType(a.ambiguity_type)}
                              </span>
                              {a.description && (
                                <p className="text-xs text-gray-400 leading-relaxed mt-0.5">
                                  {a.description}
                                </p>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
