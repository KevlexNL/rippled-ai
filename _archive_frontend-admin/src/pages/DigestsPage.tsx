import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchDigests, fetchDigest, type DigestRow } from '../api/digests'
import { StatusBadge } from '../components/StatusBadge'
import { Pagination } from '../components/Pagination'
import { JsonViewer } from '../components/JsonViewer'

export function DigestsPage() {
  const [limit] = useState(50)
  const [offset, setOffset] = useState(0)
  const [selected, setSelected] = useState<string | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['digests', limit, offset],
    queryFn: () => fetchDigests(limit, offset),
  })

  const detailQuery = useQuery({
    queryKey: ['digest', selected],
    queryFn: () => fetchDigest(selected!),
    enabled: !!selected,
  })

  return (
    <div className="flex gap-4">
      <div className="flex-1">
        {isLoading ? <p className="text-sm text-gray-500">Loading...</p> : (
          <>
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="bg-gray-50 text-left text-xs text-gray-500">
                  <th className="px-3 py-2 border-b">Sent</th>
                  <th className="px-3 py-2 border-b">Commitments</th>
                  <th className="px-3 py-2 border-b">Method</th>
                  <th className="px-3 py-2 border-b">Status</th>
                </tr>
              </thead>
              <tbody>
                {(data?.items ?? []).map((d: DigestRow) => (
                  <tr
                    key={d.id}
                    className={`border-b hover:bg-gray-50 cursor-pointer ${selected === d.id ? 'bg-blue-50' : ''}`}
                    onClick={() => setSelected(d.id === selected ? null : d.id)}
                  >
                    <td className="px-3 py-2 text-xs">{new Date(d.sent_at).toLocaleString()}</td>
                    <td className="px-3 py-2">{d.commitment_count}</td>
                    <td className="px-3 py-2 text-xs">{d.delivery_method}</td>
                    <td className="px-3 py-2"><StatusBadge value={d.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Pagination total={data?.total ?? 0} limit={limit} offset={offset} onPage={setOffset} />
          </>
        )}
      </div>

      {selected && (
        <div className="w-96 flex-shrink-0 border rounded bg-white p-4">
          <div className="flex justify-between mb-3">
            <h3 className="font-medium text-sm">Digest Detail</h3>
            <button onClick={() => setSelected(null)} className="text-gray-400 hover:text-gray-700 text-sm">✕</button>
          </div>
          {detailQuery.isLoading ? <p className="text-sm text-gray-500">Loading...</p> : (
            <JsonViewer data={(detailQuery.data as Record<string, unknown>)?.digest_content} title="digest_content" />
          )}
        </div>
      )}
    </div>
  )
}
