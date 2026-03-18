import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  getIdentityProfile,
  seedIdentities,
  confirmIdentities,
  addManualIdentity,
  deleteIdentity,
  runBackfill,
  type IdentityProfileRead,
} from '../../api/identity'

function typeBadge(type: string) {
  const labels: Record<string, string> = {
    full_name: 'Name',
    first_name: 'First Name',
    email: 'Email',
    alias: 'Alias',
  }
  return labels[type] ?? type
}

function sourceBadge(source: string | null, confirmed: boolean) {
  if (confirmed && source === 'manual') return 'Manual'
  if (confirmed) return 'Confirmed'
  return 'Detected'
}

export default function IdentitySettingsScreen() {
  const queryClient = useQueryClient()
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [manualType, setManualType] = useState('full_name')
  const [manualValue, setManualValue] = useState('')
  const [backfillMessage, setBackfillMessage] = useState<string | null>(null)

  const { data: profiles = [] } = useQuery<IdentityProfileRead[]>({
    queryKey: ['identity-profiles'],
    queryFn: getIdentityProfile,
  })

  const confirmed = profiles.filter(p => p.confirmed)
  const unconfirmed = profiles.filter(p => !p.confirmed)

  const seedMutation = useMutation({
    mutationFn: seedIdentities,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['identity-profiles'] })
    },
  })

  const confirmMutation = useMutation({
    mutationFn: ({ confirmIds, rejectIds }: { confirmIds: string[]; rejectIds: string[] }) =>
      confirmIdentities(confirmIds, rejectIds),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['identity-profiles'] })
      queryClient.invalidateQueries({ queryKey: ['commitments'] })
      setSelectedIds(new Set())
      // Count newly confirmed to show backfill message
      setBackfillMessage('Identities confirmed and commitments updated.')
      setTimeout(() => setBackfillMessage(null), 5000)
    },
  })

  const manualMutation = useMutation({
    mutationFn: ({ type, value }: { type: string; value: string }) =>
      addManualIdentity(type, value),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['identity-profiles'] })
      queryClient.invalidateQueries({ queryKey: ['commitments'] })
      setManualValue('')
      setBackfillMessage('Identity added and commitments updated.')
      setTimeout(() => setBackfillMessage(null), 5000)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      await deleteIdentity(id)
      await runBackfill()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['identity-profiles'] })
      queryClient.invalidateQueries({ queryKey: ['commitments'] })
    },
  })

  function toggleSelected(id: string) {
    setSelectedIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function handleConfirmSelected() {
    const confirmIds = Array.from(selectedIds)
    const rejectIds = unconfirmed.filter(p => !selectedIds.has(p.id)).map(p => p.id)
    confirmMutation.mutate({ confirmIds, rejectIds })
  }

  return (
    <div>
      {/* Success message */}
      {backfillMessage && (
        <div className="mb-4 px-3 py-2 rounded-lg bg-green-50 text-green-700 text-xs font-medium">
          {backfillMessage}
        </div>
      )}

      {/* Section 1: Confirmed Identities */}
      <div className="mb-8">
        <h3 className="text-sm font-semibold text-black mb-1">Your Identities</h3>
        <p className="text-xs text-gray-500 mb-3">
          Rippled uses these to match commitments to you. Names and emails that appear in your messages.
        </p>

        {confirmed.length > 0 ? (
          <div className="space-y-2">
            {confirmed.map(p => (
              <div key={p.id} className="flex items-center gap-3 rounded-lg border border-gray-100 px-3 py-2">
                <span className="inline-flex px-2 py-0.5 rounded-full bg-gray-100 text-gray-600 text-[10px] font-medium uppercase tracking-wide">
                  {typeBadge(p.identity_type)}
                </span>
                <span className="flex-1 text-sm text-black">{p.identity_value}</span>
                <span className="text-[10px] text-gray-400">{sourceBadge(p.source, p.confirmed)}</span>
                <button
                  onClick={() => deleteMutation.mutate(p.id)}
                  disabled={deleteMutation.isPending}
                  className="text-gray-400 hover:text-red-500 text-xs transition-colors"
                >
                  Remove
                </button>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-gray-400 italic">No confirmed identities yet. Detect from your data or add manually below.</p>
        )}
      </div>

      {/* Divider */}
      <div className="border-t border-gray-100 mb-6" />

      {/* Section 2: Detect + Manual */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Detect */}
        <div>
          <h3 className="text-sm font-semibold text-black mb-1">Detect from Sources</h3>
          <p className="text-xs text-gray-500 mb-3">
            Scan your connected email and messages to find names and addresses you use.
          </p>
          <button
            onClick={() => seedMutation.mutate()}
            disabled={seedMutation.isPending}
            className="px-3 py-1.5 rounded-lg bg-black text-white text-xs font-medium hover:bg-gray-900 transition-colors disabled:opacity-50"
          >
            {seedMutation.isPending ? 'Scanning...' : 'Detect from my data'}
          </button>

          {unconfirmed.length > 0 && (
            <div className="mt-4 space-y-2">
              <p className="text-xs text-gray-500 font-medium">Select identities to confirm:</p>
              {unconfirmed.map(p => (
                <label key={p.id} className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={selectedIds.has(p.id)}
                    onChange={() => toggleSelected(p.id)}
                    className="rounded border-gray-300"
                  />
                  <span className="inline-flex px-1.5 py-0.5 rounded bg-gray-100 text-gray-500 text-[10px] font-medium uppercase">
                    {typeBadge(p.identity_type)}
                  </span>
                  <span className="text-sm text-black">{p.identity_value}</span>
                </label>
              ))}
              <button
                onClick={handleConfirmSelected}
                disabled={selectedIds.size === 0 || confirmMutation.isPending}
                className="mt-2 px-3 py-1.5 rounded-lg bg-black text-white text-xs font-medium hover:bg-gray-900 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {confirmMutation.isPending ? 'Confirming...' : `Confirm selected (${selectedIds.size})`}
              </button>
            </div>
          )}
        </div>

        {/* Manual */}
        <div>
          <h3 className="text-sm font-semibold text-black mb-1">Add Manually</h3>
          <p className="text-xs text-gray-500 mb-3">
            Add a name, email, or alias that Rippled should recognize as you.
          </p>
          <div className="flex flex-col gap-2">
            <select
              value={manualType}
              onChange={e => setManualType(e.target.value)}
              className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm text-black focus:outline-none focus:ring-2 focus:ring-black focus:border-transparent"
            >
              <option value="full_name">Full Name</option>
              <option value="first_name">First Name</option>
              <option value="email">Email</option>
              <option value="alias">Alias</option>
            </select>
            <input
              type="text"
              value={manualValue}
              onChange={e => setManualValue(e.target.value)}
              placeholder={manualType === 'email' ? 'you@example.com' : 'Your name or alias'}
              className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm text-black placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-black focus:border-transparent"
            />
            <button
              onClick={() => manualMutation.mutate({ type: manualType, value: manualValue })}
              disabled={!manualValue.trim() || manualMutation.isPending}
              className="px-3 py-1.5 rounded-lg bg-black text-white text-xs font-medium hover:bg-gray-900 transition-colors self-start disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {manualMutation.isPending ? 'Adding...' : 'Add identity'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
