import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { listLabSourceItems, runTrace } from '../api/lab'
import type { SourceItemSummary, TraceResult, TraceStage } from '../api/lab'

// ─── Helpers ────────────────────────────────────────────────────────────

function formatDate(iso: string | null | undefined): string {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
}

const STATUS_BADGE: Record<string, { bg: string; text: string; label: string }> = {
  unprocessed: { bg: 'bg-[#f9fafb]', text: 'text-[#6b7280]', label: 'Unprocessed' },
  candidate_created: { bg: 'bg-[#f0fdf4]', text: 'text-[#15803d]', label: 'Candidate' },
  processed_no_match: { bg: 'bg-[#fef3c7]', text: 'text-[#92400e]', label: 'No match' },
}

const VERDICT_STYLE: Record<string, { bg: string; text: string }> = {
  commitment_created: { bg: 'bg-[#f0fdf4]', text: 'text-[#15803d]' },
  candidate_promoted: { bg: 'bg-[#f0fdf4]', text: 'text-[#15803d]' },
  candidate_pending: { bg: 'bg-[#fef3c7]', text: 'text-[#92400e]' },
  rejected_as_noise: { bg: 'bg-[#fee2e2]', text: 'text-[#991b1b]' },
  no_candidates_created: { bg: 'bg-[#fee2e2]', text: 'text-[#991b1b]' },
  not_processed: { bg: 'bg-[#f9fafb]', text: 'text-[#6b7280]' },
  unknown: { bg: 'bg-[#f9fafb]', text: 'text-[#6b7280]' },
}

const STAGE_STATUS_COLOR: Record<string, string> = {
  loaded: 'text-[#15803d]',
  complete: 'text-[#15803d]',
  matched: 'text-[#15803d]',
  found: 'text-[#15803d]',
  commitment_created: 'text-[#15803d]',
  promoted: 'text-[#15803d]',
  no_match: 'text-[#92400e]',
  no_audit_records: 'text-[#92400e]',
  no_candidates: 'text-[#991b1b]',
  not_promoted: 'text-[#991b1b]',
  no_commitments: 'text-[#6b7280]',
  no_clarification_records: 'text-[#6b7280]',
  no_commitment: 'text-[#991b1b]',
}

const STAGE_LABELS: Record<string, string> = {
  raw: 'Raw Content',
  normalization: 'Normalization',
  pattern_detection: 'Pattern Detection',
  llm_detection: 'LLM Detection',
  extraction: 'Signal Extraction',
  candidate_decision: 'Candidate Decision',
  clarification: 'Clarification',
  final_state: 'Final State',
}

// ─── Stage Detail Renderers ─────────────────────────────────────────────

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function d(val: unknown): string { return val == null ? '' : String(val) }

