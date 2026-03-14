import React from 'react'

interface ConfirmModalProps {
  title: string
  message: string
  onConfirm: () => void
  onCancel: () => void
  loading?: boolean
}

export function ConfirmModal({ title, message, onConfirm, onCancel, loading }: ConfirmModalProps) {
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded shadow-lg p-6 w-full max-w-sm">
        <h2 className="font-bold text-lg mb-2">{title}</h2>
        <p className="text-sm text-gray-600 mb-4">{message}</p>
        <div className="flex gap-2 justify-end">
          <button
            className="px-4 py-2 text-sm border rounded hover:bg-gray-50"
            onClick={onCancel}
            disabled={loading}
          >
            Cancel
          </button>
          <button
            className="px-4 py-2 text-sm bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50"
            onClick={onConfirm}
            disabled={loading}
          >
            {loading ? 'Deleting...' : 'Confirm'}
          </button>
        </div>
      </div>
    </div>
  )
}
