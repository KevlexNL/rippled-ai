import { useState } from 'react'

// ─── Types ──────────────────────────────────────────────────────────────────

type Tab = 'active' | 'commitments'

type GroupMode = 'status' | 'client' | 'source'

type BadgeType =
  | 'At risk'
  | 'Needs review'
  | 'Worth confirming'
  | 'Good catch'
  | 'Likely missing detail'
  | 'Low signal'
  | 'Delivered'
  | 'Dismissed'

type CommitmentStatus = 'at-risk' | 'needs-review' | 'worth-confirming' | 'likely-missing' | 'default' | 'delivered' | 'dismissed'

interface Commitment {
  id: string
  title: string
  description: string
  source: 'Email' | 'Slack' | 'Meetings' | 'Calendar'
  date: string
  person: string
  badge: BadgeType
  confidence: number
  status: CommitmentStatus
}

interface NextMove extends Commitment {
  rationale: string
}

// ─── Mock Data ───────────────────────────────────────────────────────────────

const ACTIVE_COMMITMENTS: Commitment[] = [
  {
    id: '1',
    title: 'David contract review may need a follow-up',
    description: 'Promised 4 days ago on Slack. No response or update found since.',
    source: 'Slack',
    date: 'Last Thursday',
    person: 'David Park',
    badge: 'At risk',
    confidence: 91,
    status: 'at-risk',
  },
  {
    id: '2',
    title: 'Revised proposal for Sarah Chen may still be outstanding',
    description: 'You mentioned sending the updated pricing proposal during yesterday\'s call. No follow-up detected yet.',
    source: 'Meetings',
    date: 'Yesterday, 3:42 PM',
    person: 'Sarah Chen',
    badge: 'Needs review',
    confidence: 87,
    status: 'needs-review',
  },
  {
    id: '3',
    title: 'Acme onboarding follow-up may need a clearer date',
    description: 'You agreed to \'get back to them next week\' but no specific date was set. Worth confirming the exact day.',
    source: 'Email',
    date: 'Monday, 11:15 AM',
    person: 'James Miller',
    badge: 'Likely missing detail',
    confidence: 72,
    status: 'likely-missing',
  },
  {
    id: '4',
    title: 'Share design mockups with marketing team',
    description: 'Mentioned in standup that you\'d share by end of week. Two days remaining.',
    source: 'Meetings',
    date: 'Wednesday, 9:30 AM',
    person: '—',
    badge: 'Worth confirming',
    confidence: 68,
    status: 'worth-confirming',
  },
]

const UP_NEXT: NextMove[] = [
  { ...ACTIVE_COMMITMENTS[3], rationale: 'Promised in standup — deadline approaching' },
  {
    id: '5',
    title: 'Review Q1 budget with finance team',
    description: '',
    source: 'Email',
    date: '3 days ago',
    person: 'Maria Reyes',
    badge: 'Needs review',
    confidence: 79,
    status: 'needs-review',
    rationale: 'Quick confirmation may unblock follow-up',
  },
  {
    id: '6',
    title: 'Confirm speaker for company all-hands',
    description: '',
    source: 'Slack',
    date: 'Tuesday',
    person: 'Kevin B',
    badge: 'Worth confirming',
    confidence: 65,
    status: 'worth-confirming',
    rationale: 'Likely waiting on your reply — low effort to close',
  },
  {
    id: '11',
    title: 'Send updated NDA to Vertex legal team',
    description: '',
    source: 'Email',
    date: 'Yesterday',
    person: 'Rachel Kim',
    badge: 'Needs review',
    confidence: 74,
    status: 'needs-review',
    rationale: 'External promise — no response detected',
  },
  {
    id: '12',
    title: 'Respond to partner integration timeline request',
    description: '',
    source: 'Slack',
    date: 'Monday',
    person: 'Leo Tran',
    badge: 'Worth confirming',
    confidence: 66,
    status: 'worth-confirming',
    rationale: 'Short reply could confirm ownership and move this forward',
  },
]

