import { adminFetch } from '../lib/apiClient'

export interface CommitmentRow {
  id: string
  title: string
  description: string | null
  lifecycle_state: string
  surfaced_as: string | null
  priority_score: number | null
  counterparty_type: string | null
  delivery_state: string | null
  resolved_deadline: string | null
  created_at: string
  updated_at: string
}

export interface CommitmentsResponse {
  items: CommitmentRow[]
  total: number
}

export interface CommitmentFilters {
  lifecycle_state?: string
  surfaced_as?: string
  delivery_state?: string
  counterparty_type?: string
  created_after?: string
  created_before?: string
  sort?: string
  limit?: number
  offset?: number
}

export async function fetchCommitments(filters: CommitmentFilters = {}): Promise<CommitmentsResponse> {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([k, v]) => { if (v !== undefined && v !== '') params.set(k, String(v)) })
  const qs = params.toString()
  return adminFetch(`/api/v1/admin/commitments${qs ? '?' + qs : ''}`) as Promise<CommitmentsResponse>
}

export async function fetchCommitment(id: string): Promise<unknown> {
  return adminFetch(`/api/v1/admin/commitments/${id}`)
}

export async function overrideCommitmentState(id: string, body: { lifecycle_state?: string; delivery_state?: string; reason: string }): Promise<CommitmentRow> {
  return adminFetch(`/api/v1/admin/commitments/${id}/state`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  }) as Promise<CommitmentRow>
}
