import React from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchCandidate } from '../api/candidates'
import { JsonViewer } from '../components/JsonViewer'

interface Props {
  id: string
  onClose: () => void
}

export function CandidateDetailPanel({ id, onClose }: Props) {
  const { data, isLoading } = useQuery({ queryKey: ['candidate', id], queryFn: () => fetchCandidate(id) })

  if (isLoading) return <div className="border rounded p-4 bg-white text-sm text-gray-500">Loading...</div>
  if (!data) return null

  const c = data as Record<string, unknown>

  return (
    <div className="border rounded bg-white p-4 text-sm space-y-3">
      <div className="flex justify-between">
        <h3 className="font-medium">Candidate Detail</h3>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-700">✕</button>
      </div>
      <div className="grid grid-cols-2 gap-1 text-xs">
        <span className="text-gray-500">Classification</span><span>{(c.model_classification as string) ?? '—'}</span>
        <span className="text-gray-500">Confidence</span><span>{c.model_confidence != null ? Number(c.model_confidence).toFixed(3) : '—'}</span>
        <span className="text-gray-500">Method</span><span>{(c.detection_method as string) ?? '—'}</span>
        <span className="text-gray-500">Source type</span><span>{(c.source_type as string) ?? '—'}</span>
      </div>
      {!!c.raw_text && <p className="text-xs text-gray-700 bg-gray-50 p-2 rounded">{c.raw_text as string}</p>}
      {!!c.model_explanation && <p className="text-xs text-gray-600 italic">{c.model_explanation as string}</p>}
      <JsonViewer data={c.context_window} title="context_window" />
    </div>
  )
}
