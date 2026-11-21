import type { Language } from '../types/visit'

export type ApprovedDangerSign = 'bleeding-during-pregnancy' | 'high-fever-in-newborn'

export interface SafetyAssessment {
  flagged: boolean
  signs: ApprovedDangerSign[]
  referralAlert: boolean
}

export interface SafetyService {
  assess(transcript: string, language?: Language): SafetyAssessment
}

const pregnancy = '(?:\\b(?:pregnan\\w*|pregnancy|antenatal| गर्भवती)\\b|ಗರ್ಭ(?:ಿಣಿ|ಧಾರಣೆ|ವಸ್ಥೆ)?|गर्भ(?:वती|ा?वस्था)?)'
const bleeding = '(?:\\b(?:bleed(?:ing)?|blood)\\b|ರಕ್ತ(?:ಸ್ರಾವ)?|ರಕ್ತಸ್ರಾವ|\\b(?:bleeding|bleedin|blood)\\s+(?:agta|aagta|ide)\\b|रक्तस्राव|खून|ब्लीडिंग|bleeding)'
const newborn = '(?:\\b(?:newborn|new born|infant|baby|neonate)\\b|ನವಜಾತ(?:\\s*ಶಿಶು)?|ಮಗು|नवजात(?:\\s*शिशु)?|शिशु|बच्चा)'
const fever = '(?:\\b(?:high\\s+fever|fever|very\\s+hot)\\b|ಹೆಚ್ಚಿನ\\s*ಜ್ವರ|ತೀವ್ರ\\s*ಜ್ವರ|ಜ್ವರ|\\b(?:jvara|jwara|bukhar|tez\\s+bukhar|tez\\s+bukhaar)\\b|तेज़?\\s*बुखार|बुखार|तेज\\s*बुखार)'

// This intentionally covers only the two danger signs approved for this workflow.
const approvedSignPatterns: Record<ApprovedDangerSign, RegExp> = {
  'bleeding-during-pregnancy': new RegExp(`(?:${pregnancy}[^.!?]{0,70}${bleeding}|${bleeding}[^.!?]{0,70}${pregnancy})`, 'i'),
  'high-fever-in-newborn': new RegExp(`(?:${newborn}[^.!?]{0,70}${fever}|${fever}[^.!?]{0,70}${newborn})`, 'i'),
}

export class MockSafetyService implements SafetyService {
  assess(transcript: string, _language?: Language): SafetyAssessment {
    const signs = (Object.entries(approvedSignPatterns) as [ApprovedDangerSign, RegExp][])
      .filter(([, pattern]) => pattern.test(transcript))
      .map(([sign]) => sign)
    return { flagged: signs.length > 0, signs, referralAlert: signs.length > 0 }
  }
}

export const safetyService: SafetyService = new MockSafetyService()
