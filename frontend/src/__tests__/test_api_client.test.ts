import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// Mock supabase before importing apiClient
vi.mock('../lib/supabase', () => ({
  supabase: {
    auth: {
      getSession: vi.fn(),
    },
  },
}))

import { apiGet, apiPost, apiPatch } from '../lib/apiClient'
import { supabase } from '../lib/supabase'

const mockGetSession = supabase.auth.getSession as ReturnType<typeof vi.fn>

function mockSessionWithUser(userId: string) {
  mockGetSession.mockResolvedValue({
    data: {
      session: {
        user: { id: userId },
      },
    },
  })
}

function mockNoSession() {
  mockGetSession.mockResolvedValue({
    data: { session: null },
  })
}

const TEST_USER_ID = 'user-abc-123'
const FAKE_RESPONSE = { id: '1', title: 'Test commitment' }

beforeEach(() => {
  vi.restoreAllMocks()
  // Reset env
  import.meta.env.VITE_API_BASE_URL = 'https://api.example.com'
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('apiGet', () => {
  it('1. injects X-User-ID header correctly', async () => {
    mockSessionWithUser(TEST_USER_ID)
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(FAKE_RESPONSE),
    })
    vi.stubGlobal('fetch', mockFetch)

    await apiGet('/api/v1/commitments')

    expect(mockFetch).toHaveBeenCalledOnce()
    const [, options] = mockFetch.mock.calls[0]
    expect(options.headers['X-User-ID']).toBe(TEST_USER_ID)
  })

  it('2. prepends BASE_URL to the path', async () => {
    mockSessionWithUser(TEST_USER_ID)
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(FAKE_RESPONSE),
    })
    vi.stubGlobal('fetch', mockFetch)

    await apiGet('/api/v1/commitments')

    const [url] = mockFetch.mock.calls[0]
    expect(url).toContain('/api/v1/commitments')
  })

  it('3. throws Error on non-2xx response', async () => {
    mockSessionWithUser(TEST_USER_ID)
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      json: () => Promise.resolve({ detail: 'Not found' }),
    })
    vi.stubGlobal('fetch', mockFetch)

    await expect(apiGet('/api/v1/commitments/missing')).rejects.toThrow('API error 404')
  })

  it('4. returns parsed JSON on success', async () => {
    mockSessionWithUser(TEST_USER_ID)
    const expected = [{ id: '1', title: 'Test' }]
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(expected),
    })
    vi.stubGlobal('fetch', mockFetch)

    const result = await apiGet('/api/v1/commitments')
    expect(result).toEqual(expected)
  })

  it('6. does not call fetch if no session (throws before fetch)', async () => {
    mockNoSession()
    const mockFetch = vi.fn()
    vi.stubGlobal('fetch', mockFetch)

    await expect(apiGet('/api/v1/commitments')).rejects.toThrow('Not authenticated')
    expect(mockFetch).not.toHaveBeenCalled()
  })
})

describe('apiPost', () => {
  it('5. sends correct body as JSON string', async () => {
    mockSessionWithUser(TEST_USER_ID)
    const body = { title: 'New commitment', context_type: 'meeting' }
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ id: 'new-id', ...body }),
    })
    vi.stubGlobal('fetch', mockFetch)

    await apiPost('/api/v1/commitments', body)

    const [, options] = mockFetch.mock.calls[0]
    expect(options.method).toBe('POST')
    expect(options.body).toBe(JSON.stringify(body))
    expect(options.headers['Content-Type']).toBe('application/json')
    expect(options.headers['X-User-ID']).toBe(TEST_USER_ID)
  })

  it('throws on non-2xx from POST', async () => {
    mockSessionWithUser(TEST_USER_ID)
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      json: () => Promise.resolve({ detail: 'Validation error' }),
    })
    vi.stubGlobal('fetch', mockFetch)

    await expect(apiPost('/api/v1/commitments', {})).rejects.toThrow('API error 422')
  })
})

describe('apiPatch', () => {
  it('sends PATCH method with correct body', async () => {
    mockSessionWithUser(TEST_USER_ID)
    const body = { lifecycle_state: 'active' }
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ id: '1', ...body }),
    })
    vi.stubGlobal('fetch', mockFetch)

    await apiPatch('/api/v1/commitments/1', body)

    const [, options] = mockFetch.mock.calls[0]
    expect(options.method).toBe('PATCH')
    expect(options.body).toBe(JSON.stringify(body))
    expect(options.headers['X-User-ID']).toBe(TEST_USER_ID)
  })

  it('throws if no session before PATCH', async () => {
    mockNoSession()
    const mockFetch = vi.fn()
    vi.stubGlobal('fetch', mockFetch)

    await expect(apiPatch('/api/v1/commitments/1', {})).rejects.toThrow('Not authenticated')
    expect(mockFetch).not.toHaveBeenCalled()
  })
})
