import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQueries, useQuery, useQueryClient } from '@tanstack/react-query'
import { getCommitment, getSignals, getAmbiguities, patchCommitment } from '../api/commitments'
import { getContexts } from '../api/contexts'
import type { CommitmentSignalRead, CommitmentAmbiguityRead } from '../types'
import StatusDot from '../components/StatusDot'
import LoadingSpinner from '../components/LoadingSpinner'
import ErrorBanner from '../components/ErrorBanner'
import PostEventBanner from '../components/PostEventBanner'
import DeliveryActions from '../components/DeliveryActions'
import ContextSelector from '../components/ContextSelector'
import { confidenceLabel } from '../utils/suggestionLanguage'

const SIGNAL_ROLE_LABELS: Record<string, string> = {
  origin: 'Origin',
  clarification: 'Clarification',
  delivery: 'Delivery',
  closure: 'Closure',
}

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

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    })
  } catch {
    return iso
  }
}

function groupSignalsByRole(
  signals: CommitmentSignalRead[]
): Record<string, CommitmentSignalRead[]> {
  const groups: Record<string, CommitmentSignalRead[]> = {}
  for (const s of signals) {
    const role = s.signal_role || 'unknown'
    if (!groups[role]) groups[role] = []
    groups[role].push(s)
  }
  return groups
}

