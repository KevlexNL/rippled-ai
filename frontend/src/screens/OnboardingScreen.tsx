import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { supabase } from '../lib/supabase'
import { apiPost } from '../lib/apiClient'

// IMAP auto-detection
function detectImapHost(email: string): string {
  const domain = email.split('@')[1] || ''
  if (domain === 'gmail.com') return 'imap.gmail.com'
  if (['outlook.com', 'hotmail.com', 'live.com'].includes(domain)) return 'outlook.office365.com'
  if (domain === 'yahoo.com') return 'imap.mail.yahoo.com'
  return domain ? `imap.${domain}` : ''
}

// Shared UI components
function Banner({ success, message }: { success: boolean; message: string }) {
  return (
    <div
      className={`p-3 rounded-lg border text-sm ${
        success
          ? 'bg-green-50 border-green-200 text-green-700'
          : 'bg-red-50 border-red-200 text-red-700'
      }`}
    >
      {message}
    </div>
  )
}

function FormField({
  label,
  id,
  type = 'text',
  value,
  onChange,
  placeholder,
}: {
  label: string
  id: string
  type?: string
  value: string
  onChange: (v: string) => void
  placeholder?: string
}) {
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-black mb-1">
        {label}
      </label>
      <input
        id={id}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full px-3 py-2.5 rounded-lg border border-gray-200 text-sm text-black placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-black focus:border-transparent"
      />
    </div>
  )
}

// Types
interface TestResult {
  success: boolean
  message?: string
  error?: string
  workspace?: string
  bot_user?: string
}

interface MeetingSetupResult {
  webhook_url: string
  webhook_secret: string
}

const MEETING_PLATFORMS = ['fireflies', 'otter', 'readai', 'custom'] as const
type MeetingPlatform = (typeof MEETING_PLATFORMS)[number]

const PLATFORM_LABELS: Record<MeetingPlatform, string> = {
  fireflies: 'Fireflies',
  otter: 'Otter.ai',
  readai: 'Read.ai',
  custom: 'Custom webhook',
}

const PLATFORM_INSTRUCTIONS: Record<MeetingPlatform, string> = {
  fireflies:
    'In Fireflies, go to Integrations → Webhooks and add your Rippled webhook URL.',
  otter: 'In Otter.ai, go to Settings → Integrations → Webhooks and add your Rippled webhook URL.',
  readai: 'In Read.ai, go to Settings → Integrations and add your Rippled webhook URL.',
  custom: 'Configure your transcript tool to POST to this webhook URL.',
}


function StepLayout({
  children,
  maxWidth = 'max-w-lg',
}: {
  children: React.ReactNode
  maxWidth?: string
}) {
  return (
    <div className="min-h-screen bg-white flex items-start justify-center px-4 pt-16 pb-16">
      <div className={`w-full ${maxWidth}`}>{children}</div>
    </div>
  )
}

