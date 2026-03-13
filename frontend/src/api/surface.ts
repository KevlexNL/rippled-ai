import { apiGet } from '../lib/apiClient'
import type { CommitmentRead } from '../types'

export const getSurface = (type: 'main' | 'shortlist' | 'clarifications') =>
  apiGet<CommitmentRead[]>(`/api/v1/surface/${type}`)