const ALL_COMMITMENTS: Commitment[] = [
  { ...ACTIVE_COMMITMENTS[0] },
  { ...ACTIVE_COMMITMENTS[1] },
  {
    id: '7',
    title: 'Send product roadmap to investors',
    description: '',
    source: 'Email',
    date: 'Last Monday',
    person: 'Priya Nair',
    badge: 'Delivered',
    confidence: 95,
    status: 'delivered',
  },
  {
    id: '8',
    title: 'Schedule 1:1 with eng lead',
    description: '',
    source: 'Slack',
    date: 'Last Friday',
    person: 'Tom West',
    badge: 'Delivered',
    confidence: 98,
    status: 'delivered',
  },
  { ...ACTIVE_COMMITMENTS[2] },
  { ...ACTIVE_COMMITMENTS[3] },
  {
    id: '9',
    title: 'Update onboarding doc with new login flow',
    description: '',
    source: 'Meetings',
    date: 'Last Wednesday',
    person: '—',
    badge: 'Dismissed',
    confidence: 55,
    status: 'dismissed',
  },
  {
    id: '10',
    title: 'Ping Alex re: security audit findings',
    description: '',
    source: 'Email',
    date: 'Last Tuesday',
    person: 'Alex Patel',
    badge: 'Dismissed',
    confidence: 61,
    status: 'dismissed',
  },
  ...UP_NEXT.slice(1),
]

// ─── Detail Mock Data ────────────────────────────────────────────────────────

const DETAIL_MOCK: Record<string, { whySurfaced: string; signals: { source: string; text: string }[]; relatedRole: string; suggestedMove: string }> = {
  '1': {
    whySurfaced: 'This commitment was made directly to a client stakeholder and has gone unanswered for 4 days. The lack of any follow-up signal after the initial promise makes this a likely drop.',
    signals: [
      { source: 'Slack', text: 'Mentioned in #project channel, last Thursday — "I\'ll get the contract review done by EOD"' },
      { source: 'Slack', text: 'No reply or thread activity since original message' },
    ],
    relatedRole: 'Engineering Lead',
    suggestedMove: 'Send David a quick update or ask if the review is still needed. Even a short acknowledgement resets the clock.',
  },
  '2': {
    whySurfaced: 'You verbally committed to sending a revised pricing proposal during yesterday\'s call. No email or document share has been detected since.',
    signals: [
      { source: 'Meetings', text: 'Call with Sarah Chen — Yesterday, 3:42 PM — "I\'ll send the updated numbers tonight"' },
      { source: 'Email', text: 'No outbound email to Sarah Chen found in the last 24 hours' },
    ],
    relatedRole: 'Account Executive',
    suggestedMove: 'Draft and send the revised proposal to Sarah. If it\'s not ready, let her know the revised timeline.',
  },
  '3': {
    whySurfaced: 'The commitment to follow up was made with a vague timeframe ("next week") and no specific date. This often leads to missed expectations.',
    signals: [
      { source: 'Email', text: 'Email to James Miller — Monday, 11:15 AM — "We\'ll get back to you next week"' },
      { source: 'Calendar', text: 'No calendar event found for Acme follow-up this week' },
    ],
    relatedRole: 'Client Success Manager',
    suggestedMove: 'Pick a specific day and send a calendar invite for the Acme onboarding follow-up.',
  },
  '4': {
    whySurfaced: 'You volunteered to share design mockups by end of week during standup. Two days remain but no share or upload has been detected.',
    signals: [
      { source: 'Meetings', text: 'Standup — Wednesday, 9:30 AM — "I\'ll share the mockups by Friday"' },
    ],
    relatedRole: 'Design Lead',
    suggestedMove: 'Prepare and share the mockups today to give the marketing team time to review before the weekend.',
  },
  '5': {
    whySurfaced: 'A Q1 budget review was requested via email 3 days ago. No response or calendar invite has been detected since.',
    signals: [
      { source: 'Email', text: 'Email from Maria Reyes — 3 days ago — "Can we review the Q1 budget this week?"' },
    ],
    relatedRole: 'Finance Lead',
    suggestedMove: 'Reply to Maria with available times or send a calendar invite for the budget review.',
  },
  '6': {
    whySurfaced: 'You were asked to confirm the speaker for the company all-hands. No reply has been detected.',
    signals: [
      { source: 'Slack', text: 'Message in #events — Tuesday — "Can you confirm the speaker for Friday\'s all-hands?"' },
    ],
    relatedRole: 'Events Coordinator',
    suggestedMove: 'Confirm the speaker or let Kevin know if you need more time to finalize.',
  },
  '11': {
    whySurfaced: 'An updated NDA was promised to Vertex\'s legal team. No outbound document or email has been detected.',
    signals: [
      { source: 'Email', text: 'Email thread with Rachel Kim — Yesterday — "I\'ll send the updated NDA today"' },
    ],
    relatedRole: 'Legal Contact',
    suggestedMove: 'Send the updated NDA to Rachel or let her know the revised timeline.',
  },
  '12': {
    whySurfaced: 'A partner asked about the integration timeline on Slack. No response has been detected.',
    signals: [
      { source: 'Slack', text: 'DM from Leo Tran — Monday — "Any update on the integration timeline?"' },
    ],
    relatedRole: 'Partner Engineer',
    suggestedMove: 'Send Leo a quick update on the integration timeline, even if details are still being finalized.',
  },
}

