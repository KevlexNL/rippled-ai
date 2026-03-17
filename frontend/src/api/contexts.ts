import { apiGet, apiPost } from '../lib/apiClient'

export interface CommitmentContextRead {
  id: string
  user_id: string
  name: string
  summary: string | null
  commitment_count: number
  created_at: string
  updated_at: string
}

export interface CommitmentContextCreate {
  name: string
  summary?: string | null
}

export const getContexts = () =>
  apiGet<CommitmentContextRead[]>('/api/v1/contexts')

export const createContext = (body: CommitmentContextCreate) =>
  apiPost<CommitmentContextRead>('/api/v1/contexts', body)
