import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchSurfacingAudit, type SurfacingAuditRow } from '../api/surfacing'
import { StatusBadge } from '../components/StatusBadge'
import { Pagination } from '../components/Pagination'

export function SurfacingPage() {
  const [filters, setFilters] = useState({ commitment_id: '', new_surfaced_as: '' })
  const [limit] = useState(50)
  const [offset, setOffset] = useState(0)

  const { data, isLoading } = useQuery({
    queryKey: ['surfacing-audit', filters, limit, offset],
    queryFn: () => fetchSurfacingAudit({ ...filters, limit, offset }),
  })

  return (
    <div>
      <div className="flex gap-2 mb-4">
        <input
          className="border rounded px-2 py-1 text-sm"
          placeholder="Commitment ID..."
          value={filters.commitment_id}
          onChange={e => setFilters(f => ({ ...f, commitment_id: e.target.value }))}
        />
        <select
          className="border rounded px-2 py-1 text-sm"
          value={filters.new_surfaced_as}
          onChange={e => setFilters(f => ({ ...f, new_surfaced_as: e.target.value }))}
        >
          <option value="">All surfaces</option>
          <option value="main">main</option>
          <option value="shortlist">shortlist</option>
          <option value="clarifications">clarifications</option>
        </select>
      </div>

      {isLoading ? <p className="text-sm text-gray-500">Loading...</p> : (
        <>
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-gray-50 text-left text-xs text-gray-500">
                <th className="px-3 py-2 border-b">Commitment</th>
                <th className="px-3 py-2 border-b">Transition</th>
                <th className="px-3 py-2 border-b">Score</th>
                <th className="px-3 py-2 border-b">Reason</th>
                <th className="px-3 py-2 border-b">When</th>
              </tr>
            </thead>
            <tbody>
              {(data?.items ?? []).map((a: SurfacingAuditRow) => (
                <tr key={a.id} className="border-b hover:bg-gray-50">
                  <td className="px-3 py-2 text-xs max-w-xs truncate">{a.commitment_title_snippet}</td>
                  <td className="px-3 py-2">
                    <span className="flex items-center gap-1 text-xs">
                      <StatusBadge value={a.old_surfaced_as} />
                      <span>→</span>
                      <StatusBadge value={a.new_surfaced_as} />
                    </span>
                  </td>
                  <td className="px-3 py-2 text-xs">{a.priority_score?.toFixed(1) ?? '—'}</td>
                  <td className="px-3 py-2 text-xs text-gray-600 max-w-xs truncate">{a.reason ?? '—'}</td>
                  <td className="px-3 py-2 text-xs text-gray-400">{new Date(a.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <Pagination total={data?.total ?? 0} limit={limit} offset={offset} onPage={setOffset} />
        </>
      )}
    </div>
  )
}
