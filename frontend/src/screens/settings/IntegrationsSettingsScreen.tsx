import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getUserSettings, patchUserSettings } from '../../api/userSettings'
import { listSources, deleteSource } from '../../api/sources'
import type { SourceRead } from '../../api/sources'
import { apiGet } from '../../lib/apiClient'

interface GoogleStatus {
  connected: boolean
  expiry: string | null
}

const MEETING_PLATFORM_LABELS: Record<string, string> = {
  fireflies: 'Fireflies',
  otter: 'Otter.ai',
  readai: 'Read.ai',
  custom: 'Custom webhook',
}

function SourceBadge({ isActive }: { isActive: boolean }) {
  return isActive ? (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-green-50 text-green-700 text-xs font-medium">
      <span className="w-1.5 h-1.5 rounded-full bg-green-500 inline-block" />
      Active
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-gray-100 text-gray-500 text-xs font-medium">
      <span className="w-1.5 h-1.5 rounded-full bg-gray-400 inline-block" />
      Disconnected
    </span>
  )
}

export default function IntegrationsSettingsScreen() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [searchParams] = useSearchParams()
  const [calendarBanner, setCalendarBanner] = useState<'connected' | 'error' | null>(null)
  const [slackBanner, setSlackBanner] = useState<'connected' | 'error' | null>(null)
  const [digestEmail, setDigestEmail] = useState('')
  const [emailEditing, setEmailEditing] = useState(false)
  const [disconnecting, setDisconnecting] = useState<string | null>(null)

  const API_BASE = import.meta.env.VITE_API_URL || ''

  // Read ?calendar= and ?slack= params on mount (OAuth redirect results)
  useEffect(() => {
    const calendarParam = searchParams.get('calendar')
    if (calendarParam === 'connected') {
      setCalendarBanner('connected')
      queryClient.invalidateQueries({ queryKey: ['google-status'] })
    } else if (calendarParam === 'error') {
      setCalendarBanner('error')
    }
    const slackParam = searchParams.get('slack')
    if (slackParam === 'connected') {
      setSlackBanner('connected')
      queryClient.invalidateQueries({ queryKey: ['sources'] })
    } else if (slackParam === 'error') {
      setSlackBanner('error')
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

  const { data: sources } = useQuery({
    queryKey: ['sources'],
    queryFn: listSources,
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

  async function handleDisconnect(source: SourceRead) {
    setDisconnecting(source.id)
    try {
      await deleteSource(source.id)
      queryClient.invalidateQueries({ queryKey: ['sources'] })
    } finally {
      setDisconnecting(null)
    }
  }

  // Group sources by type — only active or explicitly visible
  const slackSources = (sources ?? []).filter((s) => s.source_type === 'slack')
  const emailSources = (sources ?? []).filter((s) => s.source_type === 'email')
  const meetingSources = (sources ?? []).filter((s) => s.source_type === 'meeting')

  const activeSlack = slackSources.find((s) => s.is_active)
  const activeEmail = emailSources.find((s) => s.is_active)

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

      {/* Slack OAuth banner */}
      {slackBanner === 'connected' && (
        <div className="mx-4 mb-4 p-3 rounded-lg bg-green-50 border border-green-200 text-sm text-green-700">
          Slack connected successfully.
        </div>
      )}
      {slackBanner === 'error' && (
        <div className="mx-4 mb-4 p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">
          Failed to connect Slack. Please try again.
        </div>
      )}

      {/* Slack section */}
      <div className="px-4 mb-6">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">Slack</p>
        <div className="rounded-xl border border-gray-100 p-4">
          {slackSources.length === 0 ? (
            <div>
              <p className="text-sm text-gray-600 mb-3">No Slack workspace connected.</p>
              <a
                href={`${API_BASE}/api/v1/integrations/slack/oauth/start`}
                className="inline-block px-4 py-2 rounded-lg bg-black text-white text-sm font-medium hover:bg-gray-900 transition-colors"
              >
                Connect Slack
              </a>
            </div>
          ) : (
            <div className="space-y-3">
              {activeSlack ? (
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <div>
                      <p className="text-sm font-medium text-black">
                        {activeSlack.display_name || activeSlack.provider_account_id || '1 workspace connected'}
                      </p>
                      <p className="text-xs text-gray-400 mt-0.5">
                        Connected {new Date(activeSlack.created_at).toLocaleDateString()}
                      </p>
                    </div>
                    <SourceBadge isActive={true} />
                  </div>
                  <div className="flex items-center gap-3">
                    <button
                      type="button"
                      onClick={() => handleDisconnect(activeSlack)}
                      disabled={disconnecting === activeSlack.id}
                      className="text-xs text-red-500 hover:text-red-700 transition-colors disabled:opacity-50"
                    >
                      {disconnecting === activeSlack.id ? 'Disconnecting…' : 'Disconnect'}
                    </button>
                    <a
                      href={`${API_BASE}/api/v1/integrations/slack/oauth/start`}
                      className="text-xs text-gray-500 hover:text-black transition-colors"
                    >
                      Reconnect
                    </a>
                  </div>
                </div>
              ) : (
                <div className="flex items-center justify-between">
                  <p className="text-sm text-gray-500">Workspace disconnected</p>
                  <a
                    href={`${API_BASE}/api/v1/integrations/slack/oauth/start`}
                    className="text-xs font-medium text-black underline"
                  >
                    Reconnect
                  </a>
                </div>
              )}

              {/* Slack channel invite reminder */}
              <div className="mt-3 p-3 rounded-lg bg-blue-50 border border-blue-100">
                <p className="text-xs font-medium text-black mb-1">Invite bot to channels</p>
                <p className="text-xs text-gray-600">
                  To receive signals from a channel, type this in that channel:
                </p>
                <p className="mt-1 font-mono text-xs text-black">/invite @Rippled</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Email section */}
      <div className="px-4 mb-6">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">Email</p>
        <div className="rounded-xl border border-gray-100 p-4">
          {emailSources.length === 0 ? (
            <div>
              <p className="text-sm text-gray-600 mb-3">No email inbox connected.</p>
              <button
                type="button"
                onClick={() => navigate('/onboarding?step=1')}
                className="text-sm font-medium text-black underline hover:text-gray-700 transition-colors"
              >
                Connect email
              </button>
            </div>
          ) : activeEmail ? (
            <div>
              <div className="flex items-center justify-between mb-2">
                <div>
                  <p className="text-sm font-medium text-black">
                    {activeEmail.display_name || activeEmail.provider_account_id || '1 inbox connected'}
                  </p>
                  <p className="text-xs text-gray-400 mt-0.5">
                    Connected {new Date(activeEmail.created_at).toLocaleDateString()}
                  </p>
                </div>
                <SourceBadge isActive={true} />
              </div>
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => handleDisconnect(activeEmail)}
                  disabled={disconnecting === activeEmail.id}
                  className="text-xs text-red-500 hover:text-red-700 transition-colors disabled:opacity-50"
                >
                  {disconnecting === activeEmail.id ? 'Disconnecting…' : 'Disconnect'}
                </button>
                <button
                  type="button"
                  onClick={() => navigate('/onboarding?step=1')}
                  className="text-xs text-gray-500 hover:text-black transition-colors"
                >
                  Reconnect
                </button>
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-between">
              <p className="text-sm text-gray-500">Inbox disconnected</p>
              <button
                type="button"
                onClick={() => navigate('/onboarding?step=1')}
                className="text-xs font-medium text-black underline"
              >
                Reconnect
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Meetings section */}
      <div className="px-4 mb-6">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">
          Meeting Transcripts
        </p>
        <div className="rounded-xl border border-gray-100 p-4">
          {meetingSources.length === 0 ? (
            <div>
              <p className="text-sm text-gray-600 mb-3">No meeting transcript platform connected.</p>
              <button
                type="button"
                onClick={() => navigate('/onboarding?step=3')}
                className="text-sm font-medium text-black underline hover:text-gray-700 transition-colors"
              >
                Connect meetings
              </button>
            </div>
          ) : (
            <div className="space-y-4">
              {meetingSources.map((source) => {
                const platform = source.metadata_?.platform as string | undefined
                const platformLabel = platform ? (MEETING_PLATFORM_LABELS[platform] ?? platform) : source.display_name
                const webhookUrl = source.metadata_?.webhook_url as string | undefined

                return (
                  <div key={source.id} className="pb-4 border-b border-gray-100 last:border-0 last:pb-0">
                    <div className="flex items-center justify-between mb-2">
                      <div>
                        <p className="text-sm font-medium text-black">
                          {platformLabel || 'Meeting platform'}
                        </p>
                        <p className="text-xs text-gray-400 mt-0.5">
                          Connected {new Date(source.created_at).toLocaleDateString()}
                        </p>
                      </div>
                      <SourceBadge isActive={source.is_active} />
                    </div>
                    {source.is_active && webhookUrl && (
                      <div className="mb-2 p-2 rounded bg-gray-50 border border-gray-100">
                        <p className="text-xs text-gray-500 mb-0.5">Webhook URL</p>
                        <p className="text-xs font-mono text-black break-all">{webhookUrl}</p>
                      </div>
                    )}
                    {source.is_active && (
                      <button
                        type="button"
                        onClick={() => handleDisconnect(source)}
                        disabled={disconnecting === source.id}
                        className="text-xs text-red-500 hover:text-red-700 transition-colors disabled:opacity-50"
                      >
                        {disconnecting === source.id ? 'Disconnecting…' : 'Disconnect'}
                      </button>
                    )}
                  </div>
                )
              })}
              <button
                type="button"
                onClick={() => navigate('/onboarding?step=3')}
                className="text-sm font-medium text-black underline hover:text-gray-700 transition-colors"
              >
                Connect another platform
              </button>
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
