import { apiGet } from '../lib/apiClient'

export interface EventRead {
  id: string
  external_id: string | null
  title: string
  description: string | null
  starts_at: string
  ends_at: string | null
  event_type: string
  status: string
  is_recurring: boolean
  location: string | null
  attendees: unknown[] | null
  linked_commitment_count: number
  created_at: string
  updated_at: string
}

export const getUpcomingEvents = () =>
  apiGet<EventRead[]>('/api/v1/events?limit=20')
