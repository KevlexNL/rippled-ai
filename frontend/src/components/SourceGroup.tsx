import { useNavigate } from 'react-router-dom'
import type { CommitmentRead } from '../types'
import StatusDot from './StatusDot'
import CommitmentRow from './CommitmentRow'

interface Props {
  label: string
  color: 'red' | 'yellow' | 'green'
  commitments: CommitmentRead[]
  onPress: () => void
}

export default function SourceGroup({ label, color, commitments, onPress }: Props) {
  const navigate = useNavigate()

  return (
    <div className="mb-4 rounded-xl border border-gray-100 overflow-hidden shadow-sm">
      <button
        type="button"
        onClick={onPress}
        className="w-full flex items-center justify-between px-4 py-3 bg-white hover:bg-gray-50 active:bg-gray-100 transition-colors"
      >
        <div className="flex items-center gap-2">
          <StatusDot color={color} />
          <span className="text-sm font-semibold text-black">{label}</span>
          <span className="text-xs text-gray-400 font-normal">({commitments.length})</span>
        </div>
        <span className="text-gray-400 text-sm">›</span>
      </button>
      <div className="divide-y divide-gray-100">
        {commitments.map((c) => (
          <CommitmentRow
            key={c.id}
            commitment={c}
            onClick={() => navigate(`/commitment/${c.id}`)}
          />
        ))}
      </div>
    </div>
  )
}
