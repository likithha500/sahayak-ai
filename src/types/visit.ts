export type Language = 'kn' | 'hi' | 'en'
export type VisitStatus = 'draft' | 'pending' | 'confirmed' | 'flagged'
export type ApiErrorCode = 'VALIDATION_ERROR' | 'UNAUTHORIZED' | 'NOT_FOUND' | 'CONFLICT' | 'UNAVAILABLE'

export interface VisitRecord {
  id: string
  draftId: string
  beneficiaryId: string
  type: string
  date: string
  nextDate: string
  status: string
  danger: boolean
  dangerFlags: string[]
  weight: string
  vaccines: string
  notes: string
}

export interface VisitDraft {
  beneficiary_id: string
  visit_type: string
  weight_kg: number | null
  vaccinations_due: string[]
  next_visit_date: string | null
  original_transcript: string
  preferred_language: Language
  detected_input_language: Language | null
  danger_flags: string[]
  confirmation_status: VisitStatus
}

export interface ApiError {
  code: ApiErrorCode
  message: string
  field?: string
}

export interface SaveVisitRequest { draft_id: string; visit: VisitDraft }
export interface SaveVisitResponse { visit: VisitDraft; record_id: string; saved_at: string }

export type SpeechEvent =
  | { type: 'connection'; payload: { state: 'connecting' | 'connected' | 'disconnected' }; timestamp: string }
  | { type: 'partial_transcript'; payload: { text: string; detected_language: Language | null }; timestamp: string }
  | { type: 'final_transcript'; payload: { text: string; detected_language: Language | null }; timestamp: string }
  | { type: 'extraction_completed'; payload: { visit: Partial<VisitDraft> }; timestamp: string }
  | { type: 'danger_alert'; payload: { signs: string[]; referral_required: true }; timestamp: string }
  | { type: 'readback_audio'; payload: { url?: string; text?: string }; timestamp: string }
  | { type: 'correction_result'; payload: { field: string; value: string }; timestamp: string }
  | { type: 'error'; payload: { code: ApiErrorCode; message: string }; timestamp: string }
