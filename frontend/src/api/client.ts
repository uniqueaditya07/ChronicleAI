import type { HealthResponse, Case, CaseListResponse, CaseCreatePayload, ApiError } from '@/types/api'

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
}

export const api = new ApiClient()
