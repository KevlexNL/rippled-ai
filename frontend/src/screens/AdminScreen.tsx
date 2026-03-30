import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useAuth } from '../lib/auth'
import { apiGet, apiPost } from '../lib/apiClient'

const ADMIN_USER_ID = '441f9c1f-9428-477e-a04f-fb8d5e654ec2'

// ─── Types ───────────────────────────────────────────────────────────────

interface SignalItem {
  detection_audit_id: string
  source_item_id: string
  content: string
  full_content: string
  sender_name: string | null
  sender_email: string | null
  occurred_at: string | null
  parsed_result: Record<string, unknown> | null
  prompt_version: string | null
  model: string | null
}

interface OutcomeItem {
  commitment_id: string
  title: string
  commitment_text: string | null
  lifecycle_state: string
  source_context: string | null
}

interface ReviewStats {
  unreviewed_signals: number
  unreviewed_outcomes: number
  last_review_date: string | null
  total_signal_feedback: number
  total_outcome_feedback: number
}

type ExtractionCorrect = 'correct' | 'partial' | 'wrong'
type WasUseful = 'yes' | 'partial' | 'no'
type AdminTab = 'signals' | 'outcomes'

// ─── Helpers ─────────────────────────────────────────────────────────────

function formatDate(iso: string | null | undefined): string {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

function formatRelativeDate(iso: string | null | undefined): string {
  if (!iso) return 'Never'
  const d = new Date(iso)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  const days = Math.floor(diff / 86400000)
  if (days === 0) return 'Today'
  if (days === 1) return 'Yesterday'
  if (days < 7) return `${days} days ago`
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function extractCommitments(parsed: Record<string, unknown> | null): string[] {
  if (!parsed) return []
  // Handle various parsed_result shapes
  if (Array.isArray(parsed)) return parsed.map(String)
  if ('commitments' in parsed && Array.isArray(parsed.commitments)) {
    return (parsed.commitments as Record<string, unknown>[]).map(
      c => (c.title as string) || (c.text as string) || (c.commitment_text as string) || JSON.stringify(c)
    )
  }
  if ('items' in parsed && Array.isArray(parsed.items)) {
    return (parsed.items as Record<string, unknown>[]).map(
      c => (c.title as string) || (c.text as string) || JSON.stringify(c)
    )
  }
  return []
}

// ─── Star Rating ─────────────────────────────────────────────────────────

function StarRating({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  return (
    <div className="flex items-center gap-1">
      {[1, 2, 3, 4, 5].map(n => (
        <button
          key={n}
          type="button"
          onClick={() => onChange(n)}
          className={`text-[20px] transition-colors ${n <= value ? 'text-[#f59e0b]' : 'text-[#d1d1cf]'}`}
        >
          ★
        </button>
      ))}
    </div>
  )
}

// ─── Radio Group ─────────────────────────────────────────────────────────

function RadioGroup<T extends string>({ options, value, onChange }: {
  options: { value: T; label: string }[]
  value: T | null
  onChange: (v: T) => void
}) {
  return (
    <div className="flex items-center gap-2">
      {options.map(opt => (
        <button
          key={opt.value}
          type="button"
          onClick={() => onChange(opt.value)}
          className={`px-3 py-1 rounded-md text-[13px] font-medium transition-colors border ${
            value === opt.value
              ? 'bg-[#191919] text-white border-[#191919]'
              : 'bg-white text-[#6b7280] border-[#e8e8e6] hover:border-[#d1d1cf]'
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  )
}

// ─── Signal Review ───────────────────────────────────────────────────────

function SignalReviewTab() {
  const queryClient = useQueryClient()
  const [currentIndex, setCurrentIndex] = useState(0)
  const [expanded, setExpanded] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Form state
  const [extractionCorrect, setExtractionCorrect] = useState<ExtractionCorrect | null>(null)
  const [rating, setRating] = useState(0)
  const [missed, setMissed] = useState('')
  const [falsePositives, setFalsePositives] = useState('')
  const [notes, setNotes] = useState('')

  const { data: signals, isLoading } = useQuery({
    queryKey: ['admin', 'signals'],
    queryFn: () => apiGet<SignalItem[]>('/api/v1/admin/review/signals?limit=20'),
    staleTime: 30_000,
  })

  const items = signals ?? []
  const current = items[currentIndex] ?? null

  function resetForm() {
    setExtractionCorrect(null)
    setRating(0)
    setMissed('')
    setFalsePositives('')
    setNotes('')
    setExpanded(false)
    setError(null)
  }

  async function handleSubmit() {
    if (!current || !extractionCorrect || rating === 0) return
    setSubmitting(true)
    setError(null)
    try {
      await apiPost(`/api/v1/admin/review/signals/${current.detection_audit_id}`, {
        extraction_correct: extractionCorrect === 'correct',
        rating,
        missed_commitments: missed || null,
        false_positives: falsePositives || null,
        notes: notes || null,
      })
      resetForm()
      if (currentIndex < items.length - 1) {
        setCurrentIndex(i => i + 1)
      } else {
        // Refetch to get more items
        queryClient.invalidateQueries({ queryKey: ['admin', 'signals'] })
        queryClient.invalidateQueries({ queryKey: ['admin', 'stats'] })
        setCurrentIndex(0)
      }
    } catch {
      setError('Failed to submit feedback')
    } finally {
      setSubmitting(false)
    }
  }

  // Keyboard shortcuts
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.target instanceof HTMLTextAreaElement || e.target instanceof HTMLInputElement) return
    if (!current) return
    switch (e.key) {
      case 'y': case 'Y': setExtractionCorrect('correct'); break
      case 'p': case 'P': setExtractionCorrect('partial'); break
      case 'n': case 'N': setExtractionCorrect('wrong'); break
      case '1': setRating(1); break
      case '2': setRating(2); break
      case '3': setRating(3); break
      case '4': setRating(4); break
      case '5': setRating(5); break
      case 'Enter':
        if (extractionCorrect && rating > 0) handleSubmit()
        break
    }
  }, [current, extractionCorrect, rating])

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [handleKeyDown])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="w-8 h-8 border-2 border-[#191919] border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (!current) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <div className="text-[#d1d1cf] mb-4">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="20 6 9 17 4 12" />
          </svg>
        </div>
        <div className="text-[14px] text-[#6b7280] mb-1.5">Signal review queue is empty.</div>
        <div className="text-[13px] text-[#9ca3af]">All detection audits have been reviewed.</div>
      </div>
    )
  }

  const commitments = extractCommitments(current.parsed_result)
  const displayContent = expanded ? current.full_content : current.content
  const canExpand = current.full_content.length > current.content.length

  return (
    <div className="max-w-[640px] mx-auto">
      {error && (
        <div className="mb-4 rounded-md bg-[#fee2e2] border border-[#fca5a5] px-4 py-3 text-[13px] text-[#991b1b] font-medium">
          {error}
        </div>
      )}

      <div className="text-[11px] text-[#9ca3af] mb-3">
        {currentIndex + 1} of {items.length} · <span className="text-[#6b7280]">Y</span>=Correct <span className="text-[#6b7280]">P</span>=Partial <span className="text-[#6b7280]">N</span>=Wrong <span className="text-[#6b7280]">1-5</span>=Rating <span className="text-[#6b7280]">Enter</span>=Submit
      </div>

      {/* Signal card */}
      <div className="bg-white rounded-lg border border-[#e8e8e6] overflow-hidden mb-4">
        <div className="px-5 py-4">
          <div className="flex items-center justify-between mb-3">
            <div className="text-[13px] font-medium text-[#191919]">
              {current.sender_name || current.sender_email || 'Unknown sender'}
            </div>
            <div className="text-[11px] text-[#9ca3af]">{formatDate(current.occurred_at)}</div>
          </div>

          <div className="text-[13px] text-[#4b5563] leading-relaxed whitespace-pre-wrap mb-3">
            {displayContent}
          </div>
          {canExpand && (
            <button
              type="button"
              onClick={() => setExpanded(!expanded)}
              className="text-[12px] text-[#2563eb] hover:text-[#1d4ed8] font-medium"
            >
              {expanded ? 'Show less' : 'Show more'}
            </button>
          )}

          <div className="mt-4 pt-3 border-t border-[#f0f0ef]">
            <div className="text-[11px] font-semibold text-[#6b7280] uppercase tracking-wide mb-2">Extracted commitments</div>
            {commitments.length > 0 ? (
              <ul className="space-y-1">
                {commitments.map((c, i) => (
                  <li key={i} className="flex items-start gap-2 text-[13px] text-[#191919]">
                    <span className="text-[#9ca3af] mt-0.5">•</span>
                    <span>{c}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-[12px] text-[#9ca3af] italic">
                {current.parsed_result === null
                  ? 'No extraction data — this item was processed before logging was enabled. Re-run seed pass to populate.'
                  : 'No commitments extracted from this item.'}
              </p>
            )}
          </div>

          {current.model && (
            <div className="mt-3 text-[11px] text-[#b0b0ae]">
              Model: {current.model} · Prompt: {current.prompt_version || 'unknown'}
            </div>
          )}
        </div>
      </div>

      {/* Feedback form */}
      <div className="bg-white rounded-lg border border-[#e8e8e6] overflow-hidden">
        <div className="px-5 py-4 space-y-4">
          <div>
            <label className="block text-[12px] font-semibold text-[#4b5563] mb-1.5">Extraction quality</label>
            <RadioGroup
              options={[
                { value: 'correct' as ExtractionCorrect, label: 'Correct' },
                { value: 'partial' as ExtractionCorrect, label: 'Partial' },
                { value: 'wrong' as ExtractionCorrect, label: 'Wrong' },
              ]}
              value={extractionCorrect}
              onChange={setExtractionCorrect}
            />
          </div>

          <div>
            <label className="block text-[12px] font-semibold text-[#4b5563] mb-1.5">Rating</label>
            <StarRating value={rating} onChange={setRating} />
          </div>

          <div>
            <label className="block text-[12px] font-semibold text-[#4b5563] mb-1.5">Missed commitments</label>
            <textarea
              value={missed}
              onChange={e => setMissed(e.target.value)}
              placeholder="Any commitments the system missed?"
              className="w-full rounded-md border border-[#e8e8e6] px-3 py-2 text-[13px] text-[#191919] placeholder-[#b0b0ae] focus:outline-none focus:border-[#191919] resize-none"
              rows={2}
            />
          </div>

          <div>
            <label className="block text-[12px] font-semibold text-[#4b5563] mb-1.5">False positives</label>
            <textarea
              value={falsePositives}
              onChange={e => setFalsePositives(e.target.value)}
              placeholder="Any extracted items that aren't real commitments?"
              className="w-full rounded-md border border-[#e8e8e6] px-3 py-2 text-[13px] text-[#191919] placeholder-[#b0b0ae] focus:outline-none focus:border-[#191919] resize-none"
              rows={2}
            />
          </div>

          <div>
            <label className="block text-[12px] font-semibold text-[#4b5563] mb-1.5">Notes</label>
            <textarea
              value={notes}
              onChange={e => setNotes(e.target.value)}
              placeholder="Additional observations..."
              className="w-full rounded-md border border-[#e8e8e6] px-3 py-2 text-[13px] text-[#191919] placeholder-[#b0b0ae] focus:outline-none focus:border-[#191919] resize-none"
              rows={2}
            />
          </div>

          <button
            type="button"
            onClick={handleSubmit}
            disabled={!extractionCorrect || rating === 0 || submitting}
            className="w-full bg-[#191919] text-white text-[13px] font-medium py-2 rounded-md hover:bg-[#333] transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {submitting ? 'Submitting…' : 'Submit & Next'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── Outcome Review ──────────────────────────────────────────────────────

function OutcomeReviewTab() {
  const queryClient = useQueryClient()
  const [currentIndex, setCurrentIndex] = useState(0)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Form state
  const [wasUseful, setWasUseful] = useState<WasUseful | null>(null)
  const [usefulnessRating, setUsefulnessRating] = useState(0)
  const [wasTimely, setWasTimely] = useState<'yes' | 'no' | null>(null)
  const [notes, setNotes] = useState('')

  const { data: outcomes, isLoading } = useQuery({
    queryKey: ['admin', 'outcomes'],
    queryFn: () => apiGet<OutcomeItem[]>('/api/v1/admin/review/outcomes?limit=20'),
    staleTime: 30_000,
  })

  const items = outcomes ?? []
  const current = items[currentIndex] ?? null

  function resetForm() {
    setWasUseful(null)
    setUsefulnessRating(0)
    setWasTimely(null)
    setNotes('')
    setError(null)
  }

  async function handleSubmit() {
    if (!current || !wasUseful || usefulnessRating === 0) return
    setSubmitting(true)
    setError(null)
    try {
      await apiPost(`/api/v1/admin/review/outcomes/${current.commitment_id}`, {
        was_useful: wasUseful === 'yes',
        usefulness_rating: usefulnessRating,
        was_timely: wasTimely === 'yes' ? true : wasTimely === 'no' ? false : null,
        notes: notes || null,
      })
      resetForm()
      if (currentIndex < items.length - 1) {
        setCurrentIndex(i => i + 1)
      } else {
        queryClient.invalidateQueries({ queryKey: ['admin', 'outcomes'] })
        queryClient.invalidateQueries({ queryKey: ['admin', 'stats'] })
        setCurrentIndex(0)
      }
    } catch {
      setError('Failed to submit feedback')
    } finally {
      setSubmitting(false)
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="w-8 h-8 border-2 border-[#191919] border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (!current) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <div className="text-[#d1d1cf] mb-4">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="20 6 9 17 4 12" />
          </svg>
        </div>
        <div className="text-[14px] text-[#6b7280] mb-1.5">Outcome review queue is empty.</div>
        <div className="text-[13px] text-[#9ca3af]">All surfaced commitments have been reviewed.</div>
      </div>
    )
  }

  return (
    <div className="max-w-[640px] mx-auto">
      {error && (
        <div className="mb-4 rounded-md bg-[#fee2e2] border border-[#fca5a5] px-4 py-3 text-[13px] text-[#991b1b] font-medium">
          {error}
        </div>
      )}

      <div className="text-[11px] text-[#9ca3af] mb-3">
        {currentIndex + 1} of {items.length}
      </div>

      {/* Outcome card */}
      <div className="bg-white rounded-lg border border-[#e8e8e6] overflow-hidden mb-4">
        <div className="px-5 py-4">
          <div className="text-[15px] font-semibold text-[#191919] mb-2">{current.title}</div>
          {current.commitment_text && (
            <div className="text-[13px] text-[#4b5563] leading-relaxed mb-3">{current.commitment_text}</div>
          )}
          <div className="flex items-center gap-2 text-[11px] text-[#9ca3af]">
            <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ${
              current.lifecycle_state === 'delivered' ? 'bg-[#f0fdf4] text-[#15803d]' :
              current.lifecycle_state === 'active' ? 'bg-[#eff6ff] text-[#1d4ed8]' :
              'bg-[#f9fafb] text-[#6b7280] border border-[#e8e8e6]'
            }`}>
              {current.lifecycle_state}
            </span>
            {current.source_context && <span>· {current.source_context}</span>}
          </div>
        </div>
      </div>

      {/* Feedback form */}
      <div className="bg-white rounded-lg border border-[#e8e8e6] overflow-hidden">
        <div className="px-5 py-4 space-y-4">
          <div>
            <label className="block text-[12px] font-semibold text-[#4b5563] mb-1.5">Was this useful?</label>
            <RadioGroup
              options={[
                { value: 'yes' as WasUseful, label: 'Yes' },
                { value: 'partial' as WasUseful, label: 'Partial' },
                { value: 'no' as WasUseful, label: 'No' },
              ]}
              value={wasUseful}
              onChange={setWasUseful}
            />
          </div>

          <div>
            <label className="block text-[12px] font-semibold text-[#4b5563] mb-1.5">Usefulness rating</label>
            <StarRating value={usefulnessRating} onChange={setUsefulnessRating} />
          </div>

          <div>
            <label className="block text-[12px] font-semibold text-[#4b5563] mb-1.5">Was it timely?</label>
            <RadioGroup
              options={[
                { value: 'yes' as const, label: 'Yes' },
                { value: 'no' as const, label: 'No' },
              ]}
              value={wasTimely}
              onChange={setWasTimely}
            />
          </div>

          <div>
            <label className="block text-[12px] font-semibold text-[#4b5563] mb-1.5">Notes</label>
            <textarea
              value={notes}
              onChange={e => setNotes(e.target.value)}
              placeholder="Additional observations..."
              className="w-full rounded-md border border-[#e8e8e6] px-3 py-2 text-[13px] text-[#191919] placeholder-[#b0b0ae] focus:outline-none focus:border-[#191919] resize-none"
              rows={2}
            />
          </div>

          <button
            type="button"
            onClick={handleSubmit}
            disabled={!wasUseful || usefulnessRating === 0 || submitting}
            className="w-full bg-[#191919] text-white text-[13px] font-medium py-2 rounded-md hover:bg-[#333] transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {submitting ? 'Submitting…' : 'Submit & Next'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── AdminScreen ─────────────────────────────────────────────────────────

export default function AdminScreen() {
  const { user, loading } = useAuth()
  const navigate = useNavigate()
  const [tab, setTab] = useState<AdminTab>('signals')

  const { data: stats } = useQuery({
    queryKey: ['admin', 'stats'],
    queryFn: () => apiGet<ReviewStats>('/api/v1/admin/review/stats'),
    refetchInterval: 60_000,
    staleTime: 30_000,
    enabled: user?.id === ADMIN_USER_ID,
  })

  useEffect(() => {
    if (!loading && user?.id !== ADMIN_USER_ID) {
      navigate('/', { replace: true })
    }
  }, [loading, user, navigate])

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="w-8 h-8 border-2 border-[#191919] border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (user?.id !== ADMIN_USER_ID) return null

  const tabs: { id: AdminTab; label: string }[] = [
    { id: 'signals', label: 'Signal Review' },
    { id: 'outcomes', label: 'Outcome Review' },
  ]
  const archActive = false // architecture tab is a separate route

  return (
    <div className="min-h-screen bg-[#f9f9f8]">
      {/* Header */}
      <div className="bg-white border-b border-[#e8e8e6] h-[52px] flex items-center px-4 md:px-6">
        <div className="flex items-center flex-shrink-0">
          <button onClick={() => navigate('/')} className="font-semibold text-[16px] text-[#191919] tracking-tight hover:text-[#6b7280] transition-colors">
            rippled
          </button>
          <span className="ml-2 text-[11px] text-[#9ca3af] bg-[#f0f0ef] rounded-full px-2 py-0.5 font-medium">Admin</span>
        </div>
        <div className="flex items-center gap-1 mx-3 md:mx-auto">
          {tabs.map(t =>
            tab === t.id ? (
              <button key={t.id} onClick={() => setTab(t.id)} className="bg-[#191919] text-white rounded-full px-3 md:px-4 py-1 text-[13px] font-medium">{t.label}</button>
            ) : (
              <button key={t.id} onClick={() => setTab(t.id)} className="text-[#6b7280] hover:text-[#191919] px-3 md:px-4 py-1 text-[13px] transition-colors">{t.label}</button>
            )
          )}
          <button
            onClick={() => navigate('/admin/architecture')}
            className="text-[#6b7280] hover:text-[#191919] px-3 md:px-4 py-1 text-[13px] transition-colors"
          >
            Architecture
          </button>
          <button
            onClick={() => navigate('/lab')}
            className="text-[#6b7280] hover:text-[#191919] px-3 md:px-4 py-1 text-[13px] transition-colors"
          >
            Signal Lab
          </button>
        </div>
        <div className="ml-auto flex-shrink-0" />
      </div>

      {/* Stats bar */}
      <div className="bg-[#fafaf9] border-b border-[#e8e8e6] h-[22px] flex items-center px-4 md:px-5">
        <div className="flex items-center gap-2 text-[11px] text-[#6b7280]">
          <span>{stats?.unreviewed_signals ?? '–'} unreviewed signals</span>
          <span className="w-px h-2.5 bg-[#e8e8e6]" />
          <span>{stats?.unreviewed_outcomes ?? '–'} unreviewed outcomes</span>
          <span className="w-px h-2.5 bg-[#e8e8e6]" />
          <span>Last reviewed: {formatRelativeDate(stats?.last_review_date)}</span>
        </div>
      </div>

      <main className="max-w-[1100px] mx-auto px-6 pt-6 pb-12">
        {tab === 'signals' ? <SignalReviewTab /> : <OutcomeReviewTab />}
      </main>
    </div>
  )
}
