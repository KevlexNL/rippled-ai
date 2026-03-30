import { apiGet, apiPost } from '../lib/apiClient'

export interface SourceItemSummary {
  id: string
  source_type: string
  sender_name: string | null
  sender_email: string | null
  occurred_at: string | null
  content_preview: string | null
  status: 'unprocessed' | 'candidate_created' | 'processed_no_match'
}

export interface TraceStage {
  stage: string
  status: string
  data: Record<string, unknown>
}

export interface TraceResult {
  source_item_id: string
  verdict: string
  stages: TraceStage[]
}

export function listLabSourceItems(type?: string, limit = 20): Promise<SourceItemSummary[]> {
  const params = new URLSearchParams()
  if (type) params.set('type', type)
  params.set('limit', String(limit))
  return apiGet<SourceItemSummary[]>(`/api/v1/lab/source-items?${params}`)
}

export function runTrace(sourceItemIds: string[]): Promise<TraceResult[]> {
  return apiPost<TraceResult[]>('/api/v1/lab/trace', { source_item_ids: sourceItemIds })
}
