import React from 'react'

interface PaginationProps {
  total: number
  limit: number
  offset: number
  onPage: (offset: number) => void
}

export function Pagination({ total, limit, offset, onPage }: PaginationProps) {
  const page = Math.floor(offset / limit)
  const pages = Math.ceil(total / limit)

  if (pages <= 1) return null

  return (
    <div className="flex items-center gap-2 mt-4 text-sm text-gray-600">
      <button
        className="px-3 py-1 border rounded disabled:opacity-40"
        disabled={page === 0}
        onClick={() => onPage((page - 1) * limit)}
      >
        Previous
      </button>
      <span>Page {page + 1} of {pages} ({total} total)</span>
      <button
        className="px-3 py-1 border rounded disabled:opacity-40"
        disabled={page >= pages - 1}
        onClick={() => onPage((page + 1) * limit)}
      >
        Next
      </button>
    </div>
  )
}
