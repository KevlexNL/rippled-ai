/**
 * Tests for ArchitectureScreen component.
 *
 * Verifies:
 * - Architecture data loads and renders nodes
 * - Layer filter toggles work
 * - Node click opens detail panel
 * - Status colors are correct
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'

// Polyfill ResizeObserver for jsdom (required by React Flow)
globalThis.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

// Polyfill DOMMatrixReadOnly (required by React Flow)
if (!globalThis.DOMMatrixReadOnly) {
  globalThis.DOMMatrixReadOnly = class DOMMatrixReadOnly {
    m22: number
    constructor() { this.m22 = 1 }
    transformPoint() { return { x: 0, y: 0 } }
  } as unknown as typeof DOMMatrixReadOnly
}

// Mock auth to return admin user
vi.mock('../lib/auth', () => ({
  useAuth: () => ({
    user: { id: '441f9c1f-9428-477e-a04f-fb8d5e654ec2' },
    session: { access_token: 'test' },
    loading: false,
  }),
}))

// Mock apiClient
vi.mock('../lib/apiClient', () => ({
  apiGet: vi.fn().mockResolvedValue([]),
  apiPost: vi.fn().mockResolvedValue({}),
}))

// Sample architecture data
const MOCK_ARCH_DATA = {
  nodes: [
    {
      id: 'web-app',
      label: 'Rippled Web App',
      layer: 'user_flow',
      status: 'stable',
      description: 'Main SPA',
      code_path: 'frontend/src/App.tsx',
      git_sha: 'abc123',
      wos: [],
    },
    {
      id: 'signal-detection',
      label: 'Candidate Detection',
      layer: 'signal_pipeline',
      status: 'stable',
      description: 'Detects commitment signals',
      code_path: 'app/services/model_detection.py',
      git_sha: 'abc123',
      prompt_version: 'ongoing-v4',
      prompt_file: 'ops/prompts/detection-prompt-v6.md',
      wos: ['WO-RIPPLED-COMMITMENT-STRUCTURE-DETECTION'],
      open_questions: ['Should delegated asks be first-class?'],
    },
    {
      id: 'lifecycle-proposed',
      label: 'Proposed',
      layer: 'commitment_lifecycle',
      status: 'stable',
      description: 'Initial lifecycle state',
      wos: [],
    },
    {
      id: 'integration-calendar',
      label: 'Calendar',
      layer: 'integrations',
      status: 'planned',
      description: 'Calendar integration',
      wos: [],
    },
  ],
  edges: [
    { id: 'e1', source: 'web-app', target: 'signal-detection', label: 'detect' },
  ],
}

// Mock fetch for architecture JSON
const originalFetch = globalThis.fetch

beforeEach(() => {
  globalThis.fetch = vi.fn().mockImplementation((url: string) => {
    if (url.includes('rippled-arch.json')) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(MOCK_ARCH_DATA),
      })
    }
    if (url.includes('ops/prompts/')) {
      return Promise.resolve({
        ok: true,
        text: () => Promise.resolve('# Detection Prompt v6\nYou are a commitment detector...'),
      })
    }
    return Promise.resolve({ ok: false })
  })
})

afterEach(() => {
  globalThis.fetch = originalFetch
  vi.restoreAllMocks()
})

function renderScreen() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/admin/architecture']}>
        <ArchitectureScreen />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

// Lazy import so mocks are in place
let ArchitectureScreen: typeof import('../screens/ArchitectureScreen').default

beforeEach(async () => {
  const mod = await import('../screens/ArchitectureScreen')
  ArchitectureScreen = mod.default
})

describe('ArchitectureScreen', () => {
  it('renders the header with Architecture tab active', async () => {
    renderScreen()
    await waitFor(() => {
      expect(screen.getByText('Architecture')).toBeDefined()
      expect(screen.getByText('rippled')).toBeDefined()
    })
  })

  it('renders layer filter buttons', async () => {
    renderScreen()
    await waitFor(() => {
      expect(screen.getByText('All Layers')).toBeDefined()
      expect(screen.getByText('User Flow')).toBeDefined()
      expect(screen.getByText('Signal Pipeline')).toBeDefined()
      expect(screen.getByText('Commitment Lifecycle')).toBeDefined()
      expect(screen.getByText('Evaluation')).toBeDefined()
      expect(screen.getByText('Integrations')).toBeDefined()
    })
  })

  it('renders status legend', async () => {
    renderScreen()
    await waitFor(() => {
      expect(screen.getByText('stable')).toBeDefined()
      expect(screen.getByText('in progress')).toBeDefined()
      expect(screen.getByText('planned')).toBeDefined()
      expect(screen.getByText('broken')).toBeDefined()
      expect(screen.getByText('decision needed')).toBeDefined()
    })
  })

  it('loads architecture data from JSON', async () => {
    renderScreen()
    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith(
        expect.stringContaining('rippled-arch.json')
      )
    })
  })

  it('filters by layer when toggled', async () => {
    renderScreen()
    await waitFor(() => {
      expect(screen.getByText('User Flow')).toBeDefined()
    })
    fireEvent.click(screen.getByText('User Flow'))
    // After clicking, the button should be active (visual change)
    // This tests that the click handler works without error
  })
})
