import React, { useState, useEffect, useCallback } from 'react'
import { api } from '@/api/client'
import type { Source, Case } from '@/types/api'
import { SourceList } from './SourceList'
import { SourceUploadModal } from './SourceUploadModal'
import { ChunkViewerModal } from './ChunkViewerModal'
import { ArrowLeft, Upload, RefreshCw } from 'lucide-react'

interface EvidenceManagerProps {
  caseRecord: Case
  onBack: () => void
}

export const EvidenceManager: React.FC<EvidenceManagerProps> = ({ caseRecord, onBack }) => {
  const [sources, setSources] = useState<Source[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isUploadOpen, setIsUploadOpen] = useState(false)
  const [selectedSource, setSelectedSource] = useState<Source | null>(null)
  
  const loadSources = useCallback(async () => {
    try {
      setIsLoading(true)
      const data = await api.listSources(caseRecord.id)
      setSources(data.items)
    } catch (err) {
      console.error('Failed to load sources:', err)
    } finally {
      setIsLoading(false)
    }
  }, [caseRecord.id])

  useEffect(() => {
    loadSources()
  }, [loadSources])

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white border border-[var(--border)] rounded-xl p-6 shadow-xs">
        <div className="flex items-center gap-4 mb-4">
          <button 
            onClick={onBack}
            className="p-1.5 hover:bg-slate-100 rounded-md text-slate-500 transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h2 className="text-xl font-bold text-slate-900 flex items-center gap-2">
              Evidence Management
            </h2>
            <p className="text-sm text-slate-500">{caseRecord.name}</p>
          </div>
        </div>

        <div className="flex items-center justify-between mt-6">
          <div className="flex gap-2">
            <button
              onClick={loadSources}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[var(--border)] bg-white hover:bg-slate-50 text-slate-700 text-xs font-medium transition-colors"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Refresh
            </button>
          </div>
          <button
            onClick={() => setIsUploadOpen(true)}
            className="inline-flex items-center gap-1.5 px-4 py-2 bg-[var(--primary)] hover:bg-[var(--primary-hover)] text-white rounded-lg text-sm font-medium transition-colors shadow-sm"
          >
            <Upload className="w-4 h-4" />
            Upload Evidence
          </button>
        </div>
      </div>

      {/* Main Content */}
      <div className="bg-white border border-[var(--border)] rounded-xl p-6 shadow-xs min-h-[400px]">
        <h3 className="text-sm font-semibold text-slate-900 mb-4">Ingested Sources ({sources.length})</h3>
        <SourceList 
          sources={sources} 
          isLoading={isLoading} 
          onViewChunks={(source) => setSelectedSource(source)} 
        />
      </div>

      {/* Modals */}
      <SourceUploadModal
        caseId={caseRecord.id}
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        onUploadSuccess={() => {
          loadSources()
        }}
      />

      {selectedSource && (
        <ChunkViewerModal
          caseId={caseRecord.id}
          source={selectedSource}
          isOpen={!!selectedSource}
          onClose={() => setSelectedSource(null)}
        />
      )}
    </div>
  )
}
