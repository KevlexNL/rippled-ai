import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { getUserSettings, patchUserSettings } from '../api/userSettings'
import type { UserSettingsRead } from '../api/userSettings'
import { listSources } from '../api/sources'
import type { SourceRead } from '../api/sources'
import { apiGet } from '../lib/apiClient'

// ─── Icons ────────────────────────────────────────────────────────────────

function IconMail() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="4" width="20" height="16" rx="2" />
      <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7" />
    </svg>
  )
}

function IconHash() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="4" x2="20" y1="9" y2="9" /><line x1="4" x2="20" y1="15" y2="15" />
      <line x1="10" x2="8" y1="3" y2="21" /><line x1="16" x2="14" y1="3" y2="21" />
    </svg>
  )
}

function IconVideo() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="m22 8-6 4 6 4V8z" /><rect x="2" y="6" width="14" height="12" rx="2" />
    </svg>
  )
}

function IconCalendar() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="4" width="18" height="18" rx="2" />
      <line x1="16" x2="16" y1="2" y2="6" /><line x1="8" x2="8" y1="2" y2="6" />
      <line x1="3" x2="21" y1="10" y2="10" />
    </svg>
  )
}

function sourceIcon(type: string) {
  switch (type) {
    case 'email': return <IconMail />
    case 'slack': return <IconHash />
    case 'meeting': return <IconVideo />
    default: return <IconMail />
  }
}

function sourceDisplayName(type: string): string {
  switch (type) {
    case 'email': return 'Email'
    case 'slack': return 'Slack'
    case 'meeting': return 'Meetings'
    default: return type
  }
}

function StatusBadge({ connected }: { connected: boolean }) {
  return connected ? (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-green-50 text-green-700 text-xs font-medium">
      <span className="w-1.5 h-1.5 rounded-full bg-green-500 inline-block" />
      Connected
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-gray-100 text-gray-500 text-xs font-medium">
      <span className="w-1.5 h-1.5 rounded-full bg-gray-400 inline-block" />
      Not connected
    </span>
  )
}

// ─── SettingsModal ────────────────────────────────────────────────────────