const DETAIL_FALLBACK = {
  whySurfaced: 'This item was flagged based on pattern matching across your communication channels. Rippled detected language suggesting a commitment that may need follow-up.',
  signals: [
    { source: 'Multiple', text: 'Cross-referenced across connected sources' },
  ],
  relatedRole: 'Colleague',
  suggestedMove: 'Review this item and confirm whether it still needs action.',
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function confidenceLabel(confidence: number): string {
  if (confidence >= 85) return 'High confidence'
  if (confidence >= 70) return 'Medium confidence'
  return 'Some uncertainty'
}

// ─── Icons (inline SVG) ──────────────────────────────────────────────────────

function IconMail() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="4" width="20" height="16" rx="2" />
      <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7" />
    </svg>
  )
}

function IconHash() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="4" x2="20" y1="9" y2="9" />
      <line x1="4" x2="20" y1="15" y2="15" />
      <line x1="10" x2="8" y1="3" y2="21" />
      <line x1="16" x2="14" y1="3" y2="21" />
    </svg>
  )
}

function IconVideo() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="m22 8-6 4 6 4V8z" />
      <rect x="2" y="6" width="14" height="12" rx="2" />
    </svg>
  )
}

function IconCalendar() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="4" width="18" height="18" rx="2" />
      <line x1="16" x2="16" y1="2" y2="6" />
      <line x1="8" x2="8" y1="2" y2="6" />
      <line x1="3" x2="21" y1="10" y2="10" />
    </svg>
  )
}

function IconCheck() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  )
}

function IconX() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" x2="6" y1="6" y2="18" />
      <line x1="6" x2="18" y1="6" y2="18" />
    </svg>
  )
}

function IconArrow() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M5 12h14" />
      <path d="m12 5 7 7-7 7" />
    </svg>
  )
}

function IconBell() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
      <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
    </svg>
  )
}

function IconGear() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  )
}

function IconInbox() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="22 12 16 12 14 15 10 15 8 12 2 12" />
      <path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z" />
    </svg>
  )
}

function IconEmails() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="4" width="20" height="16" rx="2" />
      <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7" />
    </svg>
  )
}

function IconMessages() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  )
}

function IconMeetings() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="m22 8-6 4 6 4V8z" />
      <rect x="2" y="6" width="14" height="12" rx="2" />
    </svg>
  )
}

function IconPeople() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
      <path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </svg>
  )
}

function IconClose() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" x2="6" y1="6" y2="18" />
      <line x1="6" x2="18" y1="6" y2="18" />
    </svg>
  )
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function sourceIcon(source: Commitment['source']) {
  switch (source) {
    case 'Email': return <IconMail />
    case 'Slack': return <IconHash />
    case 'Meetings': return <IconVideo />
    case 'Calendar': return <IconCalendar />
  }
}

function badgeClasses(badge: BadgeType): string {
  switch (badge) {
    case 'Needs review': return 'bg-[#fef3c7] text-[#92400e]'
    case 'At risk': return 'bg-[#fee2e2] text-[#991b1b]'
    case 'Worth confirming': return 'bg-[#eff6ff] text-[#1d4ed8]'
    case 'Good catch': return 'bg-[#f0fdf4] text-[#15803d]'
    case 'Likely missing detail': return 'bg-[#f5f3ff] text-[#6d28d9]'
    case 'Low signal': return 'bg-[#f9fafb] text-[#6b7280] border border-[#e8e8e6]'
    case 'Delivered': return 'bg-[#f0fdf4] text-[#15803d]'
    case 'Dismissed': return 'bg-[#f9fafb] text-[#6b7280] border border-[#e8e8e6]'
  }
}

function accentClass(status: CommitmentStatus): string {
  switch (status) {
    case 'at-risk': return 'border-l-[#dc2626]'
    case 'needs-review': return 'border-l-[#d97706]'
    case 'worth-confirming': return 'border-l-[#2563eb]'
    case 'likely-missing': return 'border-l-[#6d28d9]'
    case 'delivered': return 'border-l-[#16a34a]'
    case 'dismissed': return 'border-l-[#d1d1cf]'
    default: return 'border-l-[#e8e8e6]'
  }
}

// ─── StatusBadge ─────────────────────────────────────────────────────────────

