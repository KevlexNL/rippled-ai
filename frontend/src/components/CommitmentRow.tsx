import { useState } from 'react'
import type { CommitmentRead } from '../types'
import type { ClarificationRead } from '../api/clarifications'
import { respondToClarification } from '../api/clarifications'
import { getStatusColor } from '../types'
import StatusDot from './StatusDot'
import ContextLine from './ContextLine'
import DeliveryBadge from './DeliveryBadge'
import { useQueryClient } from '@tanstack/react-query'

interface Props {
  commitment: CommitmentRead
  onClick?: () => void
  showReasoning?: boolean
  openClarification?: ClarificationRead | null
}

export default function CommitmentRow({ commitment, onClick, showReasoning = false, openClarification }: Props) {
  const color = getStatusColor(commitment)
  const [answerLoading, setAnswerLoading] = useState(false)
  const queryClient = useQueryClient()

  const hasClarification =
    commitment.lifecycle_state === 'needs_clarification' &&
    openClarification &&
    openClarification.suggested_clarification_prompt

  async function handleAnswer(answer: string) {
    if (!openClarification) return
    setAnswerLoading(true)
    try {
      await respondToClarification(openClarification.id, answer)
      await queryClient.invalidateQueries({ queryKey: ['surface'] })
    } finally {
      setAnswerLoading(false)
    }
  }

  // Get answer options from suggested_values
  const answerOptions: string[] = (() => {
    if (!openClarification?.suggested_values) return []
    const sv = openClarification.suggested_values as Record<string, unknown>
    if (Array.isArray(sv.options)) return sv.options as string[]
    return []
  })()

  return (
    <button
      type="button"
      onClick={hasClarification ? undefined : onClick}
      className={`w-full text-left px-4 py-3 border-b border-gray-100 last:border-b-0 transition-colors ${
        hasClarification ? 'cursor-default' : 'hover:bg-gray-50 active:bg-gray-100'
      }`}
    >
      <div className="flex items-start gap-3">
        <div className="mt-1">
          <StatusDot color={color} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <p className="text-sm font-medium text-black leading-snug">{commitment.title}</p>
            <DeliveryBadge state={commitment.delivery_state} />
          </div>

          {hasClarification ? (
            <div className="mt-1.5">
              <p className="text-xs text-gray-600 mb-1.5">
                {openClarification!.suggested_clarification_prompt}
              </p>
              {answerOptions.length > 0 ? (
                <div className="flex flex-wrap gap-1.5">
                  {answerOptions.slice(0, 3).map((option) => (
                    <button
                      key={option}
                      type="button"
                      disabled={answerLoading}
                      onClick={(e) => {
                        e.stopPropagation()
                        handleAnswer(option)
                      }}
                      className="px-2.5 py-1 rounded-full border border-gray-200 text-xs font-medium text-gray-700 hover:bg-gray-50 hover:border-gray-300 disabled:opacity-50 transition-colors"
                    >
                      {option}
                    </button>
                  ))}
                </div>
              ) : (
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation()
                    onClick?.()
                  }}
                  className="text-xs text-blue-600 hover:text-blue-800"
                >
                  Answer →
                </button>
              )}
            </div>
          ) : (
            <ContextLine commitment={commitment} />
          )}

          {showReasoning && (
            <div className="mt-2 space-y-1">
              {commitment.commitment_explanation && (
                <p className="text-xs text-gray-400 leading-relaxed">
                  {commitment.commitment_explanation}
                </p>
              )}
              {commitment.missing_pieces_explanation && (
                <p className="text-xs text-gray-400 leading-relaxed italic">
                  Missing: {commitment.missing_pieces_explanation}
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </button>
  )
}
