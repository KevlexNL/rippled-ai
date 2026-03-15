import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getUserSettings, patchUserSettings } from '../../api/userSettings'
import { apiGet } from '../../lib/apiClient'

interface GoogleStatus {
  connected: boolean
  expiry: string | null
}

export default function IntegrationsSettingsScreen() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [searchParams] = useSearchParams()
  const [calendarBanner, setCalendarBanner] = useState<'connected' | 'error' | null>(null)
  const [digestEmail, setDigestEmail] = useState('')
  const [emailEditing, setEmailEditing] = useState(false)

  // Read ?calendar= param on mount (OAuth redirect result)
  useEffect(() => {
    const calendarParam = searchParams.get('calendar')
    if (calendarParam === 'connected') {
      setCalendarBanner('connected')
      queryClient.invalidateQueries({ queryKey: ['google-status'] })
    } else if (calendarParam === 'error') {
      setCalendarBanner('error')
    }
  }, [searchParams, queryClient])

  const { data: googleStatus } = useQuery<GoogleStatus>({
    queryKey: ['google-status'],
    queryFn: () => apiGet<GoogleStatus>('/api/v1/integrations/google/status'),
  })

  const { data: userSettings } = useQuery({
    queryKey: ['user-settings'],
    queryFn: getUserSettings,
  })

  const mutation = useMutation({
    mutationFn: patchUserSettings,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['user-settings'] })
    },
  })

  // Sync digestEmail from loaded settings
  useEffect(() => {
    if (userSettings?.digest_to_email && !emailEditing) {
      setDigestEmail(userSettings.digest_to_email)
    }
  }, [userSettings, emailEditing])

  const API_BASE = import.meta.env.VITE_API_URL || ''

  return (
    <div className="min-h-screen bg-white pb-24">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 pt-8 pb-4">
        <button
          type="button"
          onClick={() => navigate(-1)}
          className="text-sm text-gray-500 hover:text-black transition-colors"
        >
          ‹ Back
        </button>
        <h1 className="text-base font-semibold text-black">Integrations</h1>
      </div>

      {/* Calendar connect banner */}
      {calendarBanner === 'connected' && (
        <div className="mx-4 mb-4 p-3 rounded-lg bg-green-50 border border-green-200 text-sm text-green-700">
          Google Calendar connected successfully.
        </div>
      )}
      {calendarBanner === 'error' && (
        <div className="mx-4 mb-4 p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">
          Failed to connect Google Calendar. Please try again.
        </div>
      )}

      {/* Google Calendar section */}
      <div className="px-4 mb-6">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">
          Google Calendar
        </p>
        <div className="rounded-xl border border-gray-100 p-4">
          {googleStatus?.connected ? (
            <div>
              <div className="flex items-center gap-2 mb-2">
                <span className="w-2 h-2 rounded-full bg-green-500 inline-block" />
                <span className="text-sm font-medium text-black">Connected</span>
              </div>
              {googleStatus.expiry && (
                <p className="text-xs text-gray-400 mb-3">
                  Token expires: {new Date(googleStatus.expiry).toLocaleDateString()}
                </p>
              )}
              <a
                href={`${API_BASE}/api/v1/integrations/google/disconnect`}
                className="text-xs text-red-500 hover:text-red-700 transition-colors"
                onClick={(e) => {
                  e.preventDefault()
                  // Call disconnect via fetch then invalidate
                  fetch(`${API_BASE}/api/v1/integrations/google/disconnect`, { method: 'DELETE' })
                    .then(() => queryClient.invalidateQueries({ queryKey: ['google-status'] }))
                }}
              >
                Disconnect
              </a>
            </div>
          ) : (
            <div>
              <p className="text-sm text-gray-600 mb-3">
                Connect Google Calendar so Rippled can surface commitments around your events.
              </p>
              <a
                href={`${API_BASE}/api/v1/integrations/google/auth`}
                className="inline-block px-4 py-2 rounded-lg bg-black text-white text-sm font-medium hover:bg-gray-900 transition-colors"
              >
                Connect Google Calendar
              </a>
            </div>
          )}
        </div>
      </div>

      {/* Daily Digest section */}
      <div className="px-4">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">
          Daily Digest
        </p>
        <div className="rounded-xl border border-gray-100 p-4 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-black">Daily digest email</span>
            <button
              type="button"
              onClick={() =>
                mutation.mutate({ digest_enabled: !userSettings?.digest_enabled })
              }
              className={`relative inline-flex h-5 w-9 rounded-full transition-colors ${
                userSettings?.digest_enabled ? 'bg-black' : 'bg-gray-200'
              }`}
            >
              <span
                className={`inline-block w-4 h-4 bg-white rounded-full shadow transform transition-transform mt-0.5 ${
                  userSettings?.digest_enabled ? 'translate-x-4' : 'translate-x-0.5'
                }`}
              />
            </button>
          </div>
          {userSettings?.digest_enabled && (
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Digest email</label>
              {emailEditing ? (
                <div className="flex gap-2">
                  <input
                    type="email"
                    value={digestEmail}
                    onChange={(e) => setDigestEmail(e.target.value)}
                    className="flex-1 px-3 py-1.5 rounded-lg border border-gray-200 text-sm text-black focus:outline-none focus:ring-2 focus:ring-black"
                    placeholder="you@example.com"
                  />
                  <button
                    type="button"
                    onClick={() => {
                      mutation.mutate({ digest_to_email: digestEmail })
                      setEmailEditing(false)
                    }}
                    className="px-3 py-1.5 rounded-lg bg-black text-white text-xs font-medium"
                  >
                    Save
                  </button>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => setEmailEditing(true)}
                  className="text-sm text-gray-600 hover:text-black transition-colors"
                >
                  {userSettings?.digest_to_email || 'Set email address →'}
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
