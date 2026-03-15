import { apiGet, apiPatch, apiPost } from '../lib/apiClient'
import type {
  CommitmentRead,
  CommitmentSignalRead,
  CommitmentAmbiguityRead,
  CommitmentCreate,
} from '../types'

export const getCommitments = (params?: { lifecycle_state?: string; limit?: number }) => {
  const qs = new URLSearchParams()
  if (params?.lifecycle_state) qs.set('lifecycle_state', params.lifecycle_state)
  if (params?.limit) qs.set('limit', String(params.limit))
  return apiGet<CommitmentRead[]>(`/api/v1/commitments?${qs}`)
}

export const getCommitment = (id: string) =>
  apiGet<CommitmentRead>(`/api/v1/commitments/${id}`)

export const patchCommitment = (
  id: string,
  body: Partial<{
    lifecycle_state: string
    resolved_owner: string
    resolved_deadline: string
  }>
) => apiPatch<CommitmentRead>(`/api/v1/commitments/${id}`, body)

export const postCommitment = (body: CommitmentCreate) =>
  apiPost<CommitmentRead>('/api/v1/commitments', body)

export const getSignals = (id: string) =>
  apiGet<CommitmentSignalRead[]>(`/api/v1/commitments/${id}/signals?limit=50`)

export const getAmbiguities = (id: string) =>
  apiGet<CommitmentAmbiguityRead[]>(`/api/v1/commitments/${id}/ambiguities?limit=50`)

export const patchDeliveryState = (id: string, state: string) =>
  apiPatch<CommitmentRead>(`/api/v1/commitments/${id}/delivery-state`, { state })