export default function CommitmentDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [bannerDismissed, setBannerDismissed] = useState(false)

  const results = useQueries({
    queries: [
      {
        queryKey: ['commitment', id],
        queryFn: () => getCommitment(id!),
        enabled: !!id,
      },
      {
        queryKey: ['signals', id],
        queryFn: () => getSignals(id!),
        enabled: !!id,
      },
      {
        queryKey: ['ambiguities', id],
        queryFn: () => getAmbiguities(id!),
        enabled: !!id,
      },
    ],
  })

  const [commitmentResult, signalsResult, ambiguitiesResult] = results

  const { data: contexts } = useQuery({
    queryKey: ['contexts'],
    queryFn: getContexts,
    staleTime: 60_000,
  })

  const isLoading = results.some((r) => r.isLoading)
  const isError = results.some((r) => r.isError)

  const commitment = commitmentResult.data
  const signals = signalsResult.data ?? []
  const ambiguities = ambiguitiesResult.data ?? []

  async function handleApprove() {
    if (!id) return
    await patchCommitment(id, { lifecycle_state: 'active' })
    await queryClient.invalidateQueries({ queryKey: ['commitment', id] })
    await queryClient.invalidateQueries({ queryKey: ['surface'] })
  }

  if (isLoading) return <LoadingSpinner />
  if (isError || !commitment) return <ErrorBanner message="Failed to load commitment." />

  const signalGroups = groupSignalsByRole(signals)
  const signalRoleOrder = ['origin', 'clarification', 'delivery', 'closure']

  // Determine if post-event banner should show
  const now = new Date()
  const pastEvent = commitment.linked_events?.find(
    (e) => e.relationship === 'delivery_at' && new Date(e.starts_at) < now
  ) ?? null
  const showPostEventBanner =
    !bannerDismissed &&
    commitment.post_event_reviewed === false &&
    pastEvent !== null

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
      </div>

      {/* Post-event banner */}
      {showPostEventBanner && pastEvent && (
        <PostEventBanner
          commitment={commitment}
          eventTitle={pastEvent.title}
          onDismiss={() => setBannerDismissed(true)}
        />
      )}

      {/* Title */}
      <div className="px-4 mb-4">
        <h1 className="text-xl font-bold text-black leading-snug">{commitment.title}</h1>
        {commitment.context_type && (
          <p className="mt-1 text-xs text-gray-400 uppercase tracking-wide">
            {commitment.context_type}
          </p>
        )}
      </div>

      {/* Context selector */}
      {contexts && (
        <div className="mx-4 mb-4">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1">
            Context
          </p>
          <ContextSelector
            commitment={commitment}
            contexts={contexts}
            onUpdate={() => {
              queryClient.invalidateQueries({ queryKey: ['commitment', id] })
              queryClient.invalidateQueries({ queryKey: ['contexts'] })
            }}
          />
        </div>
      )}

      {/* Commitment text blockquote */}
      {commitment.commitment_text && (
        <div className="mx-4 mb-5 pl-4 border-l-2 border-black/20">
          <p className="text-sm text-gray-600 leading-relaxed italic">
            {commitment.commitment_text}
          </p>
        </div>
      )}

      {/* Explanation */}
      {commitment.commitment_explanation && (
        <div className="mx-4 mb-5 p-4 rounded-xl bg-gray-50">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1">
            Rippled's interpretation
          </p>
          <p className="text-sm text-gray-700 leading-relaxed italic">
            {commitment.commitment_explanation}
          </p>
          <p className="text-[10px] text-gray-400 mt-1">
            {confidenceLabel(commitment.confidence_commitment)}
          </p>
        </div>
      )}

      {/* Missing pieces */}
      {commitment.missing_pieces_explanation && (
        <div className="mx-4 mb-5 p-4 rounded-xl bg-yellow-50 border border-yellow-100">
          <p className="text-xs font-semibold text-yellow-600 uppercase tracking-wide mb-1">
            Missing pieces
          </p>
          <p className="text-sm text-yellow-800 leading-relaxed">
            {commitment.missing_pieces_explanation}
          </p>
        </div>
      )}

      {/* Ambiguities */}
      {ambiguities.length > 0 && (
        <div className="mx-4 mb-5">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">
            Ambiguities
          </p>
          <div className="rounded-xl border border-gray-100 overflow-hidden divide-y divide-gray-100">
            {ambiguities.map((a: CommitmentAmbiguityRead) => (
              <div key={a.id} className="flex items-start gap-3 px-4 py-3">
                <div className="mt-0.5">
                  <StatusDot
                    color={getAmbiguityColor(a.ambiguity_type, a.is_resolved)}
                    size="sm"
                  />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium text-gray-700">
                    {formatAmbiguityType(a.ambiguity_type)}
                  </p>
                  {a.description && (
                    <p className="text-xs text-gray-400 mt-0.5 leading-relaxed">{a.description}</p>
                  )}
                  {a.is_resolved && (
                    <p className="text-xs text-green-600 mt-0.5">Resolved</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Signals by role */}
      {signals.length > 0 && (
        <div className="mx-4 mb-5">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">
            Evidence
          </p>
          {signalRoleOrder
            .filter((role) => signalGroups[role]?.length > 0)
            .map((role) => (
              <div key={role} className="mb-3">
                <p className="text-xs font-medium text-gray-500 mb-1.5">
                  {SIGNAL_ROLE_LABELS[role] ?? role}
                </p>
                <div className="rounded-xl border border-gray-100 overflow-hidden divide-y divide-gray-100">
                  {signalGroups[role].map((s: CommitmentSignalRead) => (
                    <div key={s.id} className="px-4 py-3">
                      {s.interpretation_note && (
                        <p className="text-sm text-gray-700 leading-relaxed">
                          {s.interpretation_note}
                        </p>
                      )}
                      <p className="text-xs text-gray-400 mt-1">{formatDate(s.created_at)}</p>
                    </div>
                  ))}
                </div>
              </div>
            ))}
        </div>
      )}

      {/* Delivery actions */}
      <DeliveryActions
        commitment={commitment}
        onUpdate={() => queryClient.invalidateQueries({ queryKey: ['commitment', id] })}
      />

      {/* Bottom bar */}
      <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-100 px-4 py-2 pb-safe flex items-center gap-2 z-10">
        <button
          type="button"
          onClick={() => navigate(-1)}
          className="flex-1 py-2.5 rounded-lg border border-gray-200 text-sm font-medium text-gray-600 hover:bg-gray-50 active:bg-gray-100 transition-colors"
        >
          Go back
        </button>
        {commitment.lifecycle_state === 'proposed' && (
          <button
            type="button"
            onClick={handleApprove}
            className="flex-1 py-2.5 rounded-lg bg-black text-white text-sm font-medium hover:bg-gray-900 active:bg-gray-800 transition-colors"
          >
            Approve
          </button>
        )}
      </div>
    </div>
  )
}
