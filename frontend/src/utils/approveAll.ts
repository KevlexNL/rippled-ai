import type { CommitmentRead } from '../types'
import { patchCommitment } from '../api/commitments'

export interface UndoEntry {
  id: string
  previousState: string
}

/**
 * Approve all proposed commitments by PATCHing them to 'active'.
 * Returns an undo buffer with their previous states.
 */
export async function approveAll(commitments: CommitmentRead[]): Promise<UndoEntry[]> {
  const proposed = commitments.filter((c) => c.lifecycle_state === 'proposed')
  const undoBuffer: UndoEntry[] = proposed.map((c) => ({
    id: c.id,
    previousState: c.lifecycle_state,
  }))

  await Promise.all(proposed.map((c) => patchCommitment(c.id, { lifecycle_state: 'active' })))

  return undoBuffer
}

/**
 * Revert commitments to their previous states from the undo buffer.
 */
export async function revertApproval(undoBuffer: UndoEntry[]): Promise<void> {
  await Promise.all(
    undoBuffer.map((entry) =>
      patchCommitment(entry.id, { lifecycle_state: entry.previousState })
    )
  )
}
