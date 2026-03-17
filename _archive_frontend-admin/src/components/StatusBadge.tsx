import React from 'react'

const COLORS: Record<string, string> = {
  active: 'bg-green-100 text-green-800',
  proposed: 'bg-blue-100 text-blue-800',
  needs_clarification: 'bg-yellow-100 text-yellow-800',
  delivered: 'bg-purple-100 text-purple-800',
  closed: 'bg-gray-100 text-gray-800',
  discarded: 'bg-red-100 text-red-800',
  main: 'bg-indigo-100 text-indigo-800',
  shortlist: 'bg-cyan-100 text-cyan-800',
  clarifications: 'bg-orange-100 text-orange-800',
  ok: 'bg-green-100 text-green-800',
  stale: 'bg-yellow-100 text-yellow-800',
  unknown: 'bg-gray-100 text-gray-500',
  sent: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
  confirmed: 'bg-green-100 text-green-800',
  cancelled: 'bg-red-100 text-red-800',
  tentative: 'bg-yellow-100 text-yellow-800',
}

interface StatusBadgeProps {
  value: string | null | undefined
}

export function StatusBadge({ value }: StatusBadgeProps) {
  if (!value) return <span className="text-gray-400 text-xs">—</span>
  const cls = COLORS[value] ?? 'bg-gray-100 text-gray-700'
  return <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${cls}`}>{value}</span>
}
