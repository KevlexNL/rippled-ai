import { apiGet, apiPatch } from '../lib/apiClient'

export interface UserSettingsRead {
  digest_enabled: boolean
  digest_to_email: string | null
  google_connected: boolean
}

export interface UserSettingsPatch {
  digest_enabled?: boolean | null
  digest_to_email?: string | null
}

export const getUserSettings = () =>
  apiGet<UserSettingsRead>('/api/v1/user/settings')

export const patchUserSettings = (body: UserSettingsPatch) =>
  apiPatch<UserSettingsRead>('/api/v1/user/settings', body)
