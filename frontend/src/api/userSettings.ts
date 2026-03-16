import { apiGet, apiPatch } from '../lib/apiClient'

export interface UserSettingsRead {
  digest_enabled: boolean
  digest_to_email: string | null
  google_connected: boolean
  anthropic_key_connected: boolean
  openai_key_connected: boolean
}

export interface UserSettingsPatch {
  digest_enabled?: boolean | null
  digest_to_email?: string | null
  anthropic_api_key?: string | null
  openai_api_key?: string | null
}

export const getUserSettings = () =>
  apiGet<UserSettingsRead>('/api/v1/user/settings')

export const patchUserSettings = (body: UserSettingsPatch) =>
  apiPatch<UserSettingsRead>('/api/v1/user/settings', body)
