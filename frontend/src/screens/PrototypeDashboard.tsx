import { useState } from 'react'

// ─── Types ──────────────────────────────────────────────────────────────────

type Tab = 'active' | 'shortlist' | 'commitments'

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
  confidence: string
  status: CommitmentStatus
}

interface GoodCatch {
  id: string
  badge: BadgeType
  title: string
  description: string
}

// ─── Mock Data ───────────────────────────────────────────────────────────────

const ACTIVE_COMMITMENTS: Commitment[] = [
  {
    id: '1',
    title: 'Follow up with David on contract review',
    description: 'Promised 4 days ago on Slack. No response or update found since.',
    source: 'Slack',
    date: 'Last Thursday',
    person: 'David Park',
    badge: 'At risk',
    confidence: '91%',
    status: 'at-risk',
  },
  {
    id: '2',
    title: 'Send revised proposal to Sarah Chen',
    description: 'You mentioned sending the updated pricing proposal during yesterday\'s call. No follow-up detected yet.',
    source: 'Meetings',
    date: 'Yesterday, 3:42 PM',
    person: 'Sarah Chen',
    badge: 'Needs review',
    confidence: '87%',
    status: 'needs-review',
  },
  {
    id: '3',
    title: 'Timeline unclear for Acme onboarding',
    description: 'You agreed to \'get back to them next week\' but no specific date was set. Worth confirming the exact day.',
    source: 'Email',
    date: 'Monday, 11:15 AM',
    person: 'James Miller',
    badge: 'Likely missing detail',
    confidence: '72%',
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
    confidence: '68%',
    status: 'worth-confirming',
  },
]

const SHORTLIST_EXTRA: Commitment[] = [
  {
    id: '5',
    title: 'Review Q1 budget with finance team',
    description: '',
    source: 'Email',
    date: '3 days ago',
    person: 'Maria Reyes',
    badge: 'Needs review',
    confidence: '79%',
    status: 'needs-review',
  },
  {
    id: '6',
    title: 'Confirm speaker for company all-hands',
    description: '',
    source: 'Slack',
    date: 'Tuesday',
    person: 'Kevin B',
    badge: 'Worth confirming',
    confidence: '65%',
    status: 'worth-confirming',
  },
]

const ALL_COMMITMENTS: (Commitment & { listStatus?: 'delivered' | 'dismissed' })[] = [
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
    confidence: '95%',
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
    confidence: '98%',
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
    confidence: '55%',
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
    confidence: '61%',
    status: 'dismissed',
  },
]

const GOOD_CATCHES: GoodCatch[] = [
  {
    id: 'gc1',
    badge: 'Good catch',
    title: 'Duplicate commitment detected',
    description: 'You may have promised the same deliverable to both Lisa and the product team.',
  },
  {
    id: 'gc2',
    badge: 'Worth confirming',
    title: 'Meeting prep reminder',
    description: 'Tomorrow\'s call with Vertex Partners — you mentioned preparing updated metrics.',
  },
  {
    id: 'gc3',
    badge: 'Good catch',
    title: 'Unacknowledged reply',
    description: 'James Miller replied 3 days ago. No response detected on your end.',
  },
]

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

// ─── CommitmentCard ──────────────────────────────────────────────────────────

