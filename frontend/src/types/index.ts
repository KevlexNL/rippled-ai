export type LifecycleState =
  | 'proposed'
  | 'active'
  | 'needs_clarification'
  | 'delivered'
  | 'closed'
  | 'discarded'

export interface LinkedEventRead {
  event_id: string
  title: string
  starts_at: string
  ends_at: string | null
  relationship: string
}

export interface CommitmentRead {
  id: string
  user_id: string
  version: number
  title: string
  description: string | null
  commitment_text: string | null
  commitment_type: string | null
  priority_class: string | null
  context_type: string | null
  resolved_owner: string | null
  suggested_owner: string | null
  ownership_ambiguity: string | null
  resolved_deadline: string | null
  vague_time_phrase: string | null
  suggested_due_date: string | null
  timing_ambiguity: string | null
  deliverable: string | null
  target_entity: string | null
  suggested_next_step: string | null
  deliverable_ambiguity: string | null
  lifecycle_state: LifecycleState
  state_changed_at: string
  confidence_commitment: string | null // Decimal from backend, comes as string
  confidence_owner: string | null
  confidence_deadline: string | null
  confidence_delivery: string | null
  confidence_closure: string | null
  confidence_actionability: string | null
  commitment_explanation: string | null
  missing_pieces_explanation: string | null
  is_surfaced: boolean
  surfaced_at: string | null
  observe_until: string | null
  observation_window_hours: string | null
  surfaced_as: string | null
  priority_score: string | null
  timing_strength: number | null
  business_consequence: number | null
  cognitive_burden: number | null
  confidence_for_surfacing: string | null
  surfacing_reason: string | null
  owner_candidates: unknown[] | null
  deadline_candidates: unknown[] | null
  // Phase C3 fields
  delivery_state: string | null
  counterparty_type: string | null
  counterparty_email: string | null
  post_event_reviewed: boolean
  // Phase C5 — linked events
  linked_events: LinkedEventRead[] | null
  created_at: string
  updated_at: string
}

export interface CommitmentSignalRead {
  id: string
  commitment_id: string
  source_item_id: string
  user_id: string
  signal_role: string // 'origin' | 'clarification' | 'delivery' | 'closure'
  confidence: string | null
  interpretation_note: string | null
  created_at: string
}

export interface CommitmentAmbiguityRead {
  id: string
  commitment_id: string
  ambiguity_type: string // 'owner_missing' | 'timing_missing' | 'deliverable_unclear' | 'timing_vague' | 'owner_vague_collective' | etc
  description: string | null
  is_resolved: boolean
  resolved_by_item_id: string | null
  resolved_at: string | null
  created_at: string
}

export interface CommitmentCreate {
  title: string
  description?: string | null
  commitment_text?: string | null
  context_type?: string | null
  resolved_owner?: string | null
  resolved_deadline?: string | null
  target_entity?: string | null
}

export function getStatusColor(c: CommitmentRead): 'red' | 'yellow' | 'green' {
  if (c.lifecycle_state === 'needs_clarification') return 'red'
  if (c.ownership_ambiguity === 'missing' || c.timing_ambiguity === 'missing') return 'red'
  if (c.lifecycle_state === 'proposed') return 'yellow'
  if (c.ownership_ambiguity === 'vague' || c.timing_ambiguity === 'vague') return 'yellow'
  if (
    c.confidence_commitment !== null &&
    c.confidence_commitment !== undefined &&
    Number(c.confidence_commitment) < 0.5
  )
    return 'yellow'
  return 'green'
}

export function getGroupStatusColor(commitments: CommitmentRead[]): 'red' | 'yellow' | 'green' {
  const colors = commitments.map(getStatusColor)
  if (colors.includes('red')) return 'red'
  if (colors.includes('yellow')) return 'yellow'
  return 'green'
}