function StatusBadge({ badge }: { badge: BadgeType }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ${badgeClasses(badge)}`}>
      {badge}
    </span>
  )
}

// ─── DetailPanel ─────────────────────────────────────────────────────────────

function DetailPanel({ commitment, onClose }: { commitment: Commitment | null; onClose: () => void }) {
  const isOpen = commitment !== null
  const detail = commitment ? (DETAIL_MOCK[commitment.id] || DETAIL_FALLBACK) : DETAIL_FALLBACK

  return (
    <div
      className={`fixed top-0 right-0 h-full w-[400px] bg-white border-l border-[#e8e8e6] shadow-xl z-50 flex flex-col overflow-y-auto transition-transform duration-200 ease-in-out ${isOpen ? 'translate-x-0' : 'translate-x-full'}`}
    >
      {commitment && (
        <>
          {/* Header */}
          <div className="flex items-start justify-between px-5 pt-5 pb-4 border-b border-[#f0f0ef]">
            <div className="flex-1 min-w-0">
              <div className="mb-2">
                <StatusBadge badge={commitment.badge} />
              </div>
              <div className="font-semibold text-[15px] leading-snug text-[#191919]">{commitment.title}</div>
            </div>
            {/* FIX 2: Larger close button hit target */}
            <button onClick={onClose} className="w-8 h-8 flex items-center justify-center text-[#9ca3af] hover:text-[#191919] hover:bg-[#f0f0ef] rounded-md transition-colors ml-3 mt-0.5 flex-shrink-0">
              <IconClose />
            </button>
          </div>

          {/* Status & confidence */}
          <div className="px-5 py-3 border-b border-[#f0f0ef]">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-[#9ca3af] mb-1.5">Status</div>
            <div className="flex items-center gap-2">
              <StatusBadge badge={commitment.badge} />
              <span className="text-[12px] text-[#6b7280]">{commitment.confidence}% confidence</span>
            </div>
          </div>

          {/* Why surfaced */}
          <div className="px-5 py-3 border-b border-[#f0f0ef]">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-[#9ca3af] mb-1.5">Why Rippled surfaced this</div>
            <div className="text-[13px] text-[#6b7280] leading-relaxed italic">{detail.whySurfaced}</div>
          </div>

          {/* Source signals */}
          <div className="px-5 py-3 border-b border-[#f0f0ef]">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-[#9ca3af] mb-1.5">Source signals</div>
            <div className="flex flex-col gap-2">
              {detail.signals.map((s, i) => (
                <div key={i} className="flex items-start gap-2 text-[13px] text-[#6b7280]">
                  <span className="text-[#9ca3af] mt-0.5 flex-shrink-0">{sourceIcon(s.source as Commitment['source'])}</span>
                  <span>{s.text}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Related — FIX 5: use person field, no "Unknown" */}
          <div className="px-5 py-3 border-b border-[#f0f0ef]">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-[#9ca3af] mb-1.5">Related</div>
            <div className="text-[13px] text-[#191919]">
              {commitment.person !== '—' ? (
                <>{commitment.person} <span className="text-[#9ca3af]">· {detail.relatedRole}</span></>
              ) : (
                <span className="text-[#9ca3af]">—</span>
              )}
            </div>
          </div>

          {/* Suggested next move */}
          <div className="px-5 py-3 flex-1">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-[#9ca3af] mb-1.5">Suggested next move</div>
            <div className="text-[13px] text-[#191919] leading-relaxed">{detail.suggestedMove}</div>
          </div>

          {/* Sticky bottom action bar */}
          <div className="sticky bottom-0 bg-white border-t border-[#e8e8e6] px-5 py-3 flex items-center gap-2">
            <button className="flex items-center gap-1.5 bg-[#191919] text-white text-[12px] px-3.5 py-1.5 rounded-md font-medium hover:bg-[#333] transition-colors">
              <IconCheck />
              Confirm
            </button>
            <button className="flex items-center gap-1.5 border border-[#e8e8e6] text-[#191919] text-[12px] px-3.5 py-1.5 rounded-md font-medium hover:bg-[#f5f5f4] transition-colors">
              <IconX />
              Dismiss
            </button>
            <span onClick={onClose} className="text-[12px] text-[#9ca3af] hover:text-[#191919] cursor-pointer transition-colors ml-auto">
              Close panel
            </span>
          </div>
        </>
      )}
    </div>
  )
}

// ─── CommitmentCard ──────────────────────────────────────────────────────────

function CommitmentCard({ commitment, onOpen }: { commitment: Commitment; onOpen: (id: string) => void }) {
  return (
    <div
      className={`flex bg-white rounded-lg border border-[#e8e8e6] overflow-hidden hover:border-[#d1d1cf] transition-colors cursor-pointer`}
      onClick={() => onOpen(commitment.id)}
    >
      <div className={`w-[3px] self-stretch border-l-2 ${accentClass(commitment.status)} flex-shrink-0`} style={{ borderLeftWidth: '3px', borderStyle: 'solid' }} />
      <div className="flex-1 px-3.5 py-2.5">
        <div className="flex justify-between items-center mb-1">
          <StatusBadge badge={commitment.badge} />
          <span className="text-[11px] text-[#9ca3af] font-medium">{confidenceLabel(commitment.confidence)}</span>
        </div>
        <div className="font-medium text-[14px] text-[#191919] mb-0.5">{commitment.title}</div>
        {commitment.description && (
          <div className="text-[13px] text-[#6b7280] leading-relaxed mb-2.5">{commitment.description}</div>
        )}
        <div className="flex items-center gap-1.5 text-[12px] text-[#9ca3af] mb-0">
          <span className="text-[#9ca3af]">{sourceIcon(commitment.source)}</span>
          <span>{commitment.source}</span>
          <span>·</span>
          <span>{commitment.date}</span>
          {commitment.person !== '—' && (
            <>
              <span>·</span>
              <span>{commitment.person}</span>
            </>
          )}
        </div>
        {/* FIX 8: "Why this?" in same action row as buttons */}
        <div className="flex items-center gap-2 mt-2 pt-2 border-t border-[#f0f0ef]">
          <button
            className="flex items-center gap-1.5 bg-[#191919] text-white text-[11px] px-3 py-1 rounded-md font-medium hover:bg-[#333] transition-colors"
            onClick={(e) => e.stopPropagation()}
          >
            <IconCheck />
            Confirm
          </button>
          <button
            className="flex items-center gap-1.5 bg-[#f0f0ef] text-[#191919] text-[11px] px-3 py-1 rounded-md font-medium hover:bg-[#e8e8e6] transition-colors"
            onClick={(e) => e.stopPropagation()}
          >
            <IconX />
            Dismiss
          </button>
          <button
            className="flex items-center gap-1.5 border border-[#e8e8e6] text-[#191919] text-[11px] px-3 py-1 rounded-md font-medium hover:bg-[#f5f5f4] transition-colors"
            onClick={(e) => e.stopPropagation()}
          >
            Details
          </button>
          <span
            className="text-[11px] text-[#9ca3af] hover:text-[#191919] cursor-pointer transition-colors flex items-center gap-1"
            onClick={(e) => { e.stopPropagation(); onOpen(commitment.id) }}
          >
            Why this? <IconArrow />
          </span>
        </div>
      </div>
    </div>
  )
}

// ─── CompactCommitmentRow (Commitments tab) ──────────────────────────────────

function CompactCommitmentRow({ commitment, selected, onClick }: { commitment: Commitment; selected: boolean; onClick: () => void }) {
  const isDelivered = commitment.status === 'delivered'
  const isDismissed = commitment.status === 'dismissed'
  const isFaded = isDelivered || isDismissed

  return (
    <div
      className={`rounded-lg border overflow-hidden transition-colors cursor-pointer ${
        isDelivered ? 'bg-[#f0fdf4]' : 'bg-white'
      } ${
        selected ? 'bg-[#f5f5f4] border-[#d1d1cf]' : 'border-[#e8e8e6] hover:border-[#d1d1cf]'
      } ${isFaded ? 'opacity-60' : ''}`}
      onClick={onClick}
    >
      <div className="flex">
        <div className={`w-[3px] self-stretch flex-shrink-0 ${accentClass(commitment.status)}`} style={{ borderLeftWidth: '3px', borderLeftStyle: 'solid', borderLeftColor: accentClass(commitment.status).replace('border-l-', '') }} />
        <div className="flex-1 px-4 py-2.5 flex items-center gap-3 flex-wrap">
          <StatusBadge badge={commitment.badge} />
          <span className={`text-[13px] font-medium text-[#191919] flex-1 min-w-0 ${isDelivered ? 'line-through text-[#9ca3af]' : ''}`}>
            {commitment.title}
          </span>
          <div className="flex items-center gap-1.5 text-[12px] text-[#9ca3af] flex-shrink-0">
            <span>{sourceIcon(commitment.source)}</span>
            <span>{commitment.source}</span>
            <span>·</span>
            <span>{commitment.date}</span>
            {commitment.person !== '—' && (
              <>
                <span>·</span>
                <span>{commitment.person}</span>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

// ─── BestNextMovesRail ───────────────────────────────────────────────────────

function BestNextMovesRail({ onOpen }: { onOpen: (id: string) => void }) {
  return (
    <div className="border-l border-[#f0f0ef] pl-5">
      <div className="mb-1">
        <span className="font-semibold text-[13px] text-[#191919]">Best next moves</span>
        <span className="text-[#9ca3af] text-[12px] ml-1.5">· 5</span>
      </div>
      <div className="text-[11px] text-[#9ca3af] mb-3">5 likely next moves to unblock work or move commitments forward.</div>
      <div className="flex flex-col max-h-[520px] overflow-y-auto">
        {UP_NEXT.map((c, i) => (
          <div
            key={c.id}
            className={`group px-3 py-3 rounded-md hover:bg-[#f5f5f4] cursor-pointer transition-colors ${i < UP_NEXT.length - 1 ? 'border-b border-[#f0f0ef]' : ''}`}
            onClick={() => onOpen(c.id)}
          >
            <div className="mb-1">
              <StatusBadge badge={c.badge} />
            </div>
            <div className="flex items-start justify-between gap-2">
              <div className="text-[13px] font-medium text-[#191919] leading-snug">{c.title}</div>
              <span className="opacity-0 group-hover:opacity-100 transition-opacity text-[11px] text-[#9ca3af] flex-shrink-0 mt-0.5">
                Open →
              </span>
            </div>
            <div className="flex items-center gap-1 text-[11px] text-[#9ca3af] mt-1">
              <span>{c.source}</span>
              <span>·</span>
              <span>{c.date}</span>
            </div>
            <div className="text-[11px] text-[#6b7280] italic mt-0.5">{c.rationale}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ─── ProofOfWork (sticky footer) ─────────────────────────────────────────────

function ProofOfWork() {
  return (
    <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-[#e8e8e6] z-10">
      <div className="flex justify-center py-3 px-6">
        <span className="text-[12px] text-[#9ca3af]">
          89 emails captured · 234 messages processed · 12 meetings logged · 31 people identified
        </span>
      </div>
    </div>
  )
}

// ─── Header ──────────────────────────────────────────────────────────────────

function Header({ activeTab, onTabChange }: { activeTab: Tab; onTabChange: (t: Tab) => void }) {
  const tabs: { id: Tab; label: string }[] = [
    { id: 'active', label: 'Active' },
    { id: 'commitments', label: 'Commitments' },
  ]

  return (
    <div className="bg-white border-b border-[#e8e8e6] h-[52px] flex items-center px-6">
      <div className="flex items-center flex-1">
        <span className="font-semibold text-[16px] text-[#191919] tracking-tight">rippled</span>
      </div>
      <div className="flex items-center gap-1">
        {tabs.map((t) =>
          activeTab === t.id ? (
            <button
              key={t.id}
              onClick={() => onTabChange(t.id)}
              className="bg-[#191919] text-white rounded-full px-4 py-1 text-[13px] font-medium"
            >
              {t.label}
            </button>
          ) : (
            <button
              key={t.id}
              onClick={() => onTabChange(t.id)}
              className="text-[#6b7280] hover:text-[#191919] px-4 py-1 text-[13px] transition-colors"
            >
              {t.label}
            </button>
          )
        )}
      </div>
      <div className="flex items-center gap-3 flex-1 justify-end">
        <button className="text-[#9ca3af] hover:text-[#191919] transition-colors">
          <IconBell />
        </button>
        <button className="text-[#9ca3af] hover:text-[#191919] transition-colors">
          <IconGear />
        </button>
        <div className="w-7 h-7 rounded-full bg-[#191919] flex items-center justify-center text-white text-[11px] font-semibold cursor-pointer">
          K
        </div>
      </div>
    </div>
  )
}

// ─── StatusBar ───────────────────────────────────────────────────────────────

function StatusBar() {
  return (
    <div className="bg-[#fafaf9] border-b border-[#e8e8e6] h-[32px] flex items-center px-5">
      <div className="flex items-center gap-2 flex-1">
        <div className="flex items-center gap-1">
          <span className="w-1.5 h-1.5 rounded-full bg-[#16a34a] flex-shrink-0" />
          <span className="text-[12px] text-[#6b7280]">Email</span>
        </div>
        <span className="text-[#e8e8e6]">|</span>
        <div className="flex items-center gap-1">
          <span className="w-1.5 h-1.5 rounded-full bg-[#16a34a] flex-shrink-0" />
          <span className="text-[12px] text-[#6b7280]">Slack</span>
        </div>
        <span className="text-[#e8e8e6]">|</span>
        <div className="flex items-center gap-1">
          <span className="w-1.5 h-1.5 rounded-full bg-[#16a34a] flex-shrink-0" />
          <span className="text-[12px] text-[#6b7280]">Meetings</span>
        </div>
        <span className="text-[#e8e8e6]">|</span>
        <div className="flex items-center gap-1">
          <span className="w-1.5 h-1.5 rounded-full bg-[#d97706] flex-shrink-0" />
          <span className="text-[12px] text-[#6b7280]">Calendar</span>
        </div>
      </div>
      {/* FIX 4: Added pr-4 to prevent right-side text clipping */}
      <div className="flex items-center gap-3 text-[12px] pr-4">
        <span className="text-[#6b7280]">14 signals reviewed in the last 24 hours</span>
        <span className="text-[#e8e8e6]">|</span>
        <span className="text-[#9ca3af]">Watching 6 active threads</span>
      </div>
    </div>
  )
}

// ─── CenteredHeading ─────────────────────────────────────────────────────────

function CenteredHeading({ heading, subline, countLine }: { heading: string; subline: string; countLine?: string }) {
  return (
    // FIX 7: Reduced top padding from py-5 to pt-2 pb-4
    <div className="pt-2 pb-4 max-w-[480px] mx-auto text-center">
      <div className="font-semibold text-[22px] text-[#191919]">{heading}</div>
      <div className="text-[14px] text-[#6b7280] mt-1.5">{subline}</div>
      {countLine && <div className="text-[12px] text-[#9ca3af] mt-1.5">{countLine}</div>}
    </div>
  )
}

// ─── Empty State ──────────────────────────────────────────────────────────────

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="text-[#d1d1cf] mb-4">
        <IconInbox />
      </div>
      <div className="text-[14px] text-[#6b7280] mb-1.5">Nothing needs your attention right now.</div>
      <div className="text-[13px] text-[#9ca3af]">
        Rippled is watching — we'll surface items when something deserves it.
      </div>
    </div>
  )
}

// ─── Tab Content ─────────────────────────────────────────────────────────────

function ActiveTabContent({ onOpen }: { onOpen: (id: string) => void }) {
  const surfaced = ACTIVE_COMMITMENTS.slice(0, 3)

  return (
    <>
      <CenteredHeading
        heading="What deserves your attention"
        subline="Rippled is only surfacing the highest-priority items right now."
        countLine="Showing 3 highest-priority items"
      />
      {/* FIX 9: Visual separation between cards and rail handled by BestNextMovesRail border-l */}
      <div className="grid grid-cols-[1fr_280px] gap-6">
        <div>
          <div className="flex flex-col gap-3">
            {surfaced.map((c) => (
              <CommitmentCard key={c.id} commitment={c} onOpen={onOpen} />
            ))}
          </div>
        </div>
        <BestNextMovesRail onOpen={onOpen} />
      </div>
    </>
  )
}

function CommitmentsTabContent({ onOpen, selectedId }: { onOpen: (id: string) => void; selectedId: string | null }) {
  const [groupMode, setGroupMode] = useState<GroupMode>('status')
  const [showDismissed, setShowDismissed] = useState(false)

  const groupModes: { id: GroupMode; label: string }[] = [
    { id: 'status', label: 'Status' },
    { id: 'client', label: 'Client' },
    { id: 'source', label: 'Source' },
  ]

  const statusOrder: BadgeType[] = ['Needs review', 'Worth confirming', 'At risk', 'Delivered', 'Dismissed']
  const clientGroups: Record<string, string[]> = {
    'Acme Corp': ['1', '3'],
    'Vertex Partners': ['2', '6'],
    'Internal': ['4', '5', '7', '8', '9', '10', '11', '12'],
  }
  const sourceGroups: Commitment['source'][] = ['Email', 'Slack', 'Meetings']

  const dismissedCount = ALL_COMMITMENTS.filter((c) => c.badge === 'Dismissed').length

  function renderGrouped() {
    if (groupMode === 'status') {
      return (
        <>
          {statusOrder.map((badge) => {
            const items = ALL_COMMITMENTS.filter((c) => c.badge === badge)
            if (items.length === 0) return null
            if (badge === 'Dismissed' && !showDismissed) return null
            return (
              <div key={badge}>
                <div className="text-[11px] font-semibold uppercase tracking-wide text-[#6b7280] mt-6 mb-2">{badge} · {items.length}</div>
                <div className="flex flex-col gap-2">
                  {items.map((c) => (
                    <CompactCommitmentRow
                      key={c.id}
                      commitment={c}
                      selected={selectedId === c.id}
                      onClick={() => onOpen(c.id)}
                    />
                  ))}
                </div>
              </div>
            )
          })}
          {/* FIX 6: Toggle dismissed show/hide */}
          {dismissedCount > 0 && (
            <span
              className="text-[12px] text-[#9ca3af] hover:text-[#6b7280] cursor-pointer mt-4 inline-block hover:underline underline-offset-2"
              onClick={() => setShowDismissed(!showDismissed)}
            >
              {showDismissed ? 'Hide dismissed' : `Show dismissed (${dismissedCount})`}
            </span>
          )}
        </>
      )
    }

    if (groupMode === 'client') {
      return Object.entries(clientGroups).map(([client, ids]) => {
        let items = ALL_COMMITMENTS.filter((c) => ids.includes(c.id))
        if (!showDismissed) items = items.filter((c) => c.badge !== 'Dismissed')
        if (items.length === 0) return null
        return (
          <div key={client}>
            <div className="text-[11px] font-semibold uppercase tracking-wide text-[#6b7280] mt-6 mb-2">{client} · {items.length}</div>
            <div className="flex flex-col gap-2">
              {items.map((c) => (
                <CompactCommitmentRow
                  key={c.id}
                  commitment={c}
                  selected={selectedId === c.id}
                  onClick={() => onOpen(c.id)}
                />
              ))}
            </div>
          </div>
        )
      })
    }

    if (groupMode === 'source') {
      return sourceGroups.map((source) => {
        let items = ALL_COMMITMENTS.filter((c) => c.source === source)
        if (!showDismissed) items = items.filter((c) => c.badge !== 'Dismissed')
        if (items.length === 0) return null
        return (
          <div key={source}>
            <div className="text-[11px] font-semibold uppercase tracking-wide text-[#6b7280] mt-6 mb-2">{source} · {items.length}</div>
            <div className="flex flex-col gap-2">
              {items.map((c) => (
                <CompactCommitmentRow
                  key={c.id}
                  commitment={c}
                  selected={selectedId === c.id}
                  onClick={() => onOpen(c.id)}
                />
              ))}
            </div>
          </div>
        )
      })
    }

    return null
  }

  return (
    <div className="max-w-[720px] mx-auto">
      <CenteredHeading
        heading="All commitments"
        subline="A broader view of likely commitments Rippled is tracking across your connected sources."
      />
      <div className="flex items-center mb-5">
        <span className="text-[12px] text-[#6b7280] font-medium mr-2">Group by:</span>
        {groupModes.map((g) => (
          <button
            key={g.id}
            onClick={() => setGroupMode(g.id)}
            className={`px-3 py-1 rounded-full text-[12px] font-medium transition-colors mr-1 ${
              groupMode === g.id
                ? 'bg-[#191919] text-white'
                : 'border border-[#e8e8e6] text-[#6b7280] hover:text-[#191919]'
            }`}
          >
            {g.label}
          </button>
        ))}
        <button className="ml-auto text-[11px] text-[#9ca3af] border border-[#e8e8e6] rounded-full px-2.5 py-1 hover:text-[#191919] transition-colors">
          Filters
        </button>
      </div>
      <div>{renderGrouped()}</div>
    </div>
  )
}

// ─── PrototypeDashboard ──────────────────────────────────────────────────────

export default function PrototypeDashboard() {
  const [activeTab, setActiveTab] = useState<Tab>('active')
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const allData = [...ACTIVE_COMMITMENTS, ...UP_NEXT, ...ALL_COMMITMENTS]
  const selectedCommitment = selectedId ? allData.find((c) => c.id === selectedId) || null : null

  // FIX 1: Close detail panel on tab switch
  const handleTabChange = (t: Tab) => {
    setActiveTab(t)
    setSelectedId(null)
  }

  return (
    <div className="min-h-screen bg-[#f9f9f8]">
      <Header activeTab={activeTab} onTabChange={handleTabChange} />
      <StatusBar />
      <main className="max-w-[1100px] mx-auto px-6 py-6 pb-16">
        {activeTab === 'active' && <ActiveTabContent onOpen={(id) => setSelectedId(id)} />}
        {activeTab === 'commitments' && <CommitmentsTabContent onOpen={(id) => setSelectedId(id)} selectedId={selectedId} />}
      </main>
      <ProofOfWork />
      <DetailPanel commitment={selectedCommitment} onClose={() => setSelectedId(null)} />
    </div>
  )
}
