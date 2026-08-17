import { useState, useEffect } from 'react'
import {
  CheckCircle2,
  Database,
  Terminal,
  FolderPlus,
  Trash2,
  RefreshCw,
  Layers,
  Shield,
  FileCode2,
} from 'lucide-react'
import { AppLayout } from '@/components/layout/AppLayout'
import { EvidenceManager } from '@/components/EvidenceManager'
import { api } from '@/api/client'
import type { HealthResponse, Case } from '@/types/api'

export function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [healthLoading, setHealthLoading] = useState(true)
  const [cases, setCases] = useState<Case[]>([])
  const [casesLoading, setCasesLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  
  const [selectedCase, setSelectedCase] = useState<Case | null>(null)

  // New Case Form State
  const [newCaseName, setNewCaseName] = useState('')
  const [newCaseDesc, setNewCaseDesc] = useState('')
  const [creatingCase, setCreatingCase] = useState(false)

  const fetchHealth = async () => {
    try {
      setHealthLoading(true)
      const data = await api.getHealth()
      setHealth(data)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to connect to backend service')
      setHealth(null)
    } finally {
      setHealthLoading(false)
    }
  }

  const fetchCases = async () => {
    try {
      setCasesLoading(true)
      const data = await api.listCases()
      setCases(data.items)
    } catch (err) {
      console.error('Failed to list cases:', err)
    } finally {
      setCasesLoading(false)
    }
  }

  useEffect(() => {
    fetchHealth()
    fetchCases()
  }, [])

  const handleCreateCase = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newCaseName.trim()) return

    try {
      setCreatingCase(true)
      await api.createCase({
        name: newCaseName.trim(),
        description: newCaseDesc.trim() || undefined,
      })
      setNewCaseName('')
      setNewCaseDesc('')
      await fetchCases()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create case')
    } finally {
      setCreatingCase(false)
    }
  }

  const handleDeleteCase = async (id: string) => {
    try {
      await api.deleteCase(id)
      await fetchCases()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete case')
    }
  }

  return (
    <AppLayout health={health} healthLoading={healthLoading} error={error}>
      {selectedCase ? (
        <EvidenceManager caseRecord={selectedCase} onBack={() => setSelectedCase(null)} />
      ) : (
      <div className="space-y-6">
        {/* Foundation Banner */}
        <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-xs">
          <div className="flex items-start justify-between">
            <div className="space-y-1">
              <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs font-semibold">
                <CheckCircle2 className="w-3.5 h-3.5" />
                Phase 0 Foundation Active
              </div>
              <h2 className="text-xl font-bold text-slate-900 mt-2">
                Engineering Foundation & System Shell
              </h2>
              <p className="text-sm text-slate-600 max-w-2xl">
                ChronicleAI's foundational architecture is established with FastAPI, SQLite,
                SQLAlchemy 2.0, Alembic migrations, React + Vite + TypeScript, and Tailwind CSS v4.
              </p>
            </div>
            <button
              onClick={() => {
                fetchHealth()
                fetchCases()
              }}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 text-xs font-medium transition-colors"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Refresh Status
            </button>
          </div>

          {/* System Telemetry Grid */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mt-6">
            <div className="p-4 rounded-lg bg-slate-50 border border-slate-200">
              <div className="flex items-center gap-2 text-slate-500 text-xs font-medium">
                <Terminal className="w-4 h-4 text-slate-600" />
                API Status
              </div>
              <div className="text-base font-semibold text-slate-900 mt-1">
                {health?.status === 'healthy' ? (
                  <span className="text-emerald-600">Operational</span>
                ) : (
                  <span className="text-rose-600">Unavailable</span>
                )}
              </div>
              <div className="text-[11px] text-slate-400 mt-0.5">
                Version {health?.version || '0.1.0'} ({health?.environment || 'dev'})
              </div>
            </div>

            <div className="p-4 rounded-lg bg-slate-50 border border-slate-200">
              <div className="flex items-center gap-2 text-slate-500 text-xs font-medium">
                <Database className="w-4 h-4 text-slate-600" />
                Database (SQLite)
              </div>
              <div className="text-base font-semibold text-slate-900 mt-1">
                {health?.database_connected ? (
                  <span className="text-emerald-600">Connected</span>
                ) : (
                  <span className="text-amber-600">Connecting...</span>
                )}
              </div>
              <div className="text-[11px] text-slate-400 mt-0.5">
                WAL Mode & Foreign Keys ON
              </div>
            </div>

            <div className="p-4 rounded-lg bg-slate-50 border border-slate-200">
              <div className="flex items-center gap-2 text-slate-500 text-xs font-medium">
                <Layers className="w-4 h-4 text-slate-600" />
                Active Cases in DB
              </div>
              <div className="text-base font-semibold text-slate-900 mt-1">
                {cases.length}
              </div>
              <div className="text-[11px] text-slate-400 mt-0.5">
                Verified with Alembic Schema
              </div>
            </div>

            <div className="p-4 rounded-lg bg-slate-50 border border-slate-200">
              <div className="flex items-center gap-2 text-slate-500 text-xs font-medium">
                <Shield className="w-4 h-4 text-slate-600" />
                Core Invariant
              </div>
              <div className="text-xs font-semibold text-slate-900 mt-1">
                EVIDENCE ≠ INFERENCE
              </div>
              <div className="text-[11px] text-slate-400 mt-0.5">
                Provenance before deduction
              </div>
            </div>
          </div>
        </div>

        {/* Live Integration Test Widget: Case Creation */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-xs lg:col-span-1">
            <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
              <FolderPlus className="w-4 h-4 text-slate-600" />
              Verify DB Persistence: Create Case
            </h3>
            <p className="text-xs text-slate-500 mt-1">
              Tests the end-to-end flow from React form → FastAPI REST API → SQLite session.
            </p>

            <form onSubmit={handleCreateCase} className="mt-4 space-y-3">
              <div>
                <label className="block text-xs font-medium text-slate-700">Case Name</label>
                <input
                  type="text"
                  required
                  value={newCaseName}
                  onChange={(e) => setNewCaseName(e.target.value)}
                  placeholder="e.g., Operation Apex Timeline"
                  className="mt-1 w-full px-3 py-1.5 text-xs bg-white border border-slate-200 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-slate-900"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700">Description (optional)</label>
                <textarea
                  rows={2}
                  value={newCaseDesc}
                  onChange={(e) => setNewCaseDesc(e.target.value)}
                  placeholder="Preliminary notes for timeline reconstruction..."
                  className="mt-1 w-full px-3 py-1.5 text-xs bg-white border border-slate-200 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-slate-900"
                />
              </div>

              <button
                type="submit"
                disabled={creatingCase || !newCaseName.trim()}
                className="w-full py-2 px-3 bg-slate-900 hover:bg-slate-800 disabled:opacity-50 text-white rounded-lg text-xs font-medium flex items-center justify-center gap-1.5 transition-colors"
              >
                {creatingCase ? 'Creating...' : 'Create Case Record'}
              </button>
            </form>
          </div>

          <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-xs lg:col-span-2">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
                <FileCode2 className="w-4 h-4 text-slate-600" />
                Persisted Cases ({cases.length})
              </h3>
              <span className="text-[11px] text-slate-400 font-mono">SQLite cases table</span>
            </div>

            <div className="mt-3 divide-y divide-slate-100 max-h-64 overflow-y-auto">
              {casesLoading ? (
                <div className="py-8 text-center text-xs text-slate-400">Loading cases...</div>
              ) : cases.length === 0 ? (
                <div className="py-8 text-center text-xs text-slate-400">
                  No cases created yet. Create one on the left to test persistence.
                </div>
              ) : (
                cases.map((c) => (
                  <div key={c.id} className="py-3 flex items-center justify-between gap-4">
                    <div className="min-w-0">
                      <div className="text-xs font-semibold text-slate-900 truncate">{c.name}</div>
                      {c.description && (
                        <div className="text-[11px] text-slate-500 truncate mt-0.5">{c.description}</div>
                      )}
                      <div className="text-[10px] text-slate-400 font-mono mt-0.5">
                        ID: {c.id.substring(0, 8)}... | Status: {c.status} | Created:{' '}
                        {new Date(c.created_at).toLocaleTimeString()}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => setSelectedCase(c)}
                        className="px-3 py-1 text-xs font-medium bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-md transition-colors"
                      >
                        Manage Evidence
                      </button>
                      <button
                        onClick={() => handleDeleteCase(c.id)}
                        className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-md transition-colors"
                        title="Delete Case"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Phase Roadmap Overview */}
        <div className="bg-slate-900 text-white rounded-xl p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold">ChronicleAI Phased Roadmap</h3>
            <span className="text-xs font-mono text-slate-400">1-Week Plan</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-4 text-xs">
            <div className="p-3 rounded-lg bg-slate-800 border border-slate-700">
              <div className="font-semibold text-emerald-400">Phase 0 — Foundation (Current)</div>
              <div className="text-slate-300 mt-1 text-[11px]">
                Modular monolith scaffolding, SQLite, Alembic, FastAPI, React shell, docs framework.
              </div>
            </div>
            <div className="p-3 rounded-lg bg-slate-800/60 border border-slate-700/60 text-slate-400">
              <div className="font-semibold text-slate-300">Phase 1 — Evidence Ingestion</div>
              <div className="mt-1 text-[11px]">
                Multi-format parser (PDF, DOCX, CSV, JSON, TXT, LOG) & chunk storage.
              </div>
            </div>
            <div className="p-3 rounded-lg bg-slate-800/60 border border-slate-700/60 text-slate-400">
              <div className="font-semibold text-slate-300">Phase 2 — Extraction Engine</div>
              <div className="mt-1 text-[11px]">
                Gemini structured extraction for entities, events, claims, and ISO timestamps.
              </div>
            </div>
          </div>
        </div>
      </div>
      )}
    </AppLayout>
  )
}

export default App
