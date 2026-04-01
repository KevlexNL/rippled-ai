import { apiGet, apiPatch } from '../lib/apiClient'

export interface ObservationWindowConfig {
  slack: number
  email_internal: number
  email_external: number
  meeting_internal: number
  meeting_external: number
}

export interface AutoCloseConfig {
  internal_hours: number
  external_hours: number
  big_promise_hours: number
  small_commitment_hours: number
}

export interface UserSettingsRead {
  digest_enabled: boolean
  digest_to_email: string | null
  google_connected: boolean
  anthropic_key_connected: boolean
  openai_key_connected: boolean
  observation_window_config: ObservationWindowConfig
  auto_close_config: AutoCloseConfig
}

export interface UserSettingsPatch {
  digest_enabled?: boolean | null
  digest_to_email?: string | null
  anthropic_api_key?: string | null
  openai_api_key?: string | null
  observation_window_config?: Partial<ObservationWindowConfig> | null
  auto_close_config?: Partial<AutoCloseConfig> | null
}

export const getUserSettings = () =>
  apiGet<UserSettingsRead>('/api/v1/user/settings')

export const patchUserSettings = (body: UserSettingsPatch) =>
  apiPatch<UserSettingsRead>('/api/v1/user/settings', body)
