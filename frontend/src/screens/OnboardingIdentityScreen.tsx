import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import {
  seedIdentities,
  confirmIdentities,
  type IdentityProfileRead,
} from '../api/identity'

function typeBadge(type: string) {
  const labels: Record<string, string> = {
    full_name: 'Name',
    first_name: 'First Name',
    email: 'Email',
    alias: 'Alias',
  }
  return labels[type] ?? type
}

export default function OnboardingIdentityScreen() {
  const navigate = useNavigate()
  const [profiles, setProfiles] = useState<IdentityProfileRead[]>([])
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [step, setStep] = useState<'detecting' | 'review' | 'confirming' | 'done'>('detecting')
  const [error, setError] = useState<string | null>(null)

  const seedMutation = useMutation({
    mutationFn: seedIdentities,
    onSuccess: (data) => {
      setProfiles(data)
      // Pre-select all detected identities
      setSelectedIds(new Set(data.map(p => p.id)))
      setStep('review')
    },
    onError: () => {
      setError('Failed to detect identities. You can set them up later in Settings.')
      setStep('review')
    },
  })

  const confirmMutation = useMutation({
    mutationFn: ({ confirmIds, rejectIds }: { confirmIds: string[]; rejectIds: string[] }) =>
      confirmIdentities(confirmIds, rejectIds),
    onSuccess: () => {
      setStep('done')
      // Brief pause then redirect to dashboard
      setTimeout(() => navigate('/', { replace: true }), 1500)
    },
    onError: () => {
      setError('Failed to confirm identities. Please try again.')
    },
  })

  // Auto-trigger seed detection on mount
  useEffect(() => {
    seedMutation.mutate()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function toggleSelected(id: string) {
    setSelectedIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function handleConfirm() {
    setStep('confirming')
    const confirmIds = Array.from(selectedIds)
    const rejectIds = profiles.filter(p => !selectedIds.has(p.id)).map(p => p.id)
    confirmMutation.mutate({ confirmIds, rejectIds })
  }

  function handleSkip() {
    navigate('/', { replace: true })
  }

  return (
    <div className="min-h-screen bg-white flex flex-col items-center justify-center px-4">
      <div className="w-full max-w-md">
        {/* Header */}
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-bold text-black mb-2">Set up your identity</h1>
          <p className="text-sm text-gray-500 leading-relaxed">
            We found these names and addresses in your connected sources.
            Confirm the ones that refer to you — we'll use them to identify
            your commitments automatically.
          </p>
        </div>

        {/* Detecting state */}
        {step === 'detecting' && (
          <div className="flex flex-col items-center gap-3 py-8">
            <div className="w-8 h-8 border-2 border-black border-t-transparent rounded-full animate-spin" />
            <p className="text-sm text-gray-500">Scanning your sources...</p>
          </div>
        )}

        {/* Review state */}
        {step === 'review' && (
          <>
            {error && (
              <div className="mb-4 px-3 py-2 rounded-lg bg-amber-50 border border-amber-200 text-amber-700 text-sm">
                {error}
              </div>
            )}

            {profiles.length > 0 ? (
              <div className="space-y-2 mb-6">
                {profiles.map(p => (
                  <label
                    key={p.id}
                    className="flex items-center gap-3 rounded-xl border border-gray-100 px-4 py-3 cursor-pointer hover:bg-gray-50 transition-colors"
                  >
                    <input
                      type="checkbox"
                      checked={selectedIds.has(p.id)}
                      onChange={() => toggleSelected(p.id)}
                      className="rounded border-gray-300 text-black focus:ring-black"
                    />
                    <div className="flex-1 min-w-0">
                      <span className="text-sm text-black font-medium">{p.identity_value}</span>
                    </div>
                    <span className="inline-flex px-2 py-0.5 rounded-full bg-gray-100 text-gray-500 text-[10px] font-medium uppercase tracking-wide shrink-0">
                      {typeBadge(p.identity_type)}
                    </span>
                  </label>
                ))}
              </div>
            ) : (
              <div className="py-6 text-center text-sm text-gray-400">
                No identities detected yet. You can add them manually in Settings later.
              </div>
            )}

            <div className="space-y-3">
              <button
                onClick={handleConfirm}
                disabled={selectedIds.size === 0}
                className="w-full py-3 rounded-xl bg-black text-white text-sm font-semibold hover:bg-gray-900 active:bg-gray-800 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                Confirm {selectedIds.size > 0 ? `(${selectedIds.size})` : ''}
              </button>
              <button
                onClick={handleSkip}
                className="w-full py-3 rounded-xl border border-gray-200 text-sm font-medium text-gray-500 hover:bg-gray-50 transition-colors"
              >
                Skip for now
              </button>
            </div>
          </>
        )}

        {/* Confirming state */}
        {step === 'confirming' && (
          <div className="flex flex-col items-center gap-3 py-8">
            <div className="w-8 h-8 border-2 border-black border-t-transparent rounded-full animate-spin" />
            <p className="text-sm text-gray-500">Confirming identities and updating commitments...</p>
          </div>
        )}

        {/* Done state */}
        {step === 'done' && (
          <div className="flex flex-col items-center gap-3 py-8">
            <div className="w-10 h-10 rounded-full bg-green-100 flex items-center justify-center">
              <svg className="w-5 h-5 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <p className="text-sm font-medium text-black">Identity confirmed</p>
            <p className="text-xs text-gray-500">Redirecting to your dashboard...</p>
          </div>
        )}
      </div>
    </div>
  )
}
