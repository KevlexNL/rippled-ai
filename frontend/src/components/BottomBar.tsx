interface Props {
  onOverview: () => void
  onRevert: () => void
  canRevert: boolean
}

export default function BottomBar({ onOverview, onRevert, canRevert }: Props) {
  return (
    <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-100 px-4 py-2 pb-safe flex items-center justify-between gap-2 z-10">
      <button
        type="button"
        onClick={onOverview}
        className="flex-1 py-2.5 rounded-lg bg-black text-white text-sm font-medium hover:bg-gray-900 active:bg-gray-800 transition-colors"
      >
        Overview
      </button>
      <button
        type="button"
        onClick={onRevert}
        disabled={!canRevert}
        className="flex-1 py-2.5 rounded-lg border border-gray-200 text-sm font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed hover:enabled:bg-gray-50 active:enabled:bg-gray-100"
      >
        Quick revert
      </button>
      <button
        type="button"
        disabled
        className="flex-1 py-2.5 rounded-lg border border-gray-100 text-sm font-medium text-gray-300 cursor-not-allowed"
      >
        Talk it through
      </button>
      <button
        type="button"
        disabled
        className="flex-1 py-2.5 rounded-lg border border-gray-100 text-sm font-medium text-gray-300 cursor-not-allowed"
      >
        Start session
      </button>
    </div>
  )
}