function StageDetail({ stage }: { stage: TraceStage }) {
  const data = stage.data as Record<string, unknown>

  if (stage.stage === 'raw') {
    return (
      <div className="space-y-1 text-[12px]">
        <div><span className="text-[#6b7280]">Source:</span> {d(data.source_type)} &middot; <span className="text-[#6b7280]">Sender:</span> {d(data.sender_name || data.sender_email || '?')}</div>
        <div><span className="text-[#6b7280]">Direction:</span> {d(data.direction)} &middot; <span className="text-[#6b7280]">Date:</span> {formatDate(data.occurred_at as string)}</div>
        <div><span className="text-[#6b7280]">Content:</span> {d(data.content_length)} chars &middot; <span className="text-[#6b7280]">External:</span> {d(data.is_external)}</div>
        {data.content_preview ? (
          <div className="mt-2 p-2 bg-[#f9fafb] rounded text-[11px] text-[#4b5563] whitespace-pre-wrap max-h-[120px] overflow-y-auto">
            {d(data.content_preview)}
          </div>
        ) : null}
      </div>
    )
  }

  if (stage.stage === 'normalization') {
    const spans = (data.suppressed_spans || []) as { pattern: string; matched_text: string }[]
    return (
      <div className="space-y-1 text-[12px]">
        <div><span className="text-[#6b7280]">Suppression patterns:</span> {d(data.suppression_patterns_applied)} &middot; <span className="text-[#6b7280]">Spans stripped:</span> {spans.length}</div>
        <div><span className="text-[#6b7280]">Length:</span> {d(data.raw_length)} → {d(data.normalized_length)} chars</div>
        {spans.length > 0 && (
          <div className="mt-1 space-y-0.5">
            {spans.slice(0, 5).map((s, i) => (
              <div key={i} className="text-[11px] text-[#9ca3af]">
                <span className="text-[#6b7280]">[{s.pattern}]</span> {s.matched_text.slice(0, 80)}
              </div>
            ))}
          </div>
        )}
      </div>
    )
  }

  if (stage.stage === 'pattern_detection') {
    const matches = (data.matches || []) as { pattern_name: string; trigger_class: string; base_confidence: number; matched_text: string }[]
    return (
      <div className="space-y-1 text-[12px]">
        <div><span className="text-[#6b7280]">Patterns checked:</span> {d(data.patterns_checked)} &middot; <span className="text-[#6b7280]">Matches:</span> {d(data.matches_found)}</div>
        {matches.map((m, i) => (
          <div key={i} className="flex items-start gap-2 text-[11px] mt-1 p-1.5 bg-[#f9fafb] rounded">
            <span className="font-medium text-[#2563eb] whitespace-nowrap">{m.pattern_name}</span>
            <span className="text-[#6b7280]">{m.trigger_class}</span>
            <span className="text-[#6b7280]">conf={m.base_confidence.toFixed(2)}</span>
            <span className="text-[#4b5563] truncate">{m.matched_text.slice(0, 100)}</span>
          </div>
        ))}
      </div>
    )
  }

  if (stage.stage === 'llm_detection') {
    const audits = (data.audits || []) as Record<string, unknown>[]
    return (
      <div className="space-y-2 text-[12px]">
        {audits.map((a, i) => (
          <div key={i} className="p-2 bg-[#f9fafb] rounded space-y-1">
            <div>
              <span className="text-[#6b7280]">Tier:</span> {a.tier_used as string} &middot;
              <span className="text-[#6b7280]"> Model:</span> {(a.model || '—') as string} &middot;
              <span className="text-[#6b7280]"> Prompt:</span> {(a.prompt_version || '—') as string} &middot;
              <span className="text-[#6b7280]"> Cost:</span> ${Number(a.cost_estimate || 0).toFixed(4)}
            </div>
            {a.raw_prompt ? (
              <details className="text-[11px]">
                <summary className="text-[#2563eb] cursor-pointer">Prompt</summary>
                <pre className="mt-1 p-2 bg-white rounded border border-[#e8e8e6] text-[10px] whitespace-pre-wrap max-h-[200px] overflow-y-auto">{a.raw_prompt as string}</pre>
              </details>
            ) : null}
            {a.raw_response ? (
              <details className="text-[11px]">
                <summary className="text-[#2563eb] cursor-pointer">Response</summary>
                <pre className="mt-1 p-2 bg-white rounded border border-[#e8e8e6] text-[10px] whitespace-pre-wrap max-h-[200px] overflow-y-auto">{a.raw_response as string}</pre>
              </details>
            ) : null}
            {a.error_detail ? (
              <div className="text-[#991b1b] text-[11px]">Error: {a.error_detail as string}</div>
            ) : null}
          </div>
        ))}
        {audits.length === 0 && <div className="text-[#9ca3af] text-[11px]">No audit records found for this item.</div>}
      </div>
    )
  }

  if (stage.stage === 'extraction') {
    const candidates = (data.candidates || []) as Record<string, unknown>[]
    return (
      <div className="space-y-2 text-[12px]">
        <div><span className="text-[#6b7280]">Candidates:</span> {data.candidate_count as number || 0}</div>
        {candidates.map((c, i) => (
          <div key={i} className="p-2 bg-[#f9fafb] rounded space-y-0.5 text-[11px]">
            <div><span className="text-[#6b7280]">Trigger:</span> {c.trigger_class as string} &middot; <span className="text-[#6b7280]">Conf:</span> {String(c.confidence_score)} &middot; <span className="text-[#6b7280]">Method:</span> {(c.detection_method || '—') as string}</div>
            {c.raw_text ? <div className="text-[#4b5563] italic">&quot;{(c.raw_text as string).slice(0, 150)}&quot;</div> : null}
          </div>
        ))}
      </div>
    )
  }

  if (stage.stage === 'candidate_decision') {
    const decisions = (data.decisions || []) as { candidate_id: string; decision: string; reason: string; confidence: number }[]
    return (
      <div className="space-y-1 text-[12px]">
        {decisions.map((d, i) => {
          const color = d.decision === 'promoted' ? 'text-[#15803d]' : d.decision === 'discarded' ? 'text-[#991b1b]' : 'text-[#92400e]'
          return (
            <div key={i} className="flex items-center gap-2">
              <span className="text-[#9ca3af] text-[11px]">{d.candidate_id.slice(0, 8)}</span>
              <span className={`font-medium ${color}`}>{d.decision.toUpperCase()}</span>
              <span className="text-[#6b7280] text-[11px]">({d.reason})</span>
            </div>
          )
        })}
      </div>
    )
  }

  if (stage.stage === 'clarification') {
    const clarifications = (data.clarifications || []) as Record<string, unknown>[]
    return (
      <div className="space-y-2 text-[12px]">
        {clarifications.map((cl, i) => (
          <div key={i} className="p-2 bg-[#f9fafb] rounded space-y-0.5 text-[11px]">
            <div><span className="text-[#6b7280]">Issues:</span> {((cl.issue_types || []) as string[]).join(', ')}</div>
            <div><span className="text-[#6b7280]">Severity:</span> {cl.issue_severity as string} &middot; <span className="text-[#6b7280]">Rec:</span> {cl.surface_recommendation as string}</div>
          </div>
        ))}
        {clarifications.length === 0 && <div className="text-[#9ca3af] text-[11px]">No clarification records.</div>}
      </div>
    )
  }

  if (stage.stage === 'final_state') {
    const commitments = (data.commitments || []) as Record<string, unknown>[]
    return (
      <div className="space-y-2 text-[12px]">
        {commitments.map((cm, i) => (
          <div key={i} className="p-2 bg-[#f0fdf4] rounded space-y-0.5 text-[11px]">
            <div className="font-medium text-[#15803d]">{cm.title as string}</div>
            <div><span className="text-[#6b7280]">Type:</span> {cm.commitment_type as string} &middot; <span className="text-[#6b7280]">State:</span> {cm.lifecycle_state as string} &middot; <span className="text-[#6b7280]">Priority:</span> {cm.priority_class as string}</div>
            <div><span className="text-[#6b7280]">Owner:</span> {(cm.resolved_owner || '?') as string} &middot; <span className="text-[#6b7280]">Surfaced:</span> {String(cm.is_surfaced)}</div>
          </div>
        ))}
        {commitments.length === 0 && <div className="text-[#9ca3af] text-[11px]">No commitment created.</div>}
      </div>
    )
  }

  // Fallback: dump as JSON
  return (
    <pre className="text-[11px] text-[#6b7280] whitespace-pre-wrap max-h-[200px] overflow-y-auto">
      {JSON.stringify(data, null, 2)}
    </pre>
  )
}

