const STORAGE_KEY = 'rippled_admin_key'

export const getAdminKey = (): string => localStorage.getItem(STORAGE_KEY) ?? ''
export const setAdminKey = (key: string): void => localStorage.setItem(STORAGE_KEY, key)
export const clearAdminKey = (): void => localStorage.removeItem(STORAGE_KEY)
