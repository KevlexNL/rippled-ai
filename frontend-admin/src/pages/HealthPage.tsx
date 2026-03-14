import React from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchHealth } from '../api/health'
import { StatusBadge } from '../components/StatusBadge'

export function HealthPage() {
  const { data, isLoading, error } = useQuery({ queryKey: ['health'], queryFn: fetchHealth, refetchInterval: 30_000 })

  if (isLoading) return <p className="text-sm text-gray-500">Loading...</p>
  if (error) return <p className="text-sm text-red-500">Error loading health data</p>
  if (!data) return null

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold">System Health</h2>

      {data.error_count_24h > 0 && (
        <div className="bg-red-50 border border-red-200 rounded p-3 text-sm text-red-700">
          {data.error_count_24h} detection error(s) in the last 24h
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {Object.entries(data.counts).map(([key, val]) => (
          <div key={key} className="bg-white border rounded p-3">
            <p className="text-xs text-gray-500">{key.replace(/_/g, ' ')}</p>
            <p className="text-2xl font-bold text-gray-900">{val}</p>
          </div>
        ))}
      </div>

      <div>
        <h3 className="text-sm font-medium mb-2">Celery Tasks</h3>
        <div className="space-y-2">
          {data.tasks.map(t => (
            <div key={t.name} className="flex items-center gap-3 bg-white border rounded px-3 py-2 text-sm">
              <StatusBadge value={t.status} />
              <span className="font-mono">{t.name}</span>
              <span className="text-gray-400 text-xs ml-auto">
                {t.last_run_at ? new Date(t.last_run_at).toLocaleString() : 'never'}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