export default function SettingsModal() {
  const queryClient = useQueryClient()
  const [claudeKey, setClaudeKey] = useState('')
  const [openaiKey, setOpenaiKey] = useState('')
  const [claudeSaving, setClaudeSaving] = useState(false)
  const [openaiSaving, setOpenaiSaving] = useState(false)
  const [claudeError, setClaudeError] = useState<string | null>(null)
  const [openaiError, setOpenaiError] = useState<string | null>(null)

  const { data: settings } = useQuery<UserSettingsRead>({
    queryKey: ['user-settings'],
    queryFn: getUserSettings,
    staleTime: 0,
  })

  const { data: sources } = useQuery<SourceRead[]>({
    queryKey: ['sources'],
    queryFn: listSources,
  })

  async function handleSaveClaude() {
    setClaudeError(null)
    setClaudeSaving(true)
    try {
      await patchUserSettings({ anthropic_api_key: claudeKey })
      setClaudeKey('')
      queryClient.invalidateQueries({ queryKey: ['user-settings'] })
    } catch (err) {
      setClaudeError(err instanceof Error ? err.message : 'Failed to save key')
    } finally {
      setClaudeSaving(false)
    }
  }

  async function handleSaveOpenai() {
    setOpenaiError(null)
    setOpenaiSaving(true)
    try {
      await patchUserSettings({ openai_api_key: openaiKey })
      setOpenaiKey('')
      queryClient.invalidateQueries({ queryKey: ['user-settings'] })
    } catch (err) {
      setOpenaiError(err instanceof Error ? err.message : 'Failed to save key')
    } finally {
      setOpenaiSaving(false)
    }
  }

  const claudeConnected = settings?.anthropic_key_connected ?? false
  const openaiConnected = settings?.openai_key_connected ?? false
  const activeSources = (sources ?? []).filter(s => s.is_active)

  return (
    <div className="max-w-[680px] mx-auto py-8 px-4 md:px-8 pb-12">
      {/* LLM API Token */}
      <div className="mb-10">
        <h2 className="text-base font-semibold text-black">LLM API Token</h2>
        <p className="text-xs text-gray-500 mt-1 mb-5">Connect an LLM provider to power Rippled's commitment detection.</p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Claude card */}
          <div className="rounded-xl border border-gray-100 p-4 flex flex-col gap-3">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-md bg-gray-50 flex items-center justify-center text-black text-xs font-bold">A</div>
              <div className="flex-1">
                <p className="font-semibold text-sm text-black">Claude</p>
                <p className="text-xs text-gray-500">claude-haiku-4-5 · Recommended</p>
              </div>
              <StatusBadge connected={claudeConnected} />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">API Key</label>
              <input
                type="password"
                className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm text-black placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-black focus:border-transparent"
                placeholder={claudeConnected ? 'sk-ant-•••••••' : 'sk-ant-...'}
                value={claudeKey}
                onChange={(e) => setClaudeKey(e.target.value)}
              />
            </div>
            {claudeError && <p className="text-xs text-red-700">{claudeError}</p>}
            <button
              onClick={handleSaveClaude}
              disabled={claudeSaving || !claudeKey}
              className="px-3 py-1.5 rounded-lg bg-black text-white text-xs font-medium hover:bg-gray-900 transition-colors self-start disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {claudeSaving ? 'Saving…' : claudeConnected ? 'Update key' : 'Save key'}
            </button>
          </div>

          {/* OpenAI card */}
          <div className="rounded-xl border border-gray-100 p-4 flex flex-col gap-3">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-md bg-gray-50 flex items-center justify-center text-black text-xs font-bold">G</div>
              <div className="flex-1">
                <p className="font-semibold text-sm text-black">ChatGPT</p>
                <p className="text-xs text-gray-500">gpt-4o-mini · Alternative</p>
              </div>
              <StatusBadge connected={openaiConnected} />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">API Key</label>
              <input
                type="password"
                className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm text-black placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-black focus:border-transparent"
                placeholder={openaiConnected ? 'sk-•••••••' : 'sk-...'}
                value={openaiKey}
                onChange={(e) => setOpenaiKey(e.target.value)}
              />
            </div>
            {openaiError && <p className="text-xs text-red-700">{openaiError}</p>}
            <button
              onClick={handleSaveOpenai}
              disabled={openaiSaving || !openaiKey}
              className="px-3 py-1.5 rounded-lg bg-black text-white text-xs font-medium hover:bg-gray-900 transition-colors self-start disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {openaiSaving ? 'Saving…' : openaiConnected ? 'Update key' : 'Save key'}
            </button>
          </div>
        </div>
        <p className="text-xs text-gray-400 italic mt-3">Your API key is encrypted and never exposed in responses.</p>
      </div>

      {/* Divider */}
      <div className="border-t border-gray-100 mb-10" />

      {/* Integrations */}
      <div>
        <h2 className="text-base font-semibold text-black">Integrations</h2>
        <p className="text-xs text-gray-500 mt-1 mb-5">Manage your connected data sources.</p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {activeSources.length > 0 ? (
            activeSources.map((src) => (
              <div key={src.id} className="rounded-xl border border-gray-100 p-4 flex flex-col gap-2">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-md bg-gray-50 flex items-center justify-center text-gray-500">
                    {sourceIcon(src.source_type)}
                  </div>
                  <span className="font-semibold text-sm text-black">{sourceDisplayName(src.source_type)}</span>
                  <StatusBadge connected={true} />
                </div>
                {src.display_name && (
                  <p className="text-xs text-gray-500">{src.display_name}</p>
                )}
                <a
                  href="/settings/integrations"
                  className="px-3 py-1.5 rounded-lg border border-gray-200 text-gray-500 hover:text-black text-xs font-medium transition-colors self-start mt-1 inline-block text-center"
                >
                  Edit
                </a>
              </div>
            ))
          ) : (
            <div className="col-span-1 md:col-span-2 text-center py-6">
              <p className="text-sm text-gray-500">No sources connected yet.</p>
              <a href="/settings/integrations" className="text-sm text-black hover:underline font-medium mt-1 inline-block">Connect a source</a>
            </div>
          )}

          {/* Google Calendar status */}
          <GoogleCalendarCard />
        </div>
      </div>
    </div>
  )
}

function GoogleCalendarCard() {
  const { data: googleStatus } = useQuery<{ connected: boolean; expiry: string | null }>({
    queryKey: ['google-status'],
    queryFn: () =>
      apiGet<{ connected: boolean; expiry: string | null }>('/api/v1/integrations/google/status')
        .catch(() => ({ connected: false, expiry: null })),
  })

  const connected = googleStatus?.connected ?? false

  return (
    <div className="rounded-xl border border-gray-100 p-4 flex flex-col gap-2">
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-md bg-gray-50 flex items-center justify-center text-gray-500">
          <IconCalendar />
        </div>
        <span className="font-semibold text-sm text-black">Calendar</span>
        <StatusBadge connected={connected} />
      </div>
      <p className="text-xs text-gray-500">Google Calendar</p>
      {!connected ? (
        <a
          href="/api/v1/integrations/google/auth"
          className="px-3 py-1.5 rounded-lg bg-black text-white text-xs font-medium hover:bg-gray-900 transition-colors self-start mt-1 inline-block text-center"
        >
          Connect
        </a>
      ) : (
        <a
          href="/settings/integrations"
          className="px-3 py-1.5 rounded-lg border border-gray-200 text-gray-500 hover:text-black text-xs font-medium transition-colors self-start mt-1 inline-block text-center"
        >
          Edit
        </a>
      )}
    </div>
  )
}