// ─── Stage Accordion ────────────────────────────────────────────────────

function StageAccordion({ stage }: { stage: TraceStage }) {
  const [open, setOpen] = useState(false)
  const label = STAGE_LABELS[stage.stage] || stage.stage
  const statusColor = STAGE_STATUS_COLOR[stage.status] || 'text-[#6b7280]'

  return (
    <div className="border border-[#e8e8e6] rounded-lg overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-2.5 bg-white hover:bg-[#f9fafb] transition-colors text-left"
      >
        <div className="flex items-center gap-2">
          <span className="text-[13px] font-medium text-[#191919]">{label}</span>
          <span className={`text-[11px] font-medium ${statusColor}`}>{stage.status}</span>
        </div>
        <svg className={`w-4 h-4 text-[#9ca3af] transition-transform ${open ? 'rotate-180' : ''}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M6 9l6 6 6-6" /></svg>
      </button>
      {open && (
        <div className="px-4 py-3 border-t border-[#e8e8e6] bg-white">
          <StageDetail stage={stage} />
        </div>
      )}
    </div>
  )
}

// ─── Trace Result Panel ─────────────────────────────────────────────────

function TracePanel({ trace }: { trace: TraceResult }) {
  const verdictStyle = VERDICT_STYLE[trace.verdict] || VERDICT_STYLE.unknown
  const rawStage = trace.stages.find(s => s.stage === 'raw')
  const sender = (rawStage?.data?.sender_name || rawStage?.data?.sender_email || 'Unknown') as string

  return (
    <div className="mb-6">
      <div className="flex items-center gap-3 mb-3">
        <span className="text-[13px] font-medium text-[#191919]">{trace.source_item_id.slice(0, 8)}…</span>
        <span className="text-[11px] text-[#6b7280]">{sender}</span>
        <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ${verdictStyle.bg} ${verdictStyle.text}`}>
          {trace.verdict.replace(/_/g, ' ')}
        </span>
      </div>
      <div className="space-y-1.5">
        {trace.stages.map(stage => (
          <StageAccordion key={stage.stage} stage={stage} />
        ))}
      </div>
    </div>
  )
}

