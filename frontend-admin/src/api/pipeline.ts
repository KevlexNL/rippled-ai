import { adminFetch } from '../lib/apiClient'

export async function runSurfacing(): Promise<unknown> {
  return adminFetch('/api/v1/admin/pipeline/run-surfacing', { method: 'POST' })
}

export async function runLinker(): Promise<unknown> {
  return adminFetch('/api/v1/admin/pipeline/run-linker', { method: 'POST' })
}

export async function runNudge(): Promise<unknown> {
  return adminFetch('/api/v1/admin/pipeline/run-nudge', { method: 'POST' })
}

export async function runDigestPreview(): Promise<unknown> {
  return adminFetch('/api/v1/admin/pipeline/run-digest-preview', { method: 'POST' })
}

export async function runPostEventResolver(): Promise<unknown> {
  return adminFetch('/api/v1/admin/pipeline/run-post-event-resolver', { method: 'POST' })
}

export interface SeedRequest {
  description: string
  lifecycle_state?: string
  resolved_deadline?: string
  counterparty_type?: string
  source_type?: string
}

export async function seedCommitment(body: SeedRequest): Promise<unknown> {
  return adminFetch('/api/v1/admin/test/seed-commitment', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export async function cleanupTestData(): Promise<unknown> {
  return adminFetch('/api/v1/admin/test/cleanup', {
    method: 'DELETE',
    body: JSON.stringify({ confirm: 'delete-test-data' }),
  })
}
