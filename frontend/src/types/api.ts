export interface HealthResponse {
  status: string
  app_name: string
  version: string
  environment: string
  database_connected: boolean
  timestamp: string
}

export interface Case {
  id: string
  name: string
  description?: string | null
  status: 'active' | 'archived' | 'deleted'
  created_at: string
  updated_at: string
}

export interface CaseListResponse {
  items: Case[]
  total: number
}

export interface CaseCreatePayload {
  name: string
  description?: string
}

export type ProcessingStatus = 'pending' | 'processing' | 'completed' | 'failed'
export type ChunkType = 'page' | 'paragraph' | 'row' | 'image_region' | 'log_entry'

export interface Source {
  id: string
  case_id: string
  original_filename: string
  file_type: string
  file_size: number
  content_hash: string
  processing_status: ProcessingStatus
  processing_error?: string | null
  metadata_json?: string | null
  created_at: string
  updated_at: string
  chunk_count: number
}

export interface SourceListResponse {
  items: Source[]
  total: number
}

export interface SourceChunk {
  id: string
  source_id: string
  chunk_type: ChunkType
  chunk_index: number
  content_text: string
  page_number?: number | null
  start_offset?: number | null
  end_offset?: number | null
  metadata_json?: string | null
  created_at: string
}

export interface SourceChunkListResponse {
  items: SourceChunk[]
  total: number
}

export interface ApiError {
  code: string
  message: string
  status_code: number
  details?: unknown
}
