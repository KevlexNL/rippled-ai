import { adminFetch } from '../lib/apiClient'

export interface TaskStatus {
  name: string
  last_run_at: string | null
  status: 'ok' | 'stale' | 'unknown'
}

export interface HealthCounts {
  commitments: number
  candidates: number
  events: number
  sources: number
  digests_sent: number
  surfaced_main: number
  surfaced_shortlist: number
}

export interface HealthResponse {
  tasks: TaskStatus[]
  counts: HealthCounts
  error_count_24h: number
}

export async function fetchHealth(): Promise<HealthResponse> {
  return adminFetch('/api/v1/admin/health') as Promise<HealthResponse>
}
