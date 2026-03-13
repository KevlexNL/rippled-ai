import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { supabase } from '../../lib/supabase'
import { useAuth } from '../../lib/auth'

export default function AccountSettingsScreen() {
  const { user, signOut } = useAuth()
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [passwordError, setPasswordError] = useState<string | null>(null)
  const [passwordSuccess, setPasswordSuccess] = useState(false)
  const [passwordLoading, setPasswordLoading] = useState(false)
  const [signOutLoading, setSignOutLoading] = useState(false)

  async function handleChangePassword(e: FormEvent) {
    e.preventDefault()
    setPasswordError(null)
    setPasswordSuccess(false)

    if (newPassword !== confirmPassword) {
      setPasswordError('Passwords do not match.')
      return
    }

    if (newPassword.length < 6) {
      setPasswordError('Password must be at least 6 characters.')
      return
    }

    setPasswordLoading(true)
    try {
      const { error } = await supabase.auth.updateUser({ password: newPassword })
      if (error) {
        setPasswordError(error.message)
      } else {
        setPasswordSuccess(true)
        setNewPassword('')
        setConfirmPassword('')
      }
    } catch {
      setPasswordError('An unexpected error occurred. Please try again.')
    } finally {
      setPasswordLoading(false)
    }
  }

  async function handleSignOut() {
    setSignOutLoading(true)
    try {
      await signOut()
    } finally {
      setSignOutLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-white pb-12">
      {/* Header */}
      <div className="px-4 pt-8 pb-4">
        <Link to="/" className="text-sm text-gray-500 hover:text-black transition-colors">
          ← Back
        </Link>
        <h1 className="text-2xl font-bold text-black mt-3">Account settings</h1>
      </div>

      <div className="px-4 space-y-8">
        {/* Email (read-only) */}
        <div>
          <h2 className="text-sm font-semibold text-gray-600 mb-3 uppercase tracking-wide">
            Email
          </h2>
          <div className="p-4 rounded-xl border border-gray-100 bg-gray-50">
            <p className="text-sm text-black">{user?.email ?? '—'}</p>
          </div>
        </div>

        {/* Change password */}
        <div>
          <h2 className="text-sm font-semibold text-gray-600 mb-3 uppercase tracking-wide">
            Change password
          </h2>
          <form onSubmit={handleChangePassword} className="space-y-3">
            <div>
              <label htmlFor="new-password" className="block text-sm font-medium text-black mb-1">
                New password
              </label>
              <input
                id="new-password"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                autoComplete="new-password"
                className="w-full px-3 py-2.5 rounded-lg border border-gray-200 text-sm text-black placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-black focus:border-transparent"
                placeholder="••••••••"
              />
            </div>
            <div>
              <label
                htmlFor="confirm-password"
                className="block text-sm font-medium text-black mb-1"
              >
                Confirm password
              </label>
              <input
                id="confirm-password"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                autoComplete="new-password"
                className="w-full px-3 py-2.5 rounded-lg border border-gray-200 text-sm text-black placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-black focus:border-transparent"
                placeholder="••••••••"
              />
            </div>

            {passwordError && (
              <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm">
                {passwordError}
              </div>
            )}

            {passwordSuccess && (
              <div className="p-3 rounded-lg bg-green-50 border border-green-200 text-green-700 text-sm">
                Password updated.
              </div>
            )}

            <button
              type="submit"
              disabled={passwordLoading}
              className="w-full py-2.5 rounded-lg bg-black text-white text-sm font-medium hover:bg-gray-900 active:bg-gray-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {passwordLoading ? 'Updating…' : 'Update password'}
            </button>
          </form>
        </div>

        {/* Sign out */}
        <div>
          <h2 className="text-sm font-semibold text-gray-600 mb-3 uppercase tracking-wide">
            Session
          </h2>
          <button
            type="button"
            disabled={signOutLoading}
            onClick={handleSignOut}
            className="w-full py-2.5 rounded-lg border border-gray-200 text-sm font-medium text-gray-700 hover:bg-gray-50 active:bg-gray-100 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {signOutLoading ? 'Signing out…' : 'Sign out'}
          </button>
        </div>
      </div>
    </div>
  )
}
