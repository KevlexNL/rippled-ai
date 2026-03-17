import { getAdminKey } from './auth'

const BASE_URL = (import.meta.env.VITE_API_URL as string | undefined) ?? ''

export async function adminFetch(path: string, options: RequestInit = {}): Promise<unknown> {
  const key = getAdminKey()
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'X-Admin-Key': key,
      ...(options.headers ?? {}),
    },
  })
  if (res.status === 401) throw new Error('invalid_key')
  if (res.status === 503) throw new Error('admin_not_configured')
  if (!res.ok) throw new Error(`http_${res.status}`)
  return res.json()
}
