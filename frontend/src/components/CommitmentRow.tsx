import type { CommitmentRead } from '../types'
import { getStatusColor } from '../types'
import StatusDot from './StatusDot'

interface Props {
  commitment: CommitmentRead
  onClick?: () => void
  showReasoning?: boolean
}

function getSubRow(c: CommitmentRead): { label: string; value: string } | null {
  if (c.timing_ambiguity) {
    const value = c.vague_time_phrase ?? c.suggested_due_date ?? 'Unknown'
    return { label: 'Deadline', value }
  }
  if (c.ownership_ambiguity) {
    const value = c.suggested_owner ?? c.resolved_owner ?? 'Unassigned'
    return { label: 'Responsible', value }
  }
  if (c.lifecycle_state === 'delivered') {
    return { label: 'Completed', value: '' }
  }
  return null
}

export default function CommitmentRow({ commitment, onClick, showReasoning = false }: Props) {
  const color = getStatusColor(commitment)
  const sub = getSubRow(commitment)

  return (
    <button
      type="button"
      onClick={onClick}
      className="w-full text-left px-4 py-3 border-b border-gray-100 last:border-b-0 hover:bg-gray-50 active:bg-gray-100 transition-colors"
    >
      <div className="flex items-start gap-3">
        <div className="mt-1">
          <StatusDot color={color} />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-black leading-snug">{commitment.title}</p>
          {sub && (
            <p className="mt-0.5 text-xs text-gray-500">
              <span className="font-medium">{sub.label}</span>
              {sub.value ? `: ${sub.value}` : ''}
            </p>
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
