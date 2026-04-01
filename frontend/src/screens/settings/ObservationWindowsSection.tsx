import { useState, useEffect } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { getUserSettings, patchUserSettings } from '../../api/userSettings'
import type { ObservationWindowConfig, UserSettingsRead } from '../../api/userSettings'

const WINDOW_FIELDS: { key: keyof ObservationWindowConfig; label: string; description: string }[] = [
  { key: 'slack', label: 'Slack', description: '~2 working hours' },
  { key: 'email_internal', label: 'Email (internal)', description: '~24 working hours' },
  { key: 'email_external', label: 'Email (external)', description: '~48 working hours' },
  { key: 'meeting_internal', label: 'Meetings (internal)', description: '~24 working hours' },
  { key: 'meeting_external', label: 'Meetings (external)', description: '~48 working hours' },
]

const MIN_HOURS = 0.5
const MAX_HOURS = 168

function formatHours(h: number): string {
  if (h < 24) return `${h}h`
  const days = Math.floor(h / 24)
  const rem = h % 24
  return rem > 0 ? `${days}d ${rem}h` : `${days}d`
}

export default function ObservationWindowsSection() {
  const queryClient = useQueryClient()
  const { data: settings } = useQuery<UserSettingsRead>({
    queryKey: ['user-settings'],
    queryFn: getUserSettings,
    staleTime: 0,
  })

  const [values, setValues] = useState<ObservationWindowConfig | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dirty, setDirty] = useState(false)

  // Sync local state when settings load
  useEffect(() => {
    if (settings?.observation_window_config && !dirty) {
      setValues(settings.observation_window_config)
    }
  }, [settings, dirty])

  if (!values) return null

  function handleChange(key: keyof ObservationWindowConfig, raw: string) {
    const num = parseFloat(raw)
    if (isNaN(num)) return
    setValues(prev => prev ? { ...prev, [key]: num } : prev)
    setDirty(true)
  }

  function isValid(v: number): boolean {
    return v >= MIN_HOURS && v <= MAX_HOURS
  }

  const allValid = WINDOW_FIELDS.every(f => isValid(values[f.key]))

  async function handleSave() {
    if (!values || !allValid) return
    setError(null)
    setSaving(true)
    try {
      await patchUserSettings({ observation_window_config: values })
      queryClient.invalidateQueries({ queryKey: ['user-settings'] })
      setDirty(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save')
    } finally {
      setSaving(false)
    }
  }

  async function handleReset() {
    setError(null)
    setSaving(true)
    try {
      await patchUserSettings({ observation_window_config: null })
      queryClient.invalidateQueries({ queryKey: ['user-settings'] })
      setDirty(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to reset')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="mb-10">
      <h2 className="text-base font-semibold text-black">Observation Windows</h2>
      <p className="text-xs text-gray-500 mt-1 mb-5">
        How long Rippled silently observes a commitment before surfacing it. Values are in calendar hours.
      </p>
      <div className="space-y-3">
        {WINDOW_FIELDS.map(({ key, label, description }) => {
          const v = values[key]
          const valid = isValid(v)
          return (
            <div key={key} className="flex items-center gap-4">
              <div className="w-40 flex-shrink-0">
                <p className="text-sm font-medium text-black">{label}</p>
                <p className="text-xs text-gray-400">{description}</p>
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  min={MIN_HOURS}
                  max={MAX_HOURS}
                  step={0.5}
                  value={v}
                  onChange={(e) => handleChange(key, e.target.value)}
                  className={`w-24 border rounded-lg px-3 py-1.5 text-sm text-black focus:outline-none focus:ring-2 focus:ring-black focus:border-transparent ${
                    valid ? 'border-gray-200' : 'border-red-400'
                  }`}
                />
                <span className="text-xs text-gray-400">{formatHours(v)}</span>
              </div>
            </div>
          )
        })}
      </div>
      {error && <p className="text-xs text-red-700 mt-2">{error}</p>}
      {!allValid && (
        <p className="text-xs text-red-700 mt-2">All values must be between {MIN_HOURS} and {MAX_HOURS} hours.</p>
      )}
      <div className="flex gap-3 mt-4">
        <button
          onClick={handleSave}
          disabled={saving || !dirty || !allValid}
          className="px-3 py-1.5 rounded-lg bg-black text-white text-xs font-medium hover:bg-gray-900 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {saving ? 'Saving...' : 'Save'}
        </button>
        <button
          onClick={handleReset}
          disabled={saving}
          className="px-3 py-1.5 rounded-lg border border-gray-200 text-gray-500 hover:text-black text-xs font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Reset to defaults
        </button>
      </div>
    </div>
  )
}
