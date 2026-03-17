import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchCommitments, type CommitmentRow } from '../api/commitments'
import { StatusBadge } from '../components/StatusBadge'
import { Pagination } from '../components/Pagination'
import { CommitmentDetailPanel } from './CommitmentDetailPanel'

export function CommitmentsPage() {
  const [filters, setFilters] = useState({ lifecycle_state: '', surfaced_as: '', sort: 'priority_score' })
  const [limit] = useState(50)
  const [offset, setOffset] = useState(0)
  const [selected, setSelected] = useState<string | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['commitments', filters, limit, offset],
    queryFn: () => fetchCommitments({ ...filters, limit, offset }),
  })

  return (
    <div className="flex gap-4">
      <div className="flex-1">
        <div className="flex gap-2 mb-4 flex-wrap">
          <select
            className="border rounded px-2 py-1 text-sm"
            value={filters.lifecycle_state}
            onChange={e => setFilters(f => ({ ...f, lifecycle_state: e.target.value }))}
          >
            <option value="">All states</option>
            {['proposed', 'active', 'needs_clarification', 'delivered', 'closed', 'discarded'].map(s => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
          <select
            className="border rounded px-2 py-1 text-sm"
            value={filters.surfaced_as}
            onChange={e => setFilters(f => ({ ...f, surfaced_as: e.target.value }))}
          >
            <option value="">All surfaces</option>
            {['main', 'shortlist', 'clarifications'].map(s => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
          <select
            className="border rounded px-2 py-1 text-sm"
            value={filters.sort}
            onChange={e => setFilters(f => ({ ...f, sort: e.target.value }))}
          >
            <option value="priority_score">Sort: Priority</option>
            <option value="created_at">Sort: Created</option>
            <option value="resolved_deadline">Sort: Deadline</option>
          </select>
        </div>

        {isLoading ? (
          <p className="text-sm text-gray-500">Loading...</p>
        ) : (
          <>
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="bg-gray-50 text-left text-xs text-gray-500">
                  <th className="px-3 py-2 border-b">Title</th>
                  <th className="px-3 py-2 border-b">State</th>
                  <th className="px-3 py-2 border-b">Surface</th>
                  <th className="px-3 py-2 border-b">Score</th>
                  <th className="px-3 py-2 border-b">Deadline</th>
                </tr>
              </thead>
              <tbody>
                {(data?.items ?? []).map((c: CommitmentRow) => (
                  <tr
                    key={c.id}
                    className={`border-b hover:bg-gray-50 cursor-pointer ${selected === c.id ? 'bg-blue-50' : ''}`}
                    onClick={() => setSelected(c.id === selected ? null : c.id)}
                  >
                    <td className="px-3 py-2 max-w-xs truncate">{c.title}</td>
                    <td className="px-3 py-2"><StatusBadge value={c.lifecycle_state} /></td>
                    <td className="px-3 py-2"><StatusBadge value={c.surfaced_as} /></td>
                    <td className="px-3 py-2">{c.priority_score?.toFixed(1) ?? '—'}</td>
                    <td className="px-3 py-2 text-xs text-gray-500">
                      {c.resolved_deadline ? new Date(c.resolved_deadline).toLocaleDateString() : '—'}
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
          <CommitmentDetailPanel id={selected} onClose={() => setSelected(null)} />
        </div>
      )}
    </div>
  )
}
