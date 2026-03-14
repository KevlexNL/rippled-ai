import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchEvents, type EventRow } from '../api/events'
import { StatusBadge } from '../components/StatusBadge'
import { Pagination } from '../components/Pagination'

export function EventsPage() {
  const [filters, setFilters] = useState({ event_type: '', status: '' })
  const [limit] = useState(50)
  const [offset, setOffset] = useState(0)

  const { data, isLoading } = useQuery({
    queryKey: ['events', filters, limit, offset],
    queryFn: () => fetchEvents({ ...filters, limit, offset }),
  })

  return (
    <div>
      <div className="flex gap-2 mb-4">
        <select
          className="border rounded px-2 py-1 text-sm"
          value={filters.event_type}
          onChange={e => setFilters(f => ({ ...f, event_type: e.target.value }))}
        >
          <option value="">All types</option>
          <option value="explicit">explicit</option>
          <option value="implicit">implicit</option>
        </select>
        <select
          className="border rounded px-2 py-1 text-sm"
          value={filters.status}
          onChange={e => setFilters(f => ({ ...f, status: e.target.value }))}
        >
          <option value="">All statuses</option>
          <option value="confirmed">confirmed</option>
          <option value="cancelled">cancelled</option>
          <option value="tentative">tentative</option>
        </select>
      </div>

      {isLoading ? <p className="text-sm text-gray-500">Loading...</p> : (
        <>
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-gray-50 text-left text-xs text-gray-500">
                <th className="px-3 py-2 border-b">Title</th>
                <th className="px-3 py-2 border-b">Type</th>
                <th className="px-3 py-2 border-b">Status</th>
                <th className="px-3 py-2 border-b">Starts</th>
                <th className="px-3 py-2 border-b">Links</th>
              </tr>
            </thead>
            <tbody>
              {(data?.items ?? []).map((e: EventRow) => (
                <tr key={e.id} className="border-b hover:bg-gray-50">
                  <td className="px-3 py-2 max-w-xs truncate">{e.title}</td>
                  <td className="px-3 py-2"><StatusBadge value={e.event_type} /></td>
                  <td className="px-3 py-2"><StatusBadge value={e.status} /></td>
                  <td className="px-3 py-2 text-xs text-gray-500">{new Date(e.starts_at).toLocaleString()}</td>
                  <td className="px-3 py-2 text-xs">{e.linked_commitment_count}</td>
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
