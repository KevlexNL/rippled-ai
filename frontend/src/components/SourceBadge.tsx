type SourceType = 'meeting' | 'slack' | 'email'

const labels: Record<SourceType, string> = {
  meeting: 'Meeting',
  slack: 'Slack',
  email: 'Email',
}

const icons: Record<SourceType, string> = {
  meeting: '🎙',
  slack: '💬',
  email: '✉️',
}

export default function SourceBadge({ type }: { type: string }) {
  const sourceType = type as SourceType
  const label = labels[sourceType] ?? type
  const icon = icons[sourceType] ?? '📎'

  return (
    <span className="inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">
      <span>{icon}</span>
      <span>{label}</span>
    </span>
  )
}
