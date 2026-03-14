import { adminFetch } from '../lib/apiClient'

export interface CandidateRow {
  id: string
  raw_text_snippet: string | null
  trigger_class: string | null
  model_classification: string | null
  model_confidence: number | null
  was_promoted: boolean
  was_discarded: boolean
  source_type: string | null
  created_at: string
}

export interface CandidatesResponse {
  items: CandidateRow[]
  total: number
}

export interface CandidateFilters {
  trigger_class?: string
  model_classification?: string
  created_after?: string
  limit?: number
  offset?: number
}

export async function fetchCandidates(filters: CandidateFilters = {}): Promise<CandidatesResponse> {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([k, v]) => { if (v !== undefined && v !== '') params.set(k, String(v)) })
  const qs = params.toString()
  return adminFetch(`/api/v1/admin/candidates${qs ? '?' + qs : ''}`) as Promise<CandidatesResponse>
}

export async function fetchCandidate(id: string): Promise<unknown> {
  return adminFetch(`/api/v1/admin/candidates/${id}`)
}
