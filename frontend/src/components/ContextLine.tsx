import type { CommitmentRead } from '../types'

interface Props {
  commitment: CommitmentRead
  now?: Date
}

function hoursUntil(dateStr: string, now: Date): number {
  return (new Date(dateStr).getTime() - now.getTime()) / (1000 * 60 * 60)
}

function daysUntil(dateStr: string, now: Date): number {
  return hoursUntil(dateStr, now) / 24
}

const COUNTERPARTY_LABELS: Record<string, string> = {
  external_client: 'Client',
  internal_manager: 'Manager',
  internal_peer: 'Colleague',
  self: '',
}

export default function ContextLine({ commitment: c, now = new Date() }: Props) {
  const deliveryEvent = c.linked_events?.find((e) => e.relationship === 'delivery_at') ?? null

  // Priority 1: delivery event within 25h
  if (deliveryEvent) {
    const hours = hoursUntil(deliveryEvent.starts_at, now)
    if (hours > 0 && hours <= 25) {
      const prefix = c.counterparty_type ? COUNTERPARTY_LABELS[c.counterparty_type] : ''
      const label = prefix ? `${prefix} · ` : ''
      return (
        <p className="text-xs text-orange-600 mt-0.5">
          {label}{deliveryEvent.title} in {Math.round(hours)}h
        </p>
      )
    }
  }

  // Priority 2: delivery event within 72h
  if (deliveryEvent) {
    const hours = hoursUntil(deliveryEvent.starts_at, now)
    if (hours > 0 && hours <= 72) {
      const days = Math.ceil(hours / 24)
      return (
        <p className="text-xs text-yellow-600 mt-0.5">
          {deliveryEvent.title} in {days} day{days !== 1 ? 's' : ''}
        </p>
      )
    }
  }

  // Priority 3: acknowledged
  if (c.delivery_state === 'acknowledged') {
    return <p className="text-xs text-blue-600 mt-0.5">Acknowledged · waiting on you</p>
  }

  // Priority 4: draft_sent
  if (c.delivery_state === 'draft_sent') {
    return <p className="text-xs text-purple-600 mt-0.5">Draft sent · pending final</p>
  }

  // Priority 5: overdue
  if (c.resolved_deadline) {
    const days = daysUntil(c.resolved_deadline, now)
    if (days < 0) {
      return (
        <p className="text-xs text-red-600 mt-0.5">
          Overdue · {Math.round(Math.abs(days))} day{Math.round(Math.abs(days)) !== 1 ? 's' : ''}
        </p>
      )
    }
    // Priority 6: due within 3 days
    if (days <= 3) {
      const d = Math.ceil(days)
      return (
        <p className="text-xs text-yellow-600 mt-0.5">
          Due in {d} day{d !== 1 ? 's' : ''}
        </p>
      )
    }
  }

  // Priority 7: external client
  if (c.counterparty_type === 'external_client') {
    return <p className="text-xs text-gray-500 mt-0.5">External commitment</p>
  }

  // Priority 8: nothing
  return null
}
