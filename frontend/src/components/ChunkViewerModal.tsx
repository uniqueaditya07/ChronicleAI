import React, { useState, useEffect } from 'react'
import { api } from '@/api/client'
import type { Source, SourceChunk } from '@/types/api'

interface ChunkViewerModalProps {
  caseId: string
  source: Source
  isOpen: boolean
  onClose: () => void
}

export const ChunkViewerModal: React.FC<ChunkViewerModalProps> = ({
  caseId,
  source,
  isOpen,
  onClose,
}) => {
  const [chunks, setChunks] = useState<SourceChunk[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (isOpen && source) {
      loadChunks()
    }
  }, [isOpen, source])

  const loadChunks = async () => {
    try {
      setIsLoading(true)
      const data = await api.listSourceChunks(caseId, source.id)
      setChunks(data.items)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load chunks')
    } finally {
      setIsLoading(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4 md:p-8">
      <div className="bg-[var(--surface)] w-full max-w-4xl h-full max-h-[85vh] rounded-xl border border-[var(--border)] shadow-2xl flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--border)] bg-[var(--background)]">
          <div>
            <h2 className="text-lg font-semibold text-[var(--text-primary)]">Parsed Evidence Chunks</h2>
            <p className="text-sm text-[var(--text-secondary)] mt-0.5">{source.original_filename}</p>
          </div>
          <button
            onClick={onClose}
            className="text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors p-1"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 bg-[var(--background)]">
          {isLoading ? (
            <div className="flex items-center justify-center h-full">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--primary)]"></div>
            </div>
          ) : error ? (
            <div className="p-4 text-red-400 bg-red-400/10 border border-red-400/20 rounded-md">
              {error}
            </div>
          ) : chunks.length === 0 ? (
            <div className="text-center py-12">
              <p className="text-[var(--text-secondary)]">No chunks found for this file.</p>
            </div>
          ) : (
            <div className="space-y-4">
              {chunks.map((chunk) => (
                <div key={chunk.id} className="bg-[var(--surface)] border border-[var(--border)] rounded-lg p-4">
                  <div className="flex items-center justify-between mb-3 pb-2 border-b border-[var(--border)]/50">
                    <div className="flex items-center gap-3">
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-[var(--primary)]/10 text-[var(--primary)]">
                        {chunk.chunk_type}
                      </span>
                      <span className="text-xs text-[var(--text-tertiary)] font-mono">
                        #{chunk.chunk_index}
                      </span>
                    </div>
                    {chunk.page_number && (
                      <span className="text-xs text-[var(--text-secondary)]">
                        Page {chunk.page_number}
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-[var(--text-primary)] whitespace-pre-wrap font-mono leading-relaxed">
                    {chunk.content_text}
                  </p>
                  {chunk.metadata_json && (
                    <div className="mt-4 pt-3 border-t border-[var(--border)]/50">
                      <details className="text-xs text-[var(--text-secondary)]">
                        <summary className="cursor-pointer hover:text-[var(--text-primary)]">View Metadata</summary>
                        <pre className="mt-2 p-2 bg-[var(--background)] rounded text-[10px] overflow-x-auto">
                          {JSON.stringify(JSON.parse(chunk.metadata_json), null, 2)}
                        </pre>
                      </details>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
