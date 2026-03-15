import { apiGet, apiPost } from '../lib/apiClient'

export interface ClarificationRead {
  id: string
  commitment_id: string
  suggested_clarification_prompt: string | null
  suggested_values: Record<string, unknown>
  resolved_at: string | null
}

export interface ClarificationRespondRead {
  id: string
  resolved_at: string
}

export const getClarifications = (commitmentId: string) =>
  apiGet<ClarificationRead[]>(`/api/v1/clarifications?commitment_id=${commitmentId}`)

export const respondToClarification = (id: string, answer: string) =>
  apiPost<ClarificationRespondRead>(`/api/v1/clarifications/${id}/respond`, { answer })
