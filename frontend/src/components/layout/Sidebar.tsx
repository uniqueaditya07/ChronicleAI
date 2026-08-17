import React from 'react'
import {
  FolderKanban,
  FileText,
  Clock,
  Network,
  AlertTriangle,
  Search,
  BookOpen,
  Layers,
} from 'lucide-react'

export const Sidebar: React.FC = () => {
  const navItems = [
    { label: 'Foundation & Overview', icon: Layers, active: true, phase: 'Phase 0' },
    { label: 'Evidence Ingestion', icon: FileText, disabled: true, phase: 'Phase 1' },
    { label: 'Entity & Event Extraction', icon: FolderKanban, disabled: true, phase: 'Phase 2' },
    { label: 'Reconstructed Timeline', icon: Clock, disabled: true, phase: 'Phase 3' },
    { label: 'Evidence Graph & Provenance', icon: Network, disabled: true, phase: 'Phase 4' },
    { label: 'Contradiction Engine', icon: AlertTriangle, disabled: true, phase: 'Phase 5' },
    { label: 'Investigation Agent', icon: Search, disabled: true, phase: 'Phase 6 (Stretch)' },
    { label: 'Reports & Export', icon: BookOpen, disabled: true, phase: 'Phase 7' },
  ]

  return (
    <aside className="w-64 border-r border-slate-200 bg-white flex flex-col justify-between p-4 shrink-0">
      <div>
        <div className="px-3 py-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
          Phased Navigation
        </div>
        <nav className="mt-2 space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon
            return (
              <div
                key={item.label}
                className={`flex items-center justify-between px-3 py-2.5 rounded-lg text-xs font-medium transition-colors ${
                  item.active
                    ? 'bg-slate-900 text-white shadow-xs'
                    : 'text-slate-400 cursor-not-allowed opacity-60'
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <Icon className="w-4 h-4" />
                  <span>{item.label}</span>
                </div>
                <span
                  className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${
                    item.active ? 'bg-slate-800 text-slate-200' : 'bg-slate-100 text-slate-400'
                  }`}
                >
                  {item.phase}
                </span>
              </div>
            )
          })}
        </nav>
      </div>

      <div className="border-t border-slate-100 pt-4 px-2">
        <div className="text-[11px] text-slate-500 font-mono">
          <div>Core Rule: EVIDENCE ≠ INFERENCE</div>
          <div className="mt-1 text-slate-400">Status: Phase 0 Foundation</div>
        </div>
      </div>
    </aside>
  )
}
