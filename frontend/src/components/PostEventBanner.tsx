import { useState } from 'react'
import { patchDeliveryState } from '../api/commitments'
import { useQueryClient } from '@tanstack/react-query'
import type { CommitmentRead } from '../types'

interface Props {
  commitment: CommitmentRead
  eventTitle: string
  onDismiss: () => void
}

export default function PostEventBanner({ commitment, eventTitle, onDismiss }: Props) {
  const [loading, setLoading] = useState(false)
  const queryClient = useQueryClient()

  async function handleAction(state: string) {
    setLoading(true)
    try {
      await patchDeliveryState(commitment.id, state)
      await queryClient.invalidateQueries({ queryKey: ['commitment', commitment.id] })
      await queryClient.invalidateQueries({ queryKey: ['surface'] })
    } finally {
      setLoading(false)
      onDismiss()
    }
  }

  return (
    <div className="mx-4 mb-4 p-4 rounded-xl bg-blue-50 border border-blue-200">
      <p className="text-xs font-semibold text-blue-600 uppercase tracking-wide mb-1">
        Post-event check-in
      </p>
      <p className="text-sm text-blue-800 mb-3">
        Your event <span className="font-medium">{eventTitle}</span> has passed. How did this commitment go?
      </p>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={loading}
          onClick={() => handleAction('delivered')}
          className="px-3 py-1.5 rounded-lg bg-blue-600 text-white text-xs font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
        >
          Yes, done
        </button>
        <button
          type="button"
          disabled={loading}
          onClick={() => handleAction('draft_sent')}
          className="px-3 py-1.5 rounded-lg border border-blue-300 text-blue-700 text-xs font-medium hover:bg-blue-100 disabled:opacity-50 transition-colors"
        >
          Sent a draft
        </button>
        <button
          type="button"
          disabled={loading}
          onClick={() => handleAction('pending')}
          className="px-3 py-1.5 rounded-lg border border-blue-300 text-blue-700 text-xs font-medium hover:bg-blue-100 disabled:opacity-50 transition-colors"
        >
          Not yet
        </button>
        <button
          type="button"
          disabled={loading}
          onClick={onDismiss}
          className="px-3 py-1.5 rounded-lg text-blue-500 text-xs hover:text-blue-700 disabled:opacity-50 transition-colors"
        >
          Dismiss
        </button>
      </div>
    </div>
  )
}
