type Color = 'red' | 'yellow' | 'green'

const colorMap: Record<Color, string> = {
  red: 'bg-red-500',
  yellow: 'bg-yellow-400',
  green: 'bg-green-500',
}

export default function StatusDot({
  color,
  size = 'md',
}: {
  color: Color
  size?: 'sm' | 'md'
}) {
  const dim = size === 'sm' ? 'w-2 h-2' : 'w-3 h-3'
  return (
    <span className={`inline-block rounded-full flex-shrink-0 ${dim} ${colorMap[color]}`} />
  )
}