export default function OnboardingScreen() {
  const navigate = useNavigate()
  const API_BASE = import.meta.env.VITE_API_URL || ''

  const [step, setStep] = useState(0)
  const [connectedSources, setConnectedSources] = useState<string[]>([])

  // Step 1 — Email
  const [emailForm, setEmailForm] = useState({
    email: '',
    appPassword: '',
    imapHost: '',
    internalDomains: '',
  })
  const [emailTestResult, setEmailTestResult] = useState<TestResult | null>(null)
  const [emailTestLoading, setEmailTestLoading] = useState(false)
  const [emailConnectLoading, setEmailConnectLoading] = useState(false)
  const [emailAccessExpanded, setEmailAccessExpanded] = useState(false)

  // Step 2 — Slack
  const [slackForm, setSlackForm] = useState({
    botToken: '',
    signingSecret: '',
    slackUserId: '',
  })
  const [slackTestResult, setSlackTestResult] = useState<TestResult | null>(null)
  const [slackTestLoading, setSlackTestLoading] = useState(false)
  const [slackConnectLoading, setSlackConnectLoading] = useState(false)

  // Step 3 — Meetings
  const [meetingPlatform, setMeetingPlatform] = useState<MeetingPlatform>('fireflies')
  const [meetingResult, setMeetingResult] = useState<MeetingSetupResult | null>(null)
  const [meetingConnectLoading, setMeetingConnectLoading] = useState(false)
  const [meetingConnectError, setMeetingConnectError] = useState<string | null>(null)
  const [copiedSecret, setCopiedSecret] = useState(false)

  // Step 4 — Done
  const [doneLoading, setDoneLoading] = useState(false)

  // Helpers
  function handleEmailChange(v: string) {
    setEmailForm((prev) => ({
      ...prev,
      email: v,
      imapHost: detectImapHost(v),
    }))
    setEmailTestResult(null)
  }

  async function testEmail() {
    setEmailTestLoading(true)
    setEmailTestResult(null)
    try {
      const result = await apiPost<TestResult>('/api/v1/sources/test/email', {
        email: emailForm.email,
        app_password: emailForm.appPassword,
        imap_host: emailForm.imapHost,
        internal_domains: emailForm.internalDomains
          .split(',')
          .map((d) => d.trim())
          .filter(Boolean),
      })
      setEmailTestResult({ success: true, message: result.message })
    } catch (err) {
      setEmailTestResult({
        success: false,
        error: err instanceof Error ? err.message : 'Connection test failed',
      })
    } finally {
      setEmailTestLoading(false)
    }
  }

  async function connectEmail() {
    setEmailConnectLoading(true)
    try {
      await apiPost('/api/v1/sources/setup/email', {
        email: emailForm.email,
        app_password: emailForm.appPassword,
        imap_host: emailForm.imapHost,
        internal_domains: emailForm.internalDomains
          .split(',')
          .map((d) => d.trim())
          .filter(Boolean),
      })
      setConnectedSources((prev) => [...prev, 'email'])
      setStep(2)
    } catch (err) {
      setEmailTestResult({
        success: false,
        error: err instanceof Error ? err.message : 'Failed to connect email',
      })
    } finally {
      setEmailConnectLoading(false)
    }
  }

  async function testSlack() {
    setSlackTestLoading(true)
    setSlackTestResult(null)
    try {
      const result = await apiPost<TestResult>('/api/v1/sources/test/slack', {
        bot_token: slackForm.botToken,
        signing_secret: slackForm.signingSecret,
        slack_user_id: slackForm.slackUserId,
      })
      setSlackTestResult({ success: true, message: result.message, workspace: result.workspace, bot_user: result.bot_user })
    } catch (err) {
      setSlackTestResult({
        success: false,
        error: err instanceof Error ? err.message : 'Connection test failed',
      })
    } finally {
      setSlackTestLoading(false)
    }
  }

  async function connectSlack() {
    setSlackConnectLoading(true)
    try {
      await apiPost('/api/v1/sources/setup/slack', {
        bot_token: slackForm.botToken,
        signing_secret: slackForm.signingSecret,
        slack_user_id: slackForm.slackUserId,
      })
      setConnectedSources((prev) => [...prev, 'slack'])
      setStep(3)
    } catch (err) {
      setSlackTestResult({
        success: false,
        error: err instanceof Error ? err.message : 'Failed to connect Slack',
      })
    } finally {
      setSlackConnectLoading(false)
    }
  }

  async function connectMeeting() {
    setMeetingConnectLoading(true)
    setMeetingConnectError(null)
    try {
      const result = await apiPost<MeetingSetupResult>('/api/v1/sources/setup/meeting', {
        platform: meetingPlatform,
      })
      setMeetingResult(result)
      setConnectedSources((prev) => [...prev, 'meetings'])
    } catch (err) {
      setMeetingConnectError(
        err instanceof Error ? err.message : 'Failed to connect meeting transcripts',
      )
    } finally {
      setMeetingConnectLoading(false)
    }
  }

  async function copyToClipboard(text: string) {
    await navigator.clipboard.writeText(text)
    setCopiedSecret(true)
    setTimeout(() => setCopiedSecret(false), 2000)
  }

  async function finishOnboarding() {
    setDoneLoading(true)
    try {
      await supabase.auth.updateUser({ data: { onboarding_complete: true } })
    } finally {
      setDoneLoading(false)
      navigate('/')
    }
  }

  // Step 0 — Welcome
  if (step === 0) {
    return (
      <StepLayout maxWidth="max-w-sm">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-black">Welcome to Rippled</h1>
          <p className="mt-3 text-sm text-gray-600 leading-relaxed">
            Rippled quietly watches your meetings, messages and email to help you forget fewer
            commitments. Let&apos;s connect your signal inputs.
          </p>
        </div>
        <button
          onClick={() => setStep(1)}
          className="w-full py-2.5 rounded-lg bg-black text-white text-sm font-medium hover:bg-gray-900 active:bg-gray-800 transition-colors"
        >
          Get started
        </button>
      </StepLayout>
    )
  }

  // Step 1 — Email
  if (step === 1) {
    const canConnect = emailTestResult?.success || (emailForm.email.length > 0 && emailForm.appPassword.length > 0)
    const isGmail = emailForm.email.toLowerCase().endsWith('@gmail.com')
    return (
      <StepLayout>
        <div className="mb-6">
          <p className="text-xs text-gray-400 uppercase tracking-wider mb-2">Step 1 of 4</p>
          <h1 className="text-2xl font-bold text-black">Connect your email</h1>
          <p className="mt-3 text-sm text-gray-600 leading-relaxed">
            Email is where the most consequential commitments live — proposals sent, deadlines
            agreed, deliverables promised. Rippled reads your inbox and sent mail to catch what you
            said you&apos;d do and what others said they&apos;d do for you.
          </p>
          <p className="mt-3 text-xs text-gray-400 leading-relaxed">
            Rippled reads your inbox and sent mail to detect commitments. It only reads — never
            sends or modifies.
          </p>
          <button
            type="button"
            onClick={() => setEmailAccessExpanded((v) => !v)}
            className="mt-2 text-xs text-gray-400 hover:text-black transition-colors underline"
          >
            {emailAccessExpanded ? 'Hide access details ↑' : 'What access do we need? ↓'}
          </button>
          {emailAccessExpanded && (
            <div className="mt-2 p-3 rounded-lg bg-gray-50 border border-gray-100 space-y-1">
              <p className="text-xs text-gray-600">• IMAP read access to INBOX and Sent folder</p>
              <p className="text-xs text-gray-600">
                • We do not store full email bodies — only commitment signals extracted from content
              </p>
            </div>
          )}
        </div>

        <div className="space-y-4">
          <FormField
            label="Email address"
            id="email-address"
            type="email"
            value={emailForm.email}
            onChange={handleEmailChange}
            placeholder="you@example.com"
          />
          <FormField
            label="App password"
            id="app-password"
            type="password"
            value={emailForm.appPassword}
            onChange={(v) => setEmailForm((prev) => ({ ...prev, appPassword: v }))}
            placeholder="••••••••••••"
          />
          {isGmail && (
            <p className="text-xs text-gray-500 leading-relaxed -mt-2">
              For Gmail: create an{' '}
              <a
                href="https://myaccount.google.com/apppasswords"
                target="_blank"
                rel="noopener noreferrer"
                className="underline hover:text-black"
              >
                App Password
              </a>{' '}
              in your Google account security settings and use it here instead of your regular
              password.
            </p>
          )}
          <FormField
            label="IMAP host"
            id="imap-host"
            value={emailForm.imapHost}
            onChange={(v) => setEmailForm((prev) => ({ ...prev, imapHost: v }))}
            placeholder="imap.gmail.com"
          />
          <FormField
            label="Internal domains (comma-separated)"
            id="internal-domains"
            value={emailForm.internalDomains}
            onChange={(v) => setEmailForm((prev) => ({ ...prev, internalDomains: v }))}
            placeholder="acme.com, example.com"
          />

          {emailTestResult && (
            <Banner
              success={emailTestResult.success}
              message={
                emailTestResult.success
                  ? `Connected to ${emailForm.email}${emailTestResult.message ? ` — ${emailTestResult.message}` : ''}`
                  : (emailTestResult.error ?? 'Connection test failed')
              }
            />
          )}

          <button
            onClick={testEmail}
            disabled={emailTestLoading || !emailForm.email || !emailForm.appPassword}
            className="w-full py-2.5 rounded-lg border border-gray-200 text-black text-sm font-medium hover:bg-gray-50 active:bg-gray-100 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {emailTestLoading ? 'Testing…' : 'Test connection'}
          </button>

          <button
            onClick={connectEmail}
            disabled={emailConnectLoading || !canConnect}
            className="w-full py-2.5 rounded-lg bg-black text-white text-sm font-medium hover:bg-gray-900 active:bg-gray-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {emailConnectLoading ? 'Connecting…' : 'Connect email'}
          </button>
        </div>

        <div className="mt-6 text-center">
          <button
            onClick={() => setStep(2)}
            className="text-sm text-gray-400 hover:text-black transition-colors"
          >
            I&apos;ll set this up later
          </button>
        </div>
      </StepLayout>
    )
  }

  // Step 2 — Slack
  if (step === 2) {
    const canConnectSlack = slackTestResult?.success || (slackForm.botToken.length > 0 && slackForm.signingSecret.length > 0)
    return (
      <StepLayout>
        <div className="mb-6">
          <p className="text-xs text-gray-400 uppercase tracking-wider mb-2">Step 2 of 4</p>
          <h1 className="text-2xl font-bold text-black">Connect Slack</h1>
          <p className="mt-3 text-sm text-gray-600 leading-relaxed">
            Slack is where small commitments disappear. &quot;I&apos;ll look into it.&quot; &quot;Let me check.&quot; &quot;Send
            me that.&quot; Rippled monitors your channels and DMs to surface the things that get buried in
            threads.
          </p>
        </div>

        <div className="mb-6 p-4 rounded-lg bg-gray-50 border border-gray-200">
          <p className="text-sm font-medium text-black mb-3">Setup instructions</p>
          <ol className="space-y-2 text-sm text-gray-600">
            <li className="flex gap-2">
              <span className="shrink-0 font-medium text-black">1.</span>
              <span>
                Go to{' '}
                <a
                  href="https://api.slack.com/apps"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="underline hover:text-black"
                >
                  api.slack.com/apps
                </a>{' '}
                and create a new app
              </span>
            </li>
            <li className="flex gap-2">
              <span className="shrink-0 font-medium text-black">2.</span>
              <span>
                Under &quot;OAuth &amp; Permissions&quot;, add scopes:{' '}
                <code className="text-xs bg-white border border-gray-200 rounded px-1 py-0.5">
                  channels:history
                </code>
                ,{' '}
                <code className="text-xs bg-white border border-gray-200 rounded px-1 py-0.5">
                  channels:read
                </code>
                ,{' '}
                <code className="text-xs bg-white border border-gray-200 rounded px-1 py-0.5">
                  groups:history
                </code>
                ,{' '}
                <code className="text-xs bg-white border border-gray-200 rounded px-1 py-0.5">
                  im:history
                </code>
                ,{' '}
                <code className="text-xs bg-white border border-gray-200 rounded px-1 py-0.5">
                  users:read
                </code>
              </span>
            </li>
            <li className="flex gap-2">
              <span className="shrink-0 font-medium text-black">3.</span>
              <span>
                Install the app to your workspace and copy the Bot User OAuth Token (starts with{' '}
                <code className="text-xs bg-white border border-gray-200 rounded px-1 py-0.5">
                  xoxb-
                </code>
                )
              </span>
            </li>
            <li className="flex gap-2">
              <span className="shrink-0 font-medium text-black">4.</span>
              <span>
                Under &quot;Event Subscriptions&quot;, enable events and enter your webhook URL:
              </span>
            </li>
          </ol>
          <div className="mt-2 ml-6 p-2 rounded bg-white border border-gray-200">
            <p className="text-xs font-mono text-black break-all">
              {API_BASE}/api/v1/webhooks/slack/events
            </p>
          </div>
          <p className="mt-2 ml-6 text-xs text-gray-500">
            Copy the Signing Secret shown on that page and paste it below.
          </p>
        </div>

        {connectedSources.includes('slack') && (
          <div className="mb-4 p-3 rounded-lg bg-blue-50 border border-blue-200">
            <p className="text-sm font-medium text-black mb-1">Step 2: Invite bot to channels</p>
            <p className="text-sm text-gray-600">
              To receive signals from a channel, type this in that channel:
            </p>
            <p className="mt-1 font-mono text-sm text-black">
              /invite @Rippled
            </p>
          </div>
        )}

        <div className="space-y-4">
          <FormField
            label="Bot token"
            id="bot-token"
            value={slackForm.botToken}
            onChange={(v) => setSlackForm((prev) => ({ ...prev, botToken: v }))}
            placeholder="xoxb-..."
          />
          <FormField
            label="Signing secret"
            id="signing-secret"
            type="password"
            value={slackForm.signingSecret}
            onChange={(v) => setSlackForm((prev) => ({ ...prev, signingSecret: v }))}
            placeholder="••••••••••••"
          />
          <FormField
            label="Your Slack user ID"
            id="slack-user-id"
            value={slackForm.slackUserId}
            onChange={(v) => setSlackForm((prev) => ({ ...prev, slackUserId: v }))}
            placeholder="U12345678"
          />

          {slackTestResult && (
            <Banner
              success={slackTestResult.success}
              message={
                slackTestResult.success
                  ? `Connected to ${slackTestResult.workspace ?? 'workspace'} as ${slackTestResult.bot_user ?? 'bot'}`
                  : (slackTestResult.error ?? 'Connection test failed')
              }
            />
          )}

          <button
            onClick={testSlack}
            disabled={slackTestLoading || !slackForm.botToken || !slackForm.signingSecret}
            className="w-full py-2.5 rounded-lg border border-gray-200 text-black text-sm font-medium hover:bg-gray-50 active:bg-gray-100 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {slackTestLoading ? 'Testing…' : 'Test connection'}
          </button>

          <button
            onClick={connectSlack}
            disabled={slackConnectLoading || !canConnectSlack}
            className="w-full py-2.5 rounded-lg bg-black text-white text-sm font-medium hover:bg-gray-900 active:bg-gray-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {slackConnectLoading ? 'Connecting…' : 'Connect Slack'}
          </button>
        </div>

        <div className="mt-6 text-center">
          <button
            onClick={() => setStep(3)}
            className="text-sm text-gray-400 hover:text-black transition-colors"
          >
            I&apos;ll set this up later
          </button>
        </div>
      </StepLayout>
    )
  }

  // Step 3 — Meetings
  if (step === 3) {
    return (
      <StepLayout>
        <div className="mb-6">
          <p className="text-xs text-gray-400 uppercase tracking-wider mb-2">Step 3 of 4</p>
          <h1 className="text-2xl font-bold text-black">Connect meeting transcripts</h1>
          <p className="mt-3 text-sm text-gray-600 leading-relaxed">
            Meetings are commitment-dense. Every &quot;I&apos;ll handle that&quot; and &quot;we&apos;ll ship by Friday&quot; is a
            signal. Rippled reads transcripts to catch the commitments made in rooms and calls.
          </p>
        </div>

        {/* Platform picker */}
        <div className="mb-6">
          <p className="text-sm font-medium text-black mb-3">Select your transcript platform</p>
          <div className="grid grid-cols-2 gap-2">
            {MEETING_PLATFORMS.map((platform) => (
              <button
                key={platform}
                onClick={() => {
                  setMeetingPlatform(platform)
                  setMeetingResult(null)
                  setMeetingConnectError(null)
                }}
                className={`py-2 px-3 rounded-lg border text-sm font-medium transition-colors ${
                  meetingPlatform === platform
                    ? 'bg-black text-white border-black'
                    : 'bg-white text-black border-gray-200 hover:bg-gray-50'
                }`}
              >
                {PLATFORM_LABELS[platform]}
              </button>
            ))}
          </div>
        </div>

        {/* Platform instructions */}
        <div className="mb-6 p-4 rounded-lg bg-gray-50 border border-gray-200">
          <p className="text-sm text-gray-600 leading-relaxed">
            {PLATFORM_INSTRUCTIONS[meetingPlatform]}
          </p>
        </div>

        {meetingConnectError && (
          <div className="mb-4">
            <Banner success={false} message={meetingConnectError} />
          </div>
        )}

        {/* Webhook result */}
        {meetingResult ? (
          <div className="space-y-4">
            <div className="p-4 rounded-lg bg-gray-50 border border-gray-200 space-y-3">
              <div>
                <p className="text-xs font-medium text-gray-500 mb-1">Webhook URL</p>
                <p className="text-sm font-mono text-black break-all">{meetingResult.webhook_url}</p>
              </div>
              <div>
                <p className="text-xs font-medium text-gray-500 mb-1">Webhook secret</p>
                <div className="flex items-center gap-2">
                  <p className="text-sm font-mono text-black break-all flex-1">
                    {meetingResult.webhook_secret}
                  </p>
                  <button
                    onClick={() => copyToClipboard(meetingResult.webhook_secret)}
                    className="shrink-0 px-3 py-1.5 rounded border border-gray-200 text-xs font-medium text-black hover:bg-gray-100 transition-colors"
                  >
                    {copiedSecret ? 'Copied!' : 'Copy'}
                  </button>
                </div>
                <p className="mt-1 text-xs text-red-600 font-medium">
                  Save this secret — you won&apos;t see it again
                </p>
              </div>
            </div>
            <button
              onClick={() => setStep(4)}
              className="w-full py-2.5 rounded-lg bg-black text-white text-sm font-medium hover:bg-gray-900 active:bg-gray-800 transition-colors"
            >
              Continue to dashboard
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            <button
              onClick={connectMeeting}
              disabled={meetingConnectLoading}
              className="w-full py-2.5 rounded-lg bg-black text-white text-sm font-medium hover:bg-gray-900 active:bg-gray-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {meetingConnectLoading ? 'Connecting…' : 'Connect'}
            </button>
          </div>
        )}

        {!meetingResult && (
          <div className="mt-6 text-center">
            <button
              onClick={() => setStep(4)}
              className="text-sm text-gray-400 hover:text-black transition-colors"
            >
              I&apos;ll set this up later
            </button>
          </div>
        )}
      </StepLayout>
    )
  }

  // Step 4 — Calendar
  if (step === 4) {
    return (
      <StepLayout maxWidth="max-w-sm">
        <div className="mb-8">
          <p className="text-xs text-gray-400 uppercase tracking-wider mb-2">Step 4 of 4</p>
          <h1 className="text-2xl font-bold text-black">Connect your calendar</h1>
          <p className="mt-3 text-sm text-gray-600 leading-relaxed">
            Rippled uses your calendar to detect upcoming delivery moments and surface
            commitments at the right time — before the meeting, not after.
          </p>
        </div>

        <div className="space-y-3">
          <button
            onClick={() => {
              window.open(`${API_BASE}/api/v1/integrations/google/auth`, '_blank')
            }}
            className="w-full py-2.5 rounded-lg bg-black text-white text-sm font-medium hover:bg-gray-900 active:bg-gray-800 transition-colors"
          >
            Connect Google Calendar
          </button>
          <p className="text-xs text-gray-400 text-center">
            A new tab will open. Return here after connecting.
          </p>
          <button
            onClick={() => setStep(5)}
            className="w-full py-2.5 rounded-lg border border-gray-200 text-black text-sm font-medium hover:bg-gray-50 transition-colors"
          >
            I&apos;ve connected it
          </button>
        </div>

        <div className="mt-6 text-center">
          <button
            onClick={() => setStep(5)}
            className="text-sm text-gray-400 hover:text-black transition-colors"
          >
            Skip for now
          </button>
        </div>
      </StepLayout>
    )
  }

  // Step 5 — Done
  return (
    <StepLayout maxWidth="max-w-sm">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-black">Rippled is listening</h1>

        <div className="mt-6">
          {connectedSources.length === 0 ? (
            <p className="text-sm text-gray-600 leading-relaxed">
              You haven&apos;t connected any sources yet. Rippled will start working as soon as you do.
            </p>
          ) : (
            <ul className="space-y-2">
              {connectedSources.includes('email') && (
                <li className="flex items-center gap-2 text-sm text-black">
                  <span className="text-green-600 font-medium">&#10003;</span>
                  Email connected
                </li>
              )}
              {connectedSources.includes('slack') && (
                <li className="flex items-center gap-2 text-sm text-black">
                  <span className="text-green-600 font-medium">&#10003;</span>
                  Slack connected
                </li>
              )}
              {connectedSources.includes('meetings') && (
                <li className="flex items-center gap-2 text-sm text-black">
                  <span className="text-green-600 font-medium">&#10003;</span>
                  Meetings connected
                </li>
              )}
            </ul>
          )}
        </div>
      </div>

      <button
        onClick={finishOnboarding}
        disabled={doneLoading}
        className="w-full py-2.5 rounded-lg bg-black text-white text-sm font-medium hover:bg-gray-900 active:bg-gray-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {doneLoading ? 'Finishing…' : 'Go to dashboard'}
      </button>
    </StepLayout>
  )
}
