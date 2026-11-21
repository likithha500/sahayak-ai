import assert from 'node:assert/strict'
import test from 'node:test'
import { scenarios } from '../data/mock.ts'
import { extractionService } from './extraction.service.ts'
import { safetyService } from './safety.service.ts'

test('configured danger signs are recognized across Kannada, Hindi, English, and code-mixed speech', () => {
  const cases = [
    ['Pregnant woman ge bleeding agta ide.', 'bleeding-during-pregnancy'],
    ['ಗರ್ಭಿಣಿಗೆ ರಕ್ತಸ್ರಾವ ಇದೆ', 'bleeding-during-pregnancy'],
    ['गर्भावस्था में खून आ रहा है', 'bleeding-during-pregnancy'],
    ['Newborn baby ko high fever hai.', 'high-fever-in-newborn'],
    ['ನವಜಾತ ಶಿಶುವಿಗೆ ಹೆಚ್ಚಿನ ಜ್ವರ ಇದೆ', 'high-fever-in-newborn'],
    ['नवजात शिशु को तेज बुखार है', 'high-fever-in-newborn'],
  ]

  for (const [transcript, expected] of cases) {
    const assessment = safetyService.assess(transcript)
    assert.equal(assessment.flagged, true, transcript)
    assert.equal(assessment.referralAlert, true, transcript)
    assert.ok(assessment.signs.includes(expected), transcript)
  }
})

test('danger detection stays limited to configured signs', () => {
  for (const transcript of ['Headache during pregnancy', 'newborn feeding normally', 'maternal visit completed']) {
    assert.deepEqual(safetyService.assess(transcript).signs, [])
  }
})

test('all seven demo scenarios preserve their configured danger flags', () => {
  assert.equal(scenarios.length, 7)
  for (const scenario of scenarios) {
    assert.equal(safetyService.assess(scenario.transcript).flagged, scenario.danger, scenario.id)
  }
})

test('extracts beneficiary, weight, and a deterministic relative date', () => {
  const result = extractionService.extract('Beneficiary 205 newborn baby weight 2.8 kilo hai. Next visit tomorrow.')
  assert.equal(result.beneficiaryId, 'AS-205')
  assert.equal(result.visitType, 'Newborn visit')
  assert.equal(result.weightKg, 2.8)
  assert.equal(result.nextVisitDate, '2026-11-21')
})

test('Monday resolves against the fixed demo date without inventing unspecified details', () => {
  const result = extractionService.extract('beneficiary 102 ANC checkup. Next visit Monday.')
  assert.equal(result.beneficiaryId, 'AS-102')
  assert.equal(result.visitType, 'Pregnancy visit')
  assert.equal(result.weightKg, null)
  assert.equal(result.vaccinationsDue, null)
  assert.equal(result.nextVisitDate, '2026-11-23')
})

test('local persistence upserts corrections without duplicating a visit or losing danger flags', async () => {
  const values = new Map()
  globalThis.window = { localStorage: { getItem: (key) => values.get(key) ?? null, setItem: (key, value) => values.set(key, value) } }
  const { mockVisitStore } = await import('./mock.service.ts')
  const original = { id: 'V-demo', draftId: 'draft-demo', beneficiaryId: 'AS-205', type: 'Newborn visit', date: '20 Nov 2026', nextDate: '', status: 'Flagged', danger: true, dangerFlags: ['high-fever-in-newborn'], weight: '', vaccines: '', notes: '' }
  mockVisitStore.save(original)
  mockVisitStore.save({ ...original, weight: '2.8', notes: 'Corrected value' })
  const saved = mockVisitStore.list()
  assert.equal(saved.length, 1)
  assert.equal(saved[0].weight, '2.8')
  assert.equal(saved[0].notes, 'Corrected value')
  assert.equal(saved[0].danger, true)
  assert.deepEqual(saved[0].dangerFlags, ['high-fever-in-newborn'])
})
