import type { ExtractedVisit } from './extraction.service'

export interface VisitValidation {
  valid: boolean
  missingFields: Array<'beneficiaryId' | 'visitType' | 'weightKg' | 'vaccinationsDue' | 'nextVisitDate'>
}

export interface ValidationService {
  validate(visit: ExtractedVisit, options?: { dangerFlagged?: boolean }): VisitValidation
}

export class MockValidationService implements ValidationService {
  validate(visit: ExtractedVisit, options: { dangerFlagged?: boolean } = {}): VisitValidation {
    const missingFields: VisitValidation['missingFields'] = []
    if (!visit.beneficiaryId) missingFields.push('beneficiaryId')
    if (!visit.visitType) missingFields.push('visitType')
    if (visit.weightKg === null && !options.dangerFlagged) missingFields.push('weightKg')
    if (visit.vaccinationsDue === null) missingFields.push('vaccinationsDue')
    if (!visit.nextVisitDate && !options.dangerFlagged) missingFields.push('nextVisitDate')
    return { valid: missingFields.length === 0, missingFields }
  }
}

export const validationService: ValidationService = new MockValidationService()
