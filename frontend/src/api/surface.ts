import { apiGet } from '../lib/apiClient'
import type { CommitmentRead } from '../types'

export const getSurface = (type: 'main' | 'shortlist' | 'clarifications') =>
  apiGet<CommitmentRead[]>(`/api/v1/surface/${type}`)

export interface BestNextMovesGroup {
  label: string
  items: CommitmentRead[]
}

export interface BestNextMovesResponse {
  groups: BestNextMovesGroup[]
}

export const getBestNextMoves = () =>
  apiGet<BestNextMovesResponse>('/api/v1/surface/best-next-moves')
