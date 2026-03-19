import { useState } from 'react'
import { patchCommitment } from '../api/commitments'
import type { CommitmentRead } from '../types'
import type { CommitmentContextRead } from '../api/contexts'

interface ContextSelectorProps {
  commitment: CommitmentRead
  contexts: CommitmentContextRead[]
  onUpdate: () => void
}

export default function ContextSelector({ commitment, contexts, onUpdate }: ContextSelectorProps) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (contexts.length === 0) {
    return <span className="text-xs text-gray-400">No contexts available</span>
  }

  async function handleChange(value: string) {
    const contextId = value || null
    setLoading(true)
    setError(null)
    try {
      await patchCommitment(commitment.id, { context_id: contextId })
      onUpdate()
    } catch {
      setError('Failed to update context')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <select
        value={commitment.context_id ?? ''}
        onChange={(e) => handleChange(e.target.value)}
        disabled={loading}
        className="w-full text-sm text-black bg-gray-50 border border-gray-200 rounded-lg px-3 py-1.5 focus:outline-none focus:border-black transition-colors disabled:opacity-50"
      >
        <option value="">No context</option>
        {contexts.map((ctx) => (
          <option key={ctx.id} value={ctx.id}>{ctx.name}</option>
        ))}
      </select>
      {error && (
        <p className="text-xs text-red-600 mt-1">{error}</p>
      )}
    </div>
  )
}
