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

export interface ApiError {
  code: string
  message: string
  status_code: number
  details?: unknown
}
