import React, { useState } from 'react'

interface JsonViewerProps {
  data: unknown
  title?: string
}

export function JsonViewer({ data, title }: JsonViewerProps) {
  const [expanded, setExpanded] = useState(false)
  const json = JSON.stringify(data, null, 2)
  const preview = json.slice(0, 200)

  return (
    <div className="mt-2">
      {title && <p className="text-xs text-gray-500 font-medium mb-1">{title}</p>}
      <pre className="bg-gray-900 text-green-400 text-xs rounded p-3 overflow-auto max-h-96">
        {expanded ? json : preview + (json.length > 200 ? '...' : '')}
      </pre>
      {json.length > 200 && (
        <button
          className="text-xs text-blue-500 mt-1"
          onClick={() => setExpanded(e => !e)}
        >
          {expanded ? 'Collapse' : 'Expand'}
        </button>
      )}
    </div>
  )
}
