import type { Language } from '../types/visit'

export interface ExtractedVisit {
  beneficiaryId: string | null
  visitType: string | null
  weightKg: number | null
  vaccinationsDue: string[] | null
  nextVisitDate: string | null
}

export interface ExtractionService {
  extract(transcript: string, language?: Language): ExtractedVisit
}

const visitTypes = [
  { label: 'Pregnancy visit', pattern: /\b(anc|pregnan\w*|antenatal|maternal)\b|ಗರ್ಭ|ಗರ್ಭಿಣಿ|ಗರ್ಭಧಾರಣೆ|गर्भ|गर्भवती|प्रेग्न/i },
  { label: 'Newborn visit', pattern: /\b(newborn|new born|baby|infant|newly born)\b|ನವಜಾತ|ನವಜಾತ ಶಿಶು|ಮಗು|शिशु|नवजात|बच्चा|नया जन्म/i },
  { label: 'Immunisation visit', pattern: /\b(immuni[sz]\w*|vaccinat\w*|vaccine)\b|ಲಸಿಕೆ|ಟೀಕಾಕರಣ|टीका|टीकाकरण|टीके/i },
]

const monthNames: Record<string, string> = {
  jan: '01', january: '01', feb: '02', february: '02', mar: '03', march: '03', apr: '04', april: '04',
  may: '05', jun: '06', june: '06', jul: '07', july: '07', aug: '08', august: '08', sep: '09', september: '09',
  oct: '10', october: '10', nov: '11', november: '11', dec: '12', december: '12',
}

const DEMO_TODAY = new Date(Date.UTC(2026, 10, 20))

function formatDate(date: Date): string {
  return `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, '0')}-${String(date.getUTCDate()).padStart(2, '0')}`
}

function parseDate(transcript: string): string | null {
  const iso = transcript.match(/\b(20\d{2})-(\d{2})-(\d{2})\b/)
  if (iso) return iso[0]

  const numeric = transcript.match(/\b(\d{1,2})[/.-](\d{1,2})[/.-](20\d{2})\b/)
  if (numeric) return `${numeric[3]}-${numeric[2].padStart(2, '0')}-${numeric[1].padStart(2, '0')}`

  const named = transcript.match(/\b(\d{1,2})\s+(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b(?:\s+(20\d{2}))?/i)
  if (named?.[3]) return `${named[3]}-${monthNames[named[2].toLowerCase()]}-${named[1].padStart(2, '0')}`

  const relativeDay = /\b(tomorrow|tomorrow morning|कल|कल सुबह|ನಾಳೆ|ನಾಳೆ ಬೆಳಗ್ಗೆ)\b/i.test(transcript)
  if (relativeDay) {
    const date = new Date(DEMO_TODAY)
    date.setUTCDate(date.getUTCDate() + 1)
    return formatDate(date)
  }
  if (/\b(monday|सोमवार|ಸೋಮವಾರ)\b/i.test(transcript)) {
    const date = new Date(DEMO_TODAY)
    const daysUntilMonday = (8 - date.getUTCDay()) % 7 || 7
    date.setUTCDate(date.getUTCDate() + daysUntilMonday)
    return formatDate(date)
  }
  return null
}

export class MockExtractionService implements ExtractionService {
  extract(transcript: string, _language?: Language): ExtractedVisit {
    const beneficiaryMatch = transcript.match(/\b(?:beneficiary\s*(?:id\s*)?)?(?:AS\s*[- ]?)?(\d{3})\b/i)
    const beneficiaryId = beneficiaryMatch ? `AS-${beneficiaryMatch[1]}` : null
    const visitType = visitTypes.find(({ pattern }) => pattern.test(transcript))?.label ?? null
    const weightMatch = transcript.match(/\b(?:weight\s*)?(\d+(?:\.\d+)?)\s*(?:kg|kilo(?:gram)?s?|ಕೆಜಿ|ಕಿಲೋ|किलो|किग्रा)\b/i)
    const weightKg = weightMatch ? Number(weightMatch[1]) : null

    const vaccineMatch = transcript.match(/(?:vaccinations? due|vaccines? due|due vaccines?|ಲಸಿಕೆ(?:ಗಳು)?(?: ಬಾಕಿ)?|ಬಾಕಿ ಲಸಿಕೆ|टीके? बाकी|टीकाकरण बाकी)\s*(?:is|are|:|ಇದೆ|ಇವೆ|है|हैं)?\s*([^.!?]+)/i)
      || transcript.match(/\b([A-Za-z][A-Za-z -]{0,35}?)\s+due\b/i)
    const vaccinationsDue = vaccineMatch?.[1]?.trim()
      ? vaccineMatch[1].trim().split(/\s*(?:,| and | ಮತ್ತು | और )\s*/i).filter(Boolean)
      : null

    return { beneficiaryId, visitType, weightKg, vaccinationsDue, nextVisitDate: parseDate(transcript) }
  }
}

export const extractionService: ExtractionService = new MockExtractionService()
