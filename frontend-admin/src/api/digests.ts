import { adminFetch } from '../lib/apiClient'

export interface DigestRow {
  id: string
  sent_at: string
  commitment_count: number
  delivery_method: string
  status: string
  error_message: string | null
}

export interface DigestsResponse {
  items: DigestRow[]
  total: number
}

export async function fetchDigests(limit = 50, offset = 0): Promise<DigestsResponse> {
  return adminFetch(`/api/v1/admin/digests?limit=${limit}&offset=${offset}`) as Promise<DigestsResponse>
}

export async function fetchDigest(id: string): Promise<unknown> {
  return adminFetch(`/api/v1/admin/digests/${id}`)
}