// ─── Source Type Tabs ────────────────────────────────────────────────────

type SourceTab = 'email' | 'slack' | 'meeting'
const SOURCE_TABS: { id: SourceTab; label: string }[] = [
  { id: 'email', label: 'Email' },
  { id: 'slack', label: 'Slack' },
  { id: 'meeting', label: 'Meeting' },
]

// ─── Main Screen ────────────────────────────────────────────────────────

export default function SignalLabScreen() {
  const navigate = useNavigate()
  const [sourceTab, setSourceTab] = useState<SourceTab>('email')
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [traces, setTraces] = useState<TraceResult[]>([])

  const { data: items, isLoading } = useQuery({
    queryKey: ['lab', 'source-items', sourceTab],
    queryFn: () => listLabSourceItems(sourceTab, 30),
    staleTime: 30_000,
  })

  const traceMutation = useMutation({
    mutationFn: (ids: string[]) => runTrace(ids),
    onSuccess: (data) => setTraces(data),
  })

  function toggleItem(id: string) {
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else if (next.size < 5) next.add(id)
      return next
    })
  }

  function handleRunTrace() {
    if (selected.size === 0) return
    traceMutation.mutate(Array.from(selected))
  }

  function handleTabChange(tab: SourceTab) {
    setSourceTab(tab)
    setSelected(new Set())
    setTraces([])
  }

  return (
    <div className="min-h-screen bg-[#f9f9f8]">
      {/* Header */}
      <div className="bg-white border-b border-[#e8e8e6] h-[52px] flex items-center px-4 md:px-6">
        <button onClick={() => navigate('/')} className="font-semibold text-[16px] text-[#191919] tracking-tight hover:text-[#6b7280] transition-colors">
          rippled
        </button>
        <span className="ml-2 text-[11px] text-[#9ca3af] bg-[#f0f0ef] rounded-full px-2 py-0.5 font-medium">Signal Lab</span>
        <div className="ml-auto">
          <button onClick={() => navigate('/admin')} className="text-[13px] text-[#6b7280] hover:text-[#191919] transition-colors">
            Admin
          </button>
        </div>
      </div>

      <div className="max-w-[1400px] mx-auto px-4 md:px-6 py-6">
        <div className="flex flex-col lg:flex-row gap-6">
          {/* Left panel — Sample picker */}
          <div className="w-full lg:w-[420px] flex-shrink-0">
            <div className="bg-white rounded-lg border border-[#e8e8e6] overflow-hidden">
              {/* Source type tabs */}
              <div className="flex border-b border-[#e8e8e6]">
                {SOURCE_TABS.map(t => (
                  <button
                    key={t.id}
                    onClick={() => handleTabChange(t.id)}
                    className={`flex-1 py-2.5 text-[13px] font-medium transition-colors ${
                      sourceTab === t.id
                        ? 'text-[#191919] border-b-2 border-[#191919]'
                        : 'text-[#6b7280] hover:text-[#191919]'
                    }`}
                  >
                    {t.label}
                  </button>
                ))}
              </div>

              {/* Item list */}
              <div className="max-h-[calc(100vh-220px)] overflow-y-auto">
                {isLoading ? (
                  <div className="flex items-center justify-center py-12">
                    <div className="w-6 h-6 border-2 border-[#191919] border-t-transparent rounded-full animate-spin" />
                  </div>
                ) : !items?.length ? (
                  <div className="py-12 text-center text-[13px] text-[#9ca3af]">No {sourceTab} items found.</div>
                ) : (
                  items.map(item => {
                    const isSelected = selected.has(item.id)
                    const badge = STATUS_BADGE[item.status] || STATUS_BADGE.unprocessed
                    return (
                      <button
                        key={item.id}
                        type="button"
                        onClick={() => toggleItem(item.id)}
                        className={`w-full text-left px-4 py-3 border-b border-[#f0f0ef] transition-colors ${
                          isSelected ? 'bg-[#f0f4ff]' : 'hover:bg-[#f9fafb]'
                        }`}
                      >
                        <div className="flex items-start gap-2.5">
                          <div className={`mt-0.5 w-4 h-4 rounded border flex items-center justify-center flex-shrink-0 ${
                            isSelected ? 'bg-[#191919] border-[#191919]' : 'border-[#d1d1cf]'
                          }`}>
                            {isSelected && (
                              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3"><polyline points="20 6 9 17 4 12" /></svg>
                            )}
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-0.5">
                              <span className="text-[13px] font-medium text-[#191919] truncate">
                                {item.sender_name || item.sender_email || 'Unknown'}
                              </span>
                              <span className={`inline-flex items-center rounded-full px-1.5 py-0 text-[10px] font-medium ${badge.bg} ${badge.text} border border-[#e8e8e6]`}>
                                {badge.label}
                              </span>
                            </div>
                            <div className="text-[11px] text-[#9ca3af] mb-1">{formatDate(item.occurred_at)}</div>
                            <div className="text-[12px] text-[#6b7280] line-clamp-2">{item.content_preview}</div>
                          </div>
                        </div>
                      </button>
                    )
                  })
                )}
              </div>

              {/* Run trace button */}
              <div className="px-4 py-3 border-t border-[#e8e8e6] bg-[#f9fafb]">
                <button
                  type="button"
                  onClick={handleRunTrace}
                  disabled={selected.size === 0 || traceMutation.isPending}
                  className="w-full bg-[#191919] text-white text-[13px] font-medium py-2 rounded-md hover:bg-[#333] transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {traceMutation.isPending
                    ? 'Tracing…'
                    : `Run Trace (${selected.size} item${selected.size !== 1 ? 's' : ''})`}
                </button>
                <div className="text-[11px] text-[#9ca3af] mt-1.5 text-center">Select 1–5 items, then run trace</div>
              </div>
            </div>
          </div>

          {/* Right panel — Trace output */}
          <div className="flex-1 min-w-0">
            {traceMutation.isError && (
              <div className="mb-4 rounded-md bg-[#fee2e2] border border-[#fca5a5] px-4 py-3 text-[13px] text-[#991b1b] font-medium">
                Failed to run trace. Check that the API is running.
              </div>
            )}

            {traces.length === 0 && !traceMutation.isPending ? (
              <div className="flex flex-col items-center justify-center py-20 text-center">
                <div className="text-[#d1d1cf] mb-4">
                  <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <path d="M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
                  </svg>
                </div>
                <div className="text-[14px] text-[#6b7280] mb-1">Select items and run a trace</div>
                <div className="text-[12px] text-[#9ca3af]">The trace will show each pipeline stage for the selected source items.</div>
              </div>
            ) : traceMutation.isPending ? (
              <div className="flex items-center justify-center py-20">
                <div className="w-8 h-8 border-2 border-[#191919] border-t-transparent rounded-full animate-spin" />
              </div>
            ) : (
              <div>
                <div className="mb-4 text-[13px] text-[#6b7280]">
                  Showing {traces.length} trace{traces.length !== 1 ? 's' : ''}
                </div>
                {traces.map(trace => (
                  <TracePanel key={trace.source_item_id} trace={trace} />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
