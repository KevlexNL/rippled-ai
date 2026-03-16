import { apiGet } from '../lib/apiClient'

export interface StatsRead {
  meetings_analyzed: number
  messages_processed: number
  emails_captured: number
  commitments_detected: number
  sources_connected: number
  people_identified: number
}

export const getStats = () =>
  apiGet<StatsRead>('/api/v1/stats')
