import { apiGet, apiPost, apiDelete } from '../lib/apiClient'

export interface IdentityProfileRead {
  id: string
  user_id: string
  identity_type: string
  identity_value: string
  source: string | null
  confirmed: boolean
  created_at: string
}

export interface BackfillResult {
  updated: number
}

export const getIdentityProfile = () =>
  apiGet<IdentityProfileRead[]>('/api/v1/identity/profile')

export const seedIdentities = () =>
  apiPost<IdentityProfileRead[]>('/api/v1/identity/seed', {})

export const confirmIdentities = (confirmIds: string[], rejectIds: string[]) =>
  apiPost<IdentityProfileRead[]>('/api/v1/identity/confirm', {
    confirm_ids: confirmIds,
    reject_ids: rejectIds,
  })

export const addManualIdentity = (identityType: string, identityValue: string) =>
  apiPost<IdentityProfileRead>('/api/v1/identity/manual', {
    identity_type: identityType,
    identity_value: identityValue,
  })

export const deleteIdentity = (id: string) =>
  apiDelete(`/api/v1/identity/${id}`)

export const runBackfill = () =>
  apiPost<BackfillResult>('/api/v1/identity/backfill', {})

export interface IdentityStatus {
  has_confirmed_identities: boolean
  confirmed_count: number
}

export const getIdentityStatus = () =>
  apiGet<IdentityStatus>('/api/v1/identity/status')
