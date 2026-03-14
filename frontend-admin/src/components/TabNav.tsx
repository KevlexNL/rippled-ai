import React from 'react'
import { NavLink } from 'react-router-dom'

const tabs = [
  { to: '/', label: 'Health', end: true },
  { to: '/commitments', label: 'Commitments' },
  { to: '/candidates', label: 'Candidates' },
  { to: '/events', label: 'Events' },
  { to: '/surfacing', label: 'Surfacing' },
  { to: '/digests', label: 'Digests' },
  { to: '/pipeline', label: 'Pipeline' },
]

export function TabNav() {
  return (
    <nav className="bg-white border-b px-6 flex gap-1">
      {tabs.map(t => (
        <NavLink
          key={t.to}
          to={t.to}
          end={t.end}
          className={({ isActive }) =>
            `px-3 py-2 text-sm font-medium border-b-2 ${
              isActive ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-600 hover:text-gray-900'
            }`
          }
        >
          {t.label}
        </NavLink>
      ))}
    </nav>
  )
}
