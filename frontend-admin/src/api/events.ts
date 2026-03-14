import { adminFetch } from '../lib/apiClient'

export interface EventRow {
  id: string
  title: string
  event_type: string
  status: string
  starts_at: string
  ends_at: string | null
  linked_commitment_count: number
}

export interface EventsResponse {
  items: EventRow[]
  total: number
}

export interface EventFilters {
  event_type?: string
  status?: string
  starts_after?: string
  starts_before?: string
  limit?: number
  offset?: number
}

export async function fetchEvents(filters: EventFilters = {}): Promise<EventsResponse> {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([k, v]) => { if (v !== undefined && v !== '') params.set(k, String(v)) })
  const qs = params.toString()
  return adminFetch(`/api/v1/admin/events${qs ? '?' + qs : ''}`) as Promise<EventsResponse>
}

export async function fetchEvent(id: string): Promise<unknown> {
  return adminFetch(`/api/v1/admin/events/${id}`)
}
