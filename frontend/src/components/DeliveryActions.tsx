import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { patchDeliveryState, patchCommitment } from '../api/commitments'
import type { CommitmentRead } from '../types'

interface Props {
  commitment: CommitmentRead
  onUpdate: () => void
}

export default function DeliveryActions({ commitment: c, onUpdate }: Props) {
  const [loading, setLoading] = useState(false)
  const queryClient = useQueryClient()

  async function act(fn: () => Promise<unknown>) {
    setLoading(true)
    try {
      await fn()
      await queryClient.invalidateQueries({ queryKey: ['commitment', c.id] })
      await queryClient.invalidateQueries({ queryKey: ['surface'] })
      onUpdate()
    } finally {
      setLoading(false)
    }
  }

  const state = c.delivery_state
  const lifecycle = c.lifecycle_state

  // Don't show actions if already done
  if (lifecycle === 'delivered' || lifecycle === 'closed' || lifecycle === 'discarded') return null

  const btnBase = 'px-3 py-1.5 rounded-lg text-xs font-medium transition-colors disabled:opacity-50'
  const btnSecondary = `${btnBase} border border-gray-200 text-gray-700 hover:bg-gray-50`
  const btnPrimary = `${btnBase} bg-black text-white hover:bg-gray-900`
  const btnDanger = `${btnBase} border border-red-200 text-red-600 hover:bg-red-50`

  return (
    <div className="mx-4 mb-4">
      <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">Actions</p>
      <div className="flex flex-wrap gap-2">
        {!state && (
          <>
            <button
              type="button"
              disabled={loading}
              onClick={() => act(() => patchDeliveryState(c.id, 'draft_sent'))}
              className={btnSecondary}
            >
              Sent a draft
            </button>
            <button
              type="button"
              disabled={loading}
              onClick={() => act(() => patchDeliveryState(c.id, 'delivered'))}
              className={btnPrimary}
            >
              Done
            </button>
            <button
              type="button"
              disabled={loading}
              onClick={() => act(() => patchCommitment(c.id, { lifecycle_state: 'discarded' }))}
              className={btnDanger}
            >
              Not mine
            </button>
          </>
        )}
        {state === 'draft_sent' && (
          <>
            <button
              type="button"
              disabled={loading}
              onClick={() => act(() => patchDeliveryState(c.id, 'delivered'))}
              className={btnPrimary}
            >
              Sent final
            </button>
            <button
              type="button"
              disabled={loading}
              onClick={() => setLoading(false)}
              className={btnSecondary}
            >
              Still in progress
            </button>
          </>
        )}
        {state === 'acknowledged' && (
          <>
            <button
              type="button"
              disabled={loading}
              onClick={() => act(() => patchDeliveryState(c.id, 'delivered'))}
              className={btnPrimary}
            >
              Done
            </button>
            <button
              type="button"
              disabled={loading}
              onClick={() => act(() => patchDeliveryState(c.id, 'rescheduled'))}
              className={btnSecondary}
            >
              Pushed back
            </button>
          </>
        )}
      </div>
    </div>
  )
}
