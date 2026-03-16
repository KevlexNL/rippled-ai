import { supabase } from './supabase'

const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string) || ''

export async function getUserId(): Promise<string> {
  const { data } = await supabase.auth.getSession()
  const userId = data.session?.user?.id
  if (!userId) throw new Error('Not authenticated')
  return userId
}

export async function apiGet<T>(path: string): Promise<T> {
  const userId = await getUserId()
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'X-User-ID': userId, 'Content-Type': 'application/json' },
  })
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`)
  return res.json() as Promise<T>
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const userId = await getUserId()
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    headers: { 'X-User-ID': userId, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`)
  return res.json() as Promise<T>
}

export async function apiPatch<T>(path: string, body: unknown): Promise<T> {
  const userId = await getUserId()
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'PATCH',
    headers: { 'X-User-ID': userId, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`)
  return res.json() as Promise<T>
}

export async function apiDelete(path: string): Promise<void> {
  const userId = await getUserId()
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'DELETE',
    headers: { 'X-User-ID': userId },
  })
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`)
}