function CommitmentCard({ commitment }: { commitment: Commitment }) {
  return (
    <div className={`flex bg-white rounded-lg border border-[#e8e8e6] overflow-hidden hover:border-[#d1d1cf] transition-colors`}>
      <div className={`w-[3px] self-stretch border-l-2 ${accentClass(commitment.status)} flex-shrink-0`} style={{ borderLeftWidth: '3px', borderStyle: 'solid' }} />
      <div className="flex-1 px-4 py-3">
        <div className="flex justify-between items-center mb-1.5">
          <StatusBadge badge={commitment.badge} />
          <span className="text-[11px] text-[#9ca3af] font-medium">{commitment.confidence} confidence</span>
        </div>
        <div className="font-medium text-[14px] text-[#191919] mb-1">{commitment.title}</div>
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
        <div className="flex gap-2 mt-2.5 pt-2.5 border-t border-[#f0f0ef]">
          <button className="flex items-center gap-1.5 bg-[#191919] text-white text-[12px] px-3 py-1.5 rounded-md font-medium hover:bg-[#333] transition-colors">
            <IconCheck />
            Mark done
          </button>
          <button className="flex items-center gap-1.5 bg-[#f0f0ef] text-[#191919] text-[12px] px-3 py-1.5 rounded-md font-medium hover:bg-[#e8e8e6] transition-colors">
            <IconX />
            Dismiss
          </button>
          <button className="flex items-center gap-1.5 border border-[#e8e8e6] text-[#191919] text-[12px] px-3 py-1.5 rounded-md font-medium hover:bg-[#f5f5f4] transition-colors">
            View context
            <IconArrow />
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── CompactCommitmentRow (Commitments tab) ──────────────────────────────────

function CompactCommitmentRow({ commitment }: { commitment: Commitment }) {
  const isDelivered = commitment.status === 'delivered'
  const isDismissed = commitment.status === 'dismissed'
  const isFaded = isDelivered || isDismissed

  return (
    <div className={`flex bg-white rounded-lg border border-[#e8e8e6] overflow-hidden hover:border-[#d1d1cf] transition-colors ${isFaded ? 'opacity-60' : ''}`}>
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
        {!isFaded && (
          <div className="flex gap-1.5 flex-shrink-0">
            <button className="flex items-center gap-1 bg-[#191919] text-white text-[11px] px-2.5 py-1 rounded-md font-medium hover:bg-[#333] transition-colors">
              <IconCheck />
              Done
            </button>
            <button className="flex items-center gap-1 bg-[#f0f0ef] text-[#191919] text-[11px] px-2.5 py-1 rounded-md font-medium hover:bg-[#e8e8e6] transition-colors">
              <IconX />
              Dismiss
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

// ─── GoodCatchCard ───────────────────────────────────────────────────────────

function GoodCatchCard({ catch: c }: { catch: GoodCatch }) {
  return (
    <div className="bg-white border border-[#e8e8e6] rounded-lg p-3 hover:border-[#d1d1cf] transition-colors">
      <div className="flex items-start justify-between">
        <StatusBadge badge={c.badge} />
        <button className="text-[#9ca3af] hover:text-[#191919] transition-colors ml-2 mt-0.5">
          <IconArrow />
        </button>
      </div>
      <div className="text-[13px] font-medium text-[#191919] mt-1.5 mb-1">{c.title}</div>
      <div className="text-[12px] text-[#9ca3af] leading-relaxed">{c.description}</div>
    </div>
  )
}

// ─── ProofOfWork ─────────────────────────────────────────────────────────────

function ProofOfWork() {
  const stats = [
    { icon: <IconEmails />, label: 'Emails captured', value: '89' },
    { icon: <IconMessages />, label: 'Messages processed', value: '234' },
    { icon: <IconMeetings />, label: 'Meetings logged', value: '12' },
    { icon: <IconPeople />, label: 'People identified', value: '31' },
  ]

  return (
    <div className="bg-white border border-[#e8e8e6] rounded-lg p-4">
      <div className="text-[13px] font-semibold text-[#191919] mb-3">Proof of work</div>
      <div className="grid grid-cols-2 gap-2">
        {stats.map((s) => (
          <div key={s.label} className="bg-[#f9f9f8] rounded-md p-3">
            <div className="flex items-center gap-1.5 text-[#9ca3af]">
              {s.icon}
              <span className="text-[11px] text-[#9ca3af]">{s.label}</span>
            </div>
            <div className="font-semibold text-[20px] text-[#191919] mt-1">{s.value}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ─── Header ──────────────────────────────────────────────────────────────────

function Header({ activeTab, onTabChange }: { activeTab: Tab; onTabChange: (t: Tab) => void }) {
  const tabs: { id: Tab; label: string }[] = [
    { id: 'active', label: 'Active' },
    { id: 'shortlist', label: 'Shortlist' },
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
    <div className="bg-[#fafaf9] border-b border-[#e8e8e6] h-[36px] flex items-center px-6">
      <div className="flex items-center gap-3 flex-1">
        <div className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-[#16a34a] flex-shrink-0" />
          <span className="text-[12px] text-[#6b7280]">Email</span>
        </div>
        <span className="text-[#e8e8e6]">|</span>
        <div className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-[#16a34a] flex-shrink-0" />
          <span className="text-[12px] text-[#6b7280]">Slack</span>
        </div>
        <span className="text-[#e8e8e6]">|</span>
        <div className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-[#16a34a] flex-shrink-0" />
          <span className="text-[12px] text-[#6b7280]">Meetings</span>
        </div>
        <span className="text-[#e8e8e6]">|</span>
        <div className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-[#d97706] flex-shrink-0" />
          <span className="text-[12px] text-[#6b7280]">Calendar</span>
        </div>
      </div>
      <div className="flex items-center gap-3 text-[12px]">
        <span className="text-[#6b7280]">14 signals reviewed in the last 24 hours</span>
        <span className="text-[#e8e8e6]">|</span>
        <span className="text-[#9ca3af]">Watching 6 active threads</span>
      </div>
    </div>
  )
}

// ─── ContextBanner ───────────────────────────────────────────────────────────

function ContextBanner() {
  return (
    <div className="bg-white border-b border-[#e8e8e6] py-3 px-6 flex items-center gap-2.5">
      <span className="relative flex h-2 w-2 flex-shrink-0">
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
        <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500" />
      </span>
      <span className="text-[13px] text-[#6b7280]">
        Rippled is monitoring your inbox, Slack, and meetings
      </span>
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

// ─── Sidebar ─────────────────────────────────────────────────────────────────

function Sidebar({ showGoodCatches = true }: { showGoodCatches?: boolean }) {
  return (
    <div className="flex flex-col">
      <ProofOfWork />
      {showGoodCatches && (
        <div className="mt-4">
          <div className="text-[13px] font-semibold text-[#191919] mb-3">Good catches</div>
          <div className="flex flex-col gap-2.5">
            {GOOD_CATCHES.map((c) => (
              <GoodCatchCard key={c.id} catch={c} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Tab Content ─────────────────────────────────────────────────────────────

function ActiveTabContent() {
  return (
    <div className="grid grid-cols-[1fr_280px] gap-6">
      <div>
        <div className="flex items-center gap-2 mb-3">
          <span className="font-semibold text-[15px] text-[#191919]">What deserves your attention</span>
          <span className="bg-[#f0f0ef] text-[#6b7280] text-[11px] font-medium px-2 py-0.5 rounded-full">
            {ACTIVE_COMMITMENTS.length}
          </span>
        </div>
        <div className="flex flex-col gap-3">
          {ACTIVE_COMMITMENTS.map((c) => (
            <CommitmentCard key={c.id} commitment={c} />
          ))}
        </div>
      </div>
      <Sidebar />
    </div>
  )
}

function ShortlistTabContent() {
  const shortlist = [...ACTIVE_COMMITMENTS.slice(0, 3), ...SHORTLIST_EXTRA]
  return (
    <div className="grid grid-cols-[1fr_280px] gap-6">
      <div>
        <div className="flex items-center gap-2 mb-3">
          <span className="font-semibold text-[15px] text-[#191919]">Your shortlist — 5 most important</span>
          <span className="bg-[#f0f0ef] text-[#6b7280] text-[11px] font-medium px-2 py-0.5 rounded-full">
            {shortlist.length}
          </span>
        </div>
        <div className="flex flex-col gap-2.5">
          {shortlist.map((c) => (
            <div key={c.id} className={`flex bg-white rounded-lg border border-[#e8e8e6] overflow-hidden hover:border-[#d1d1cf] transition-colors`}>
              <div className={`w-[3px] self-stretch flex-shrink-0`} style={{ borderLeftWidth: '3px', borderLeftStyle: 'solid', borderLeftColor: accentClass(c.status).replace('border-l-[', '').replace(']', '') }} />
              <div className="flex-1 px-4 py-2.5">
                <div className="flex justify-between items-center mb-1">
                  <StatusBadge badge={c.badge} />
                  <span className="text-[11px] text-[#9ca3af]">{c.confidence}</span>
                </div>
                <div className="font-medium text-[13px] text-[#191919] mb-0.5">{c.title}</div>
                <div className="flex items-center gap-1.5 text-[12px] text-[#9ca3af] mt-1">
                  <span>{sourceIcon(c.source)}</span>
                  <span>{c.source}</span>
                  <span>·</span>
                  <span>{c.date}</span>
                  {c.person !== '—' && (
                    <>
                      <span>·</span>
                      <span>{c.person}</span>
                    </>
                  )}
                </div>
                <div className="flex gap-2 mt-2 pt-2 border-t border-[#f0f0ef]">
                  <button className="flex items-center gap-1.5 bg-[#191919] text-white text-[12px] px-3 py-1 rounded-md font-medium hover:bg-[#333] transition-colors">
                    <IconCheck />
                    Mark done
                  </button>
                  <button className="flex items-center gap-1.5 bg-[#f0f0ef] text-[#191919] text-[12px] px-3 py-1 rounded-md font-medium hover:bg-[#e8e8e6] transition-colors">
                    <IconX />
                    Dismiss
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
      <Sidebar showGoodCatches={false} />
    </div>
  )
}

function CommitmentsTabContent() {
  return (
    <div className="grid grid-cols-[1fr_280px] gap-6">
      <div>
        <div className="flex items-center gap-2 mb-3">
          <span className="font-semibold text-[15px] text-[#191919]">All commitments</span>
          <span className="bg-[#f0f0ef] text-[#6b7280] text-[11px] font-medium px-2 py-0.5 rounded-full">
            {ALL_COMMITMENTS.length}
          </span>
        </div>
        <div className="flex flex-col gap-2">
          {ALL_COMMITMENTS.map((c) => (
            <CompactCommitmentRow key={c.id} commitment={c} />
          ))}
        </div>
      </div>
      <Sidebar />
    </div>
  )
}

// ─── PrototypeDashboard ──────────────────────────────────────────────────────

export default function PrototypeDashboard() {
  const [activeTab, setActiveTab] = useState<Tab>('active')

  return (
    <div className="min-h-screen bg-[#f9f9f8]">
      <Header activeTab={activeTab} onTabChange={setActiveTab} />
      <StatusBar />
      <ContextBanner />
      <main className="max-w-[1100px] mx-auto px-6 py-6">
        {activeTab === 'active' && <ActiveTabContent />}
        {activeTab === 'shortlist' && <ShortlistTabContent />}
        {activeTab === 'commitments' && <CommitmentsTabContent />}
      </main>
    </div>
  )
}
