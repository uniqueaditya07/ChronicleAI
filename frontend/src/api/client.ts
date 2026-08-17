import type { HealthResponse, Case, CaseListResponse, CaseCreatePayload, ApiError, Source, SourceListResponse, SourceChunkListResponse } from '@/types/api'

const API_BASE = '/api/v1'

class ApiClient {
  private async request<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const url = `${API_BASE}${endpoint}`
    const headers = {
      'Content-Type': 'application/json',
      ...(options?.headers || {}),
    }

    try {
      const response = await fetch(url, { ...options, headers })
      
      if (!response.ok) {
        let errorData: { error?: ApiError } = {}
        try {
          errorData = await response.json()
        } catch {
          // Response was not JSON
        }
        
        const message = errorData.error?.message || `HTTP ${response.status}: ${response.statusText}`
        throw new Error(message)
      }

      if (response.status === 204) {
        return {} as T
      }

      return await response.json()
    } catch (error) {
      if (error instanceof Error) {
        throw error
      }
      throw new Error('An unexpected network error occurred.')
    }
  }

  async getHealth(): Promise<HealthResponse> {
    return this.request<HealthResponse>('/health')
  }

  async listCases(): Promise<CaseListResponse> {
    return this.request<CaseListResponse>('/cases')
  }

  async createCase(payload: CaseCreatePayload): Promise<Case> {
    return this.request<Case>('/cases', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  }

  async deleteCase(caseId: string): Promise<void> {
    return this.request<void>(`/cases/${caseId}`, {
      method: 'DELETE',
    })
  }

  // --- Sources ---
  
  async listSources(caseId: string, skip: number = 0, limit: number = 100): Promise<SourceListResponse> {
    return this.request<SourceListResponse>(`/cases/${caseId}/sources?skip=${skip}&limit=${limit}`)
  }

  async getSource(caseId: string, sourceId: string): Promise<Source> {
    return this.request<Source>(`/cases/${caseId}/sources/${sourceId}`)
  }

  async listSourceChunks(caseId: string, sourceId: string, skip: number = 0, limit: number = 100): Promise<SourceChunkListResponse> {
    return this.request<SourceChunkListResponse>(`/cases/${caseId}/sources/${sourceId}/chunks?skip=${skip}&limit=${limit}`)
  }

  async uploadSource(caseId: string, file: File): Promise<Source> {
    const url = `${API_BASE}/cases/${caseId}/sources/`
    const formData = new FormData()
    formData.append('file', file)

    // Using native fetch because we don't want 'Content-Type': 'application/json' for FormData
    const response = await fetch(url, {
      method: 'POST',
      body: formData,
    })

    if (!response.ok) {
      let errorData: { error?: ApiError } = {}
      try {
        errorData = await response.json()
      } catch {
        // Response was not JSON
      }
      
      const message = errorData.error?.message || `HTTP ${response.status}: ${response.statusText}`
      throw new Error(message)
    }

    return await response.json()
  }
}

export const api = new ApiClient()
