import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchCandidates, type CandidateRow } from '../api/candidates'
import { StatusBadge } from '../components/StatusBadge'
import { Pagination } from '../components/Pagination'
import { CandidateDetailPanel } from './CandidateDetailPanel'

export function CandidatesPage() {
  const [filters, setFilters] = useState({ trigger_class: '', model_classification: '' })
  const [limit] = useState(50)
  const [offset, setOffset] = useState(0)
  const [selected, setSelected] = useState<string | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['candidates', filters, limit, offset],
    queryFn: () => fetchCandidates({ ...filters, limit, offset }),
  })

  return (
    <div className="flex gap-4">
      <div className="flex-1">
        <div className="flex gap-2 mb-4">
          <input
            className="border rounded px-2 py-1 text-sm"
            placeholder="Trigger class..."
            value={filters.trigger_class}
            onChange={e => setFilters(f => ({ ...f, trigger_class: e.target.value }))}
          />
          <select
            className="border rounded px-2 py-1 text-sm"
            value={filters.model_classification}
            onChange={e => setFilters(f => ({ ...f, model_classification: e.target.value }))}
          >
            <option value="">All classifications</option>
            {['commitment', 'not_commitment', 'ambiguous', 'error'].map(s => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>

        {isLoading ? <p className="text-sm text-gray-500">Loading...</p> : (
          <>
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="bg-gray-50 text-left text-xs text-gray-500">
                  <th className="px-3 py-2 border-b">Snippet</th>
                  <th className="px-3 py-2 border-b">Trigger</th>
                  <th className="px-3 py-2 border-b">Classification</th>
                  <th className="px-3 py-2 border-b">Confidence</th>
                  <th className="px-3 py-2 border-b">Status</th>
                </tr>
              </thead>
              <tbody>
                {(data?.items ?? []).map((c: CandidateRow) => (
                  <tr
                    key={c.id}
                    className={`border-b hover:bg-gray-50 cursor-pointer ${selected === c.id ? 'bg-blue-50' : ''}`}
                    onClick={() => setSelected(c.id === selected ? null : c.id)}
                  >
                    <td className="px-3 py-2 max-w-xs truncate text-xs text-gray-700">{c.raw_text_snippet ?? '—'}</td>
                    <td className="px-3 py-2 text-xs">{c.trigger_class ?? '—'}</td>
                    <td className="px-3 py-2"><StatusBadge value={c.model_classification} /></td>
                    <td className="px-3 py-2">
                      {c.model_confidence != null && (
                        <div className="w-16 bg-gray-200 rounded-full h-1.5">
                          <div className="bg-blue-500 h-1.5 rounded-full" style={{ width: `${c.model_confidence * 100}%` }} />
                        </div>
                      )}
                    </td>
                    <td className="px-3 py-2">
                      {c.was_promoted ? <span className="text-green-600 text-xs">promoted</span>
                        : c.was_discarded ? <span className="text-red-500 text-xs">discarded</span>
                        : <span className="text-gray-400 text-xs">pending</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pagination total={data?.total ?? 0} limit={limit} offset={offset} onPage={setOffset} />
          </>
        )}
      </div>

      {selected && (
        <div className="w-96 flex-shrink-0">
          <CandidateDetailPanel id={selected} onClose={() => setSelected(null)} />
        </div>
      )}
    </div>
  )
}
