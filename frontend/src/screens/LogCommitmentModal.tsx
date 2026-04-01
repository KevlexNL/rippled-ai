import { useState, useRef, useEffect } from 'react'
import { postCommitment } from '../api/commitments'
import type { CommitmentCreate } from '../types'

type LogSource = 'slack' | 'email' | 'meeting'

interface LogCommitmentModalProps {
  onCancel: () => void
  onSuccess: () => void
}

export default function LogCommitmentModal({ onCancel, onSuccess }: LogCommitmentModalProps) {
  const [description, setDescription] = useState('')
  const [person, setPerson] = useState('')
  const [source, setSource] = useState<LogSource>('slack')
  const [deadline, setDeadline] = useState('')
  const [counterparty, setCounterparty] = useState('')
  const [success, setSuccess] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const errorRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (error) errorRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, [error])

  const sources: { id: LogSource; label: string }[] = [
    { id: 'slack', label: 'Slack' },
    { id: 'email', label: 'Email' },
    { id: 'meeting', label: 'Meetings' },
  ]

  async function handleSubmit() {
    if (!description.trim()) {
      setError('Please describe the commitment before saving.')
      return
    }
    setError(null)
    setLoading(true)
    try {
      const body: CommitmentCreate = {
        title: description,
        context_type: source,
        resolved_owner: person || undefined,
        resolved_deadline: deadline || undefined,
        counterparty_name: counterparty || undefined,
      }
      await postCommitment(body)
      setSuccess(true)
      setTimeout(() => {
        onSuccess()
      }, 1500)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to log commitment'
      if (message === 'Not authenticated') {
        setError('Session expired — please refresh the page.')
      } else {
        setError(message)
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-[540px] mx-auto pt-8 pb-8 px-6">
      <div className="pt-2 pb-4 text-center">
        <div className="font-semibold text-[24px] text-[#191919]">Log a commitment</div>
        <div className="text-[14px] text-[#6b7280] mt-1.5">Add something Rippled should track.</div>
      </div>
      <div className="bg-white border border-[#e8e8e6] rounded-lg p-6 mt-6" data-testid="modal-card">
        {success && (
          <div className="mb-4 rounded-md bg-[#f0fdf4] border border-[#bbf7d0] px-4 py-3 text-[13px] text-[#15803d] font-medium">
            Commitment logged. Rippled will track it.
          </div>
        )}

        {error && (
          <div ref={errorRef} data-testid="modal-error" className="mb-4 rounded-md bg-[#fee2e2] border border-[#fca5a5] px-4 py-3 text-[13px] text-[#991b1b] font-medium">
            {error}
          </div>
        )}

        <div data-testid="modal-fields">
        {/* What did you commit to? */}
        <div className="mb-5">
          <label className="block text-[13px] font-medium text-[#191919] mb-1.5">What did you commit to?</label>
          <textarea
            rows={3}
            className="w-full border border-[#e8e8e6] rounded-md px-3 py-2 text-[13px] text-[#191919] placeholder:text-[#9ca3af] focus:outline-none focus:border-[#d1d1cf] resize-none"
            placeholder="Describe the commitment or promise you made..."
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </div>

        {/* Who is involved? */}
        <div className="mb-5">
          <label className="block text-[13px] font-medium text-[#191919] mb-1.5">Who is involved?</label>
          <input
            type="text"
            className="w-full border border-[#e8e8e6] rounded-md px-3 py-2 text-[13px] text-[#191919] placeholder:text-[#9ca3af] focus:outline-none focus:border-[#d1d1cf]"
            placeholder="Person or team name"
            value={person}
            onChange={(e) => setPerson(e.target.value)}
          />
        </div>

        {/* Client / counterparty */}
        <div className="mb-5">
          <label className="block text-[13px] font-medium text-[#191919] mb-1.5">Client <span className="text-[#9ca3af] font-normal">(optional)</span></label>
          <input
            type="text"
            className="w-full border border-[#e8e8e6] rounded-md px-3 py-2 text-[13px] text-[#191919] placeholder:text-[#9ca3af] focus:outline-none focus:border-[#d1d1cf]"
            placeholder="Client or organization name"
            value={counterparty}
            onChange={(e) => setCounterparty(e.target.value)}
          />
        </div>

        {/* Source */}
        <div className="mb-5">
          <label className="block text-[13px] font-medium text-[#191919] mb-1.5">Source</label>
          <div className="flex gap-2">
            {sources.map((s) => (
              <button
                key={s.id}
                type="button"
                onClick={() => setSource(s.id)}
                className={`px-3 py-1.5 rounded-full text-[12px] font-medium transition-colors ${
                  source === s.id
                    ? 'bg-[#191919] text-white'
                    : 'border border-[#e8e8e6] text-[#6b7280] hover:text-[#191919]'
                }`}
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>

        {/* Deadline */}
        <div className="mb-6">
          <label className="block text-[13px] font-medium text-[#191919] mb-1.5">Any deadline or target date? <span className="text-[#9ca3af] font-normal">(optional)</span></label>
          <input
            type="date"
            className="w-full border border-[#e8e8e6] rounded-md px-3 py-2 text-[13px] text-[#191919] focus:outline-none focus:border-[#d1d1cf]"
            value={deadline}
            onChange={(e) => setDeadline(e.target.value)}
          />
        </div>

        </div>
        {/* Actions */}
        <div className="flex items-center gap-3 pt-4 border-t border-[#f0f0ef]">
          <button
            onClick={handleSubmit}
            disabled={loading || !description.trim()}
            className="bg-[#191919] text-white text-[13px] px-4 py-2 rounded-md font-medium hover:bg-[#333] transition-colors disabled:opacity-50"
          >
            {loading ? 'Saving...' : 'Log commitment'}
          </button>
          <button
            onClick={onCancel}
            className="text-[13px] text-[#6b7280] hover:text-[#191919] transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  )
}
