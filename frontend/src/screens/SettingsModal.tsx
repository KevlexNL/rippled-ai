import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { getUserSettings, patchUserSettings } from '../api/userSettings'
import type { UserSettingsRead } from '../api/userSettings'
import { listSources } from '../api/sources'
import type { SourceRead } from '../api/sources'

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
    <div className="max-w-[680px] mx-auto py-8 px-8">
      {/* LLM API Token */}
      <div className="mb-10">
        <div className="font-semibold text-[17px] text-[#191919]">LLM API Token</div>
        <div className="text-[13px] text-[#6b7280] mt-1 mb-5">Connect an LLM provider to power Rippled's commitment detection.</div>
        <div className="grid grid-cols-2 gap-4">
          {/* Claude card */}
          <div className="bg-white border border-[#e8e8e6] rounded-lg p-4 flex flex-col gap-3">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-md bg-[#f0f0ef] flex items-center justify-center text-[#191919] text-[12px] font-bold">A</div>
              <div className="flex-1">
                <div className="font-semibold text-[15px] text-[#191919]">Claude</div>
                <div className="text-[12px] text-[#6b7280]">claude-haiku-4-5 · Recommended</div>
              </div>
              <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ${claudeConnected ? 'bg-[#f0fdf4] text-[#15803d]' : 'bg-[#f9fafb] text-[#6b7280] border border-[#e8e8e6]'}`}>
                {claudeConnected ? 'Connected' : 'Not connected'}
              </span>
            </div>
            <div>
              <label className="block text-[12px] text-[#6b7280] mb-1">API Key</label>
              <input
                type="password"
                className="w-full border border-[#e8e8e6] rounded-md px-3 py-1.5 text-[13px] text-[#191919] placeholder:text-[#9ca3af] focus:outline-none focus:border-[#d1d1cf]"
                placeholder={claudeConnected ? 'sk-ant-•••••••' : 'sk-ant-...'}
                value={claudeKey}
                onChange={(e) => setClaudeKey(e.target.value)}
              />
            </div>
            {claudeError && <div className="text-[12px] text-[#991b1b]">{claudeError}</div>}
            <button
              onClick={handleSaveClaude}
              disabled={claudeSaving || !claudeKey}
              className="bg-[#191919] text-white text-[12px] px-3 py-1.5 rounded-md font-medium hover:bg-[#333] transition-colors self-start disabled:opacity-50"
            >
              {claudeSaving ? 'Saving...' : claudeConnected ? 'Update key' : 'Save key'}
            </button>
          </div>

          {/* OpenAI card */}
          <div className="bg-white border border-[#e8e8e6] rounded-lg p-4 flex flex-col gap-3">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-md bg-[#f0f0ef] flex items-center justify-center text-[#191919] text-[12px] font-bold">G</div>
              <div className="flex-1">
                <div className="font-semibold text-[15px] text-[#191919]">ChatGPT</div>
                <div className="text-[12px] text-[#6b7280]">gpt-4o-mini · Alternative</div>
              </div>
              <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ${openaiConnected ? 'bg-[#f0fdf4] text-[#15803d]' : 'bg-[#f9fafb] text-[#6b7280] border border-[#e8e8e6]'}`}>
                {openaiConnected ? 'Connected' : 'Not connected'}
              </span>
            </div>
            <div>
              <label className="block text-[12px] text-[#6b7280] mb-1">API Key</label>
              <input
                type="password"
                className="w-full border border-[#e8e8e6] rounded-md px-3 py-1.5 text-[13px] text-[#191919] placeholder:text-[#9ca3af] focus:outline-none focus:border-[#d1d1cf]"
                placeholder={openaiConnected ? 'sk-•••••••' : 'sk-...'}
                value={openaiKey}
                onChange={(e) => setOpenaiKey(e.target.value)}
              />
            </div>
            {openaiError && <div className="text-[12px] text-[#991b1b]">{openaiError}</div>}
            <button
              onClick={handleSaveOpenai}
              disabled={openaiSaving || !openaiKey}
              className="bg-[#191919] text-white text-[12px] px-3 py-1.5 rounded-md font-medium hover:bg-[#333] transition-colors self-start disabled:opacity-50"
            >
              {openaiSaving ? 'Saving...' : openaiConnected ? 'Update key' : 'Save key'}
            </button>
          </div>
        </div>
        <div className="text-[12px] text-[#9ca3af] italic mt-3">Your API key is encrypted and never exposed in responses.</div>
      </div>

      {/* Divider */}
      <div className="border-t border-[#e8e8e6] mb-10" />

      {/* Integrations */}
      <div>
        <div className="font-semibold text-[17px] text-[#191919]">Integrations</div>
        <div className="text-[13px] text-[#6b7280] mt-1 mb-5">Manage your connected data sources.</div>
        <div className="grid grid-cols-2 gap-4">
          {activeSources.length > 0 ? (
            activeSources.map((src) => (
              <div key={src.id} className="bg-white border border-[#e8e8e6] rounded-lg p-4 flex flex-col gap-2">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-md bg-[#f0f0ef] flex items-center justify-center text-[#6b7280]">
                    {sourceIcon(src.source_type)}
                  </div>
                  <span className="font-semibold text-[15px] text-[#191919]">{sourceDisplayName(src.source_type)}</span>
                  <span className="inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium bg-[#f0fdf4] text-[#15803d] ml-auto">Connected</span>
                </div>
                {src.display_name && (
                  <div className="text-[12px] text-[#6b7280]">{src.display_name}</div>
                )}
                <a
                  href={`/settings/sources`}
                  className="border border-[#e8e8e6] text-[#6b7280] hover:text-[#191919] text-[12px] px-3 py-1.5 rounded-md font-medium transition-colors self-start mt-1 inline-block text-center"
                >
                  Edit
                </a>
              </div>
            ))
          ) : (
            <div className="col-span-2 text-center py-6">
              <div className="text-[13px] text-[#6b7280]">No sources connected yet.</div>
              <a href="/settings/sources" className="text-[13px] text-[#191919] hover:underline font-medium mt-1 inline-block">Connect a source</a>
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
      fetch('/api/v1/integrations/google/status', {
        headers: { 'Content-Type': 'application/json' },
      }).then(r => r.ok ? r.json() : { connected: false, expiry: null }),
  })

  const connected = googleStatus?.connected ?? false

  return (
    <div className="bg-white border border-[#e8e8e6] rounded-lg p-4 flex flex-col gap-2">
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-md bg-[#f0f0ef] flex items-center justify-center text-[#6b7280]">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="4" width="18" height="18" rx="2" />
            <line x1="16" x2="16" y1="2" y2="6" /><line x1="8" x2="8" y1="2" y2="6" />
            <line x1="3" x2="21" y1="10" y2="10" />
          </svg>
        </div>
        <span className="font-semibold text-[15px] text-[#191919]">Calendar</span>
        <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ml-auto ${
          connected ? 'bg-[#f0fdf4] text-[#15803d]' : 'bg-[#fef3c7] text-[#92400e]'
        }`}>
          {connected ? 'Connected' : 'Not connected'}
        </span>
      </div>
      <div className="text-[12px] text-[#6b7280]">Google Calendar</div>
      {!connected ? (
        <a
          href="/api/v1/integrations/google/auth"
          className="border border-[#d97706] text-[#92400e] text-[12px] px-3 py-1.5 rounded-md font-medium transition-colors self-start mt-1 hover:bg-[#fef3c7] inline-block text-center"
        >
          Connect
        </a>
      ) : (
        <a
          href="/settings/integrations"
          className="border border-[#e8e8e6] text-[#6b7280] hover:text-[#191919] text-[12px] px-3 py-1.5 rounded-md font-medium transition-colors self-start mt-1 inline-block text-center"
        >
          Edit
        </a>
      )}
    </div>
  )
}
