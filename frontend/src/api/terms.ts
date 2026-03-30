import { apiGet, apiPost, apiPatch, apiDelete } from '../lib/apiClient'

export interface AliasRead {
  id: string
  alias: string
  source: string | null
  created_at: string
}

export interface CommonTermRead {
  id: string
  user_id: string
  canonical_term: string
  context: string | null
  aliases: AliasRead[]
  created_at: string
  updated_at: string
}

export const listTerms = () =>
  apiGet<CommonTermRead[]>('/api/v1/identity/terms')

export const createTerm = (body: {
  canonical_term: string
  context?: string | null
  aliases?: string[]
}) => apiPost<CommonTermRead>('/api/v1/identity/terms', body)

export const updateTerm = (id: string, body: {
  canonical_term?: string | null
  context?: string | null
}) => apiPatch<CommonTermRead>(`/api/v1/identity/terms/${id}`, body)

export const deleteTerm = (id: string) =>
  apiDelete(`/api/v1/identity/terms/${id}`)

export const addAlias = (termId: string, alias: string) =>
  apiPost<AliasRead>(`/api/v1/identity/terms/${termId}/aliases`, { alias })

export const deleteAlias = (termId: string, aliasId: string) =>
  apiDelete(`/api/v1/identity/terms/${termId}/aliases/${aliasId}`)
