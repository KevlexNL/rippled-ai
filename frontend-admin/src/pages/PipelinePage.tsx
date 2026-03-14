import React, { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { runSurfacing, runLinker, runNudge, runDigestPreview, runPostEventResolver, seedCommitment, cleanupTestData } from '../api/pipeline'
import { JsonViewer } from '../components/JsonViewer'
import { ConfirmModal } from '../components/ConfirmModal'

interface TriggerCardProps {
  title: string
  description: string
  onRun: () => Promise<unknown>
}

function TriggerCard({ title, description, onRun }: TriggerCardProps) {
  const [result, setResult] = useState<unknown>(null)
  const mutation = useMutation({ mutationFn: onRun, onSuccess: setResult })

  return (
    <div className="border rounded bg-white p-4 space-y-2">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="font-medium text-sm">{title}</h3>
          <p className="text-xs text-gray-500">{description}</p>
        </div>
        <button
          className="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 flex-shrink-0 ml-3"
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending}
        >
          {mutation.isPending ? 'Running...' : 'Run'}
        </button>
      </div>
      {mutation.isError && <p className="text-xs text-red-500">Error: {String(mutation.error)}</p>}
      {!!result && <JsonViewer data={result} />}
    </div>
  )
}

export function PipelinePage() {
  const [seedDesc, setSeedDesc] = useState('')
  const [showCleanup, setShowCleanup] = useState(false)
  const [seedResult, setSeedResult] = useState<unknown>(null)

  const seedMutation = useMutation({ mutationFn: () => seedCommitment({ description: seedDesc }), onSuccess: setSeedResult })
  const cleanupMutation = useMutation({ mutationFn: cleanupTestData, onSuccess: () => setShowCleanup(false) })

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold">Pipeline Triggers</h2>
      <p className="text-sm text-amber-600 bg-amber-50 border border-amber-200 rounded p-2">
        Manual triggers — avoid running while Celery beat is active to prevent duplicate audit rows.
      </p>

      <div className="space-y-3">
        <TriggerCard title="Surfacing Sweep" description="Recompute all commitment surfaces and priority scores" onRun={runSurfacing} />
        <TriggerCard title="Event Linker" description="Link commitments to delivery events" onRun={runLinker} />
        <TriggerCard title="Pre-Event Nudge" description="Force upcoming delivery commitments to main" onRun={runNudge} />
        <TriggerCard title="Digest Preview" description="Build digest without delivering (preview only)" onRun={runDigestPreview} />
        <TriggerCard title="Post-Event Resolver" description="Resolve commitments after their delivery events end" onRun={runPostEventResolver} />
      </div>

      <div className="border rounded bg-white p-4 space-y-3">
        <h3 className="font-medium text-sm">Test Data</h3>
        <div className="space-y-2">
          <input
            className="w-full border rounded px-3 py-2 text-sm"
            placeholder="Commitment description..."
            value={seedDesc}
            onChange={e => setSeedDesc(e.target.value)}
          />
          <button
            className="px-4 py-2 text-sm bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50"
            onClick={() => seedMutation.mutate()}
            disabled={!seedDesc || seedMutation.isPending}
          >
            {seedMutation.isPending ? 'Seeding...' : 'Seed Commitment'}
          </button>
          {!!seedResult && <JsonViewer data={seedResult} />}
        </div>

        <div className="border-t pt-3">
          <button
            className="px-4 py-2 text-sm bg-red-600 text-white rounded hover:bg-red-700"
            onClick={() => setShowCleanup(true)}
          >
            Cleanup Test Data
          </button>
        </div>
      </div>

      {showCleanup && (
        <ConfirmModal
          title="Delete Test Data"
          message="This will delete all rows created by admin-test-seed sources. This cannot be undone."
          onConfirm={() => cleanupMutation.mutate()}
          onCancel={() => setShowCleanup(false)}
          loading={cleanupMutation.isPending}
        />
      )}
    </div>
  )
}
