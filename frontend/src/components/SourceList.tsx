import React from 'react'
import type { Source } from '@/types/api'

interface SourceListProps {
  sources: Source[]
  isLoading: boolean
  onViewChunks: (source: Source) => void
}

export const SourceList: React.FC<SourceListProps> = ({ sources, isLoading, onViewChunks }) => {
  if (isLoading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="animate-pulse flex items-center justify-between p-4 bg-[var(--surface)] border border-[var(--border)] rounded-lg">
            <div className="flex items-center gap-4">
              <div className="w-10 h-10 bg-[var(--border)] rounded-md"></div>
              <div className="space-y-2">
                <div className="h-4 bg-[var(--border)] rounded w-32"></div>
                <div className="h-3 bg-[var(--border)] rounded w-24"></div>
              </div>
            </div>
            <div className="h-8 bg-[var(--border)] rounded w-20"></div>
          </div>
        ))}
      </div>
    )
  }

  if (sources.length === 0) {
    return (
      <div className="text-center py-12 bg-[var(--surface)] border border-[var(--border)] rounded-xl border-dashed">
        <svg className="w-12 h-12 text-[var(--text-tertiary)] mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
        <p className="text-[var(--text-secondary)] font-medium">No evidence uploaded yet</p>
        <p className="text-[var(--text-tertiary)] text-sm mt-1">Upload files to begin extracting timelines</p>
      </div>
    )
  }

  const getStatusBadge = (status: Source['processing_status']) => {
    switch (status) {
      case 'completed':
        return <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-500 border border-emerald-500/20">Parsed</span>
      case 'processing':
        return <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-500/10 text-blue-500 border border-blue-500/20 animate-pulse">Processing</span>
      case 'failed':
        return <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-500/10 text-red-500 border border-red-500/20">Failed</span>
      default:
        return <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-500/10 text-gray-500 border border-gray-500/20">Pending</span>
    }
  }

  return (
    <div className="space-y-3">
      {sources.map((source) => (
        <div 
          key={source.id} 
          className="flex items-center justify-between p-4 bg-[var(--surface)] border border-[var(--border)] rounded-lg hover:border-[var(--text-secondary)] transition-colors group"
        >
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 rounded-md bg-[var(--primary)]/10 flex items-center justify-center text-[var(--primary)] font-medium text-xs uppercase">
              {source.file_type}
            </div>
            <div>
              <h4 className="font-medium text-[var(--text-primary)] text-sm">{source.original_filename}</h4>
              <div className="flex items-center gap-3 mt-1 text-xs text-[var(--text-secondary)]">
                <span>{(source.file_size / 1024).toFixed(1)} KB</span>
                <span className="w-1 h-1 rounded-full bg-[var(--text-tertiary)]"></span>
                <span>{source.chunk_count} chunks</span>
                <span className="w-1 h-1 rounded-full bg-[var(--text-tertiary)]"></span>
                <span>{new Date(source.created_at).toLocaleDateString()}</span>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-4">
            {getStatusBadge(source.processing_status)}
            <button
              onClick={() => onViewChunks(source)}
              disabled={source.processing_status !== 'completed'}
              className="px-3 py-1.5 text-xs font-medium bg-[var(--background)] border border-[var(--border)] rounded-md hover:text-[var(--primary)] hover:border-[var(--primary)] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              View Chunks
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}
