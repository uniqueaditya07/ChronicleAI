import React from 'react'
import { Activity, Server, AlertCircle } from 'lucide-react'
import type { HealthResponse } from '@/types/api'

interface TopBarProps {
  health: HealthResponse | null
  healthLoading: boolean
  error: string | null
}

export const TopBar: React.FC<TopBarProps> = ({ health, healthLoading, error }) => {
  return (
    <header className="h-14 border-b border-slate-200 bg-white px-6 flex items-center justify-between sticky top-0 z-10 shadow-xs">
      <div className="flex items-center gap-3">
        <div className="h-8 w-8 rounded-lg bg-slate-900 flex items-center justify-center text-white font-semibold text-sm shadow-sm">
          CA
        </div>
        <div>
          <h1 className="text-base font-semibold text-slate-900 leading-none">ChronicleAI</h1>
          <p className="text-xs text-slate-500 mt-0.5">Timeline Reconstruction & Investigation System</p>
        </div>
      </div>

      <div className="flex items-center gap-4">
        {error && (
          <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-rose-50 border border-rose-200 text-rose-700 text-xs font-medium">
            <AlertCircle className="w-3.5 h-3.5 text-rose-500" />
            <span>Connection Error</span>
          </div>
        )}

        <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-slate-50 border border-slate-200 text-xs">
          <Server className="w-3.5 h-3.5 text-slate-500" />
          <span className="text-slate-600 font-medium">Backend:</span>
          {healthLoading ? (
            <span className="text-slate-400">checking...</span>
          ) : health?.status === 'healthy' ? (
            <span className="inline-flex items-center gap-1 text-emerald-600 font-medium">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
              Connected (v{health.version})
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 text-rose-600 font-medium">
              <span className="w-2 h-2 rounded-full bg-rose-500"></span>
              Disconnected
            </span>
          )}
        </div>

        <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-slate-50 border border-slate-200 text-xs">
          <Activity className="w-3.5 h-3.5 text-slate-500" />
          <span className="text-slate-600 font-medium">DB:</span>
          {health?.database_connected ? (
            <span className="text-emerald-600 font-medium">SQLite Active</span>
          ) : (
            <span className="text-slate-400">Pending</span>
          )}
        </div>
      </div>
    </header>
  )
}
