import React from 'react'
import { TopBar } from './TopBar'
import { Sidebar } from './Sidebar'
import type { HealthResponse } from '@/types/api'

interface AppLayoutProps {
  health: HealthResponse | null
  healthLoading: boolean
  error: string | null
  children: React.ReactNode
}

export const AppLayout: React.FC<AppLayoutProps> = ({
  health,
  healthLoading,
  error,
  children,
}) => {
  return (
    <div className="min-h-screen flex flex-col bg-slate-50 text-slate-900 font-sans">
      <TopBar health={health} healthLoading={healthLoading} error={error} />
      <div className="flex-1 flex overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-y-auto p-8">
          <div className="max-w-6xl mx-auto">{children}</div>
        </main>
      </div>
    </div>
  )
}
