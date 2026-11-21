import type { ApiError, SaveVisitRequest, SaveVisitResponse, SpeechEvent, VisitDraft } from '../types/visit'

export interface ApiService {
  saveVisit(request: SaveVisitRequest): Promise<SaveVisitResponse>
  connectEvents(onEvent: (event: SpeechEvent) => void, onError?: (error: ApiError) => void): () => void
}

export class MockApiService implements ApiService {
  async saveVisit(request: SaveVisitRequest): Promise<SaveVisitResponse> {
    return {
      visit: { ...request.visit },
      record_id: `demo-${request.draft_id}`,
      saved_at: new Date().toISOString(),
    }
  }

  connectEvents(_onEvent: (event: SpeechEvent) => void, _onError?: (error: ApiError) => void): () => void {
    return () => undefined
  }
}

export const apiService: ApiService = new MockApiService()
export type { VisitDraft }
