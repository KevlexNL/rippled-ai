import React from 'react'
import { TabNav } from './TabNav'

interface LayoutProps {
  children: React.ReactNode
}

export function Layout({ children }: LayoutProps) {
  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b px-6 py-3 flex items-center justify-between">
        <span className="font-bold text-gray-800">Rippled Admin</span>
        <span className="text-xs text-gray-400">Phase C4</span>
      </header>
      <TabNav />
      <main className="px-6 py-4">{children}</main>
    </div>
  )
}
