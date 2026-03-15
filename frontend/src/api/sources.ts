import { apiGet, apiDelete } from '../lib/apiClient'

export interface SourceRead {
  id: string
  user_id: string
  source_type: 'meeting' | 'slack' | 'email'
  provider_account_id: string | null
  display_name: string | null
  is_active: boolean
  has_credentials: boolean
  created_at: string
  updated_at: string
  metadata_?: Record<string, unknown>
}

export const listSources = () =>
  apiGet<SourceRead[]>('/api/v1/sources?limit=50')

export const deleteSource = (id: string) =>
  apiDelete(`/api/v1/sources/${id}`)
