import { adminFetch } from '../lib/apiClient'

export interface SurfacingAuditRow {
  id: number
  commitment_id: string
  commitment_title_snippet: string
  old_surfaced_as: string | null
  new_surfaced_as: string | null
  priority_score: number | null
  reason: string | null
  created_at: string
}

export interface SurfacingAuditResponse {
  items: SurfacingAuditRow[]
  total: number
}

export interface SurfacingFilters {
  commitment_id?: string
  created_after?: string
  old_surfaced_as?: string
  new_surfaced_as?: string
  limit?: number
  offset?: number
}

export async function fetchSurfacingAudit(filters: SurfacingFilters = {}): Promise<SurfacingAuditResponse> {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([k, v]) => { if (v !== undefined && v !== '') params.set(k, String(v)) })
  const qs = params.toString()
  return adminFetch(`/api/v1/admin/surfacing-audit${qs ? '?' + qs : ''}`) as Promise<SurfacingAuditResponse>
}
