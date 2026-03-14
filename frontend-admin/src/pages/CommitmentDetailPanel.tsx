import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchCommitment, overrideCommitmentState } from '../api/commitments'
import { StatusBadge } from '../components/StatusBadge'
import { JsonViewer } from '../components/JsonViewer'

interface Props {
  id: string
  onClose: () => void
}

export function CommitmentDetailPanel({ id, onClose }: Props) {
  const qc = useQueryClient()
  const { data, isLoading } = useQuery({ queryKey: ['commitment', id], queryFn: () => fetchCommitment(id) })
  const [overrideForm, setOverrideForm] = useState({ lifecycle_state: '', delivery_state: '', reason: '' })
  const mutation = useMutation({
    mutationFn: () => overrideCommitmentState(id, {
      lifecycle_state: overrideForm.lifecycle_state || undefined,
      delivery_state: overrideForm.delivery_state || undefined,
      reason: overrideForm.reason,
    }),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ['commitments'] }); void qc.invalidateQueries({ queryKey: ['commitment', id] }) },
  })

  if (isLoading) return <div className="border rounded p-4 bg-white text-sm text-gray-500">Loading...</div>
  if (!data) return null

  const d = data as Record<string, unknown>
  const c = d.commitment as Record<string, unknown>

  return (
    <div className="border rounded bg-white p-4 text-sm space-y-4">
      <div className="flex justify-between items-start">
        <h3 className="font-medium truncate">{c.title as string}</h3>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-700 ml-2">✕</button>
      </div>

      <div className="grid grid-cols-2 gap-1 text-xs">
        <span className="text-gray-500">State</span><StatusBadge value={c.lifecycle_state as string} />
        <span className="text-gray-500">Surface</span><StatusBadge value={c.surfaced_as as string | null} />
        <span className="text-gray-500">Score</span><span>{c.priority_score != null ? Number(c.priority_score).toFixed(1) : '—'}</span>
        <span className="text-gray-500">Counterparty</span><span>{(c.counterparty_type as string) ?? '—'}</span>
      </div>

      {(d.surfacing_audit as unknown[])?.length > 0 && (
        <div>
          <p className="text-xs font-medium text-gray-500 mb-1">Surfacing Audit</p>
          {(d.surfacing_audit as Array<Record<string, unknown>>).slice(0, 3).map((a, i) => (
            <div key={i} className="text-xs text-gray-600 border-b py-1">
              {a.old_surfaced_as as string ?? 'none'} → {a.new_surfaced_as as string ?? 'none'} — {a.reason as string}
            </div>
          ))}
        </div>
      )}

      {!!d.source_snippet && (
        <div>
          <p className="text-xs font-medium text-gray-500 mb-1">Source snippet</p>
          <p className="text-xs text-gray-700 bg-gray-50 rounded p-2 line-clamp-3">{d.source_snippet as string}</p>
        </div>
      )}

      <div className="border-t pt-3">
        <p className="text-xs font-medium text-gray-500 mb-2">State Override (bypasses validation)</p>
        <div className="space-y-2">
          <select
            className="w-full border rounded px-2 py-1 text-xs"
            value={overrideForm.lifecycle_state}
            onChange={e => setOverrideForm(f => ({ ...f, lifecycle_state: e.target.value }))}
          >
            <option value="">— no change —</option>
            {['proposed', 'active', 'needs_clarification', 'delivered', 'closed', 'discarded'].map(s => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
          <input
            className="w-full border rounded px-2 py-1 text-xs"
            placeholder="Reason (required)"
            value={overrideForm.reason}
            onChange={e => setOverrideForm(f => ({ ...f, reason: e.target.value }))}
          />
          <button
            className="w-full bg-orange-500 text-white rounded px-3 py-1 text-xs font-medium hover:bg-orange-600 disabled:opacity-50"
            onClick={() => mutation.mutate()}
            disabled={!overrideForm.reason || mutation.isPending}
          >
            {mutation.isPending ? 'Saving...' : 'Apply Override'}
          </button>
        </div>
      </div>
    </div>
  )
}
