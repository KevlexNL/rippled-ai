import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPatch } from '../../lib/apiClient'
import LoadingSpinner from '../../components/LoadingSpinner'
import ErrorBanner from '../../components/ErrorBanner'

interface Source {
  id: string
  source_type: string
  display_name: string
  is_active: boolean
}

const SOURCE_ICONS: Record<string, string> = {
  email: '✉',
  slack: '#',
  meeting: '🎤',
}

const ALL_SOURCE_TYPES = ['email', 'slack', 'meeting']

function sourceIcon(type: string): string {
  return SOURCE_ICONS[type] ?? '•'
}

function sourceDisplayName(type: string): string {
  const names: Record<string, string> = {
    email: 'Email',
    slack: 'Slack',
    meeting: 'Meetings',
  }
  return names[type] ?? type
}

export default function SourcesSettingsScreen() {
  const queryClient = useQueryClient()
  const [disconnecting, setDisconnecting] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const { data: sources, isLoading, isError } = useQuery<Source[]>({
    queryKey: ['sources'],
    queryFn: () => apiGet<Source[]>('/api/v1/sources'),
  })

  async function handleDisconnect(source: Source) {
    setError(null)
    setDisconnecting(source.id)
    try {
      await apiPatch(`/api/v1/sources/${source.id}`, { is_active: false })
      await queryClient.invalidateQueries({ queryKey: ['sources'] })
    } catch {
      setError(`Failed to disconnect ${source.display_name}. Please try again.`)
    } finally {
      setDisconnecting(null)
    }
  }

  if (isLoading) return <LoadingSpinner />
  if (isError) return <ErrorBanner message="Failed to load sources. Please try again." />

  const activeSources = sources ?? []
  const connectedTypes = new Set(activeSources.map((s) => s.source_type))
  const unconnectedTypes = ALL_SOURCE_TYPES.filter((t) => !connectedTypes.has(t))

  return (
    <div className="min-h-screen bg-white pb-12">
      {/* Header */}
      <div className="px-4 pt-8 pb-4">
        <Link to="/" className="text-sm text-gray-500 hover:text-black transition-colors">
          ← Back
        </Link>
        <h1 className="text-2xl font-bold text-black mt-3">Connected sources</h1>
      </div>

      {error && (
        <div className="mx-4 mb-4 p-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm">
          {error}
        </div>
      )}

      {/* Connected source cards */}
      <div className="px-4 space-y-3">
        {activeSources.length === 0 && (
          <p className="text-sm text-gray-400 text-center py-8">No sources connected yet.</p>
        )}
        {activeSources.map((source) => (
          <div
            key={source.id}
            className="flex items-center justify-between p-4 rounded-xl border border-gray-100 bg-white shadow-sm"
          >
            <div className="flex items-center gap-3">
              <span className="text-lg w-6 text-center">{sourceIcon(source.source_type)}</span>
              <div>
                <p className="text-sm font-medium text-black">{source.display_name}</p>
                <div className="flex items-center gap-1.5 mt-0.5">
                  <span
                    className={`inline-block w-2 h-2 rounded-full ${
                      source.is_active ? 'bg-green-500' : 'bg-gray-300'
                    }`}
                  />
                  <span className="text-xs text-gray-500">
                    {source.is_active ? 'Active' : 'Inactive'}
                  </span>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Link
                to="/onboarding"
                className="px-3 py-1.5 rounded-lg border border-gray-200 text-xs font-medium text-gray-600 hover:bg-gray-50 transition-colors"
              >
                Edit
              </Link>
              <button
                type="button"
                disabled={disconnecting === source.id}
                onClick={() => handleDisconnect(source)}
                className="px-3 py-1.5 rounded-lg border border-red-200 text-xs font-medium text-red-600 hover:bg-red-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {disconnecting === source.id ? 'Disconnecting…' : 'Disconnect'}
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Add new source section */}
      {unconnectedTypes.length > 0 && (
        <div className="px-4 mt-8">
          <h2 className="text-sm font-semibold text-gray-600 mb-3 uppercase tracking-wide">
            Add new source
          </h2>
          <div className="space-y-2">
            {unconnectedTypes.map((type) => (
              <Link
                key={type}
                to="/onboarding"
                className="flex items-center gap-3 p-4 rounded-xl border border-dashed border-gray-200 hover:bg-gray-50 transition-colors"
              >
                <span className="text-lg w-6 text-center">{sourceIcon(type)}</span>
                <span className="text-sm font-medium text-black">{sourceDisplayName(type)}</span>
                <span className="ml-auto text-xs text-gray-400">Connect →</span>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
