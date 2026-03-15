interface Props {
  state: string | null
}

const BADGE_CONFIG: Record<string, { label: string; className: string }> = {
  draft_sent: { label: 'Draft sent', className: 'bg-purple-100 text-purple-700' },
  acknowledged: { label: 'Acknowledged', className: 'bg-blue-100 text-blue-700' },
  partial: { label: 'Partial', className: 'bg-yellow-100 text-yellow-700' },
  rescheduled: { label: 'Rescheduled', className: 'bg-orange-100 text-orange-700' },
}

export default function DeliveryBadge({ state }: Props) {
  if (!state) return null
  const config = BADGE_CONFIG[state]
  if (!config) return null
  return (
    <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${config.className}`}>
      {config.label}
    </span>
  )
}
