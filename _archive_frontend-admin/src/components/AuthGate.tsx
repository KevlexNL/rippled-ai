import React, { useState } from 'react'
import { getAdminKey, setAdminKey } from '../lib/auth'

interface AuthGateProps {
  children: React.ReactNode
}

export function AuthGate({ children }: AuthGateProps) {
  const [key, setKey] = useState(getAdminKey)
  const [input, setInput] = useState('')
  const [error, setError] = useState('')

  if (key) {
    return <>{children}</>
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!input.trim()) {
      setError('Please enter an admin key')
      return
    }
    setAdminKey(input.trim())
    setKey(input.trim())
    setError('')
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100">
      <div className="bg-white p-8 rounded shadow w-full max-w-sm">
        <h1 className="text-xl font-bold mb-4">Rippled Admin</h1>
        <p className="text-sm text-gray-500 mb-4">Enter your admin API key to continue.</p>
        <form onSubmit={handleSubmit} className="space-y-3">
          <input
            type="password"
            className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Admin key"
            value={input}
            onChange={e => setInput(e.target.value)}
          />
          {error && <p className="text-red-500 text-xs">{error}</p>}
          <button
            type="submit"
            className="w-full bg-blue-600 text-white rounded px-4 py-2 text-sm font-medium hover:bg-blue-700"
          >
            Sign in
          </button>
        </form>
      </div>
    </div>
  )
}
