'use client'

import { useEffect, useMemo, useState } from 'react'
import { beneficiaries, scenarios, type Beneficiary, type Scenario } from '@/src/data/mock'
import { mockVisitStore } from '@/src/services/mock.service'
import { extractionService } from '@/src/services/extraction.service'
import { safetyService } from '@/src/services/safety.service'
import type { VisitRecord } from '@/src/types/visit'
import type { Language } from '@/src/data/translations'

export type AppPage = 'home' | 'people' | 'follow' | 'history' | 'profile' | 'voice' | 'record' | 'review' | 'saved'

const visitTypeFor = (beneficiary: Beneficiary) => beneficiary.category === 'Pregnant' ? 'Pregnancy visit' : 'Newborn visit'

export function useSahayakApp() {
  const [lang, setLang] = useState<Language>('kn')
  const [page, setPage] = useState<AppPage>('home')
  const [selected, setSelected] = useState<Beneficiary>(beneficiaries[1])
  const [filter, setFilter] = useState('All')
  const [followFilter, setFollowFilter] = useState('All')
  const [query, setQuery] = useState('')
  const [historyQuery, setHistoryQuery] = useState('')
  const [scenario, setScenario] = useState<Scenario>(scenarios[1])
  const [recording, setRecording] = useState(false)
  const [, setSeconds] = useState(0)
  const [weight, setWeight] = useState('')
  const [visitType, setVisitType] = useState(visitTypeFor(beneficiaries[1]))
  const [vaccines, setVaccines] = useState('')
  const [nextDate, setNextDate] = useState('')
  const [notes, setNotes] = useState('')
  const [savedRecords, setSavedRecords] = useState<VisitRecord[]>([])
  const [draftId, setDraftId] = useState(() => crypto.randomUUID())
  const [confirmed, setConfirmed] = useState(false)
  const [dangerAcknowledged, setDangerAcknowledged] = useState(false)
  const [correction, setCorrection] = useState(false)
  const [correctionField, setCorrectionField] = useState<'weight' | 'vaccines' | 'nextDate' | 'notes'>('weight')
  const [correctionValue, setCorrectionValue] = useState('')
  useEffect(() => { setSavedRecords(mockVisitStore.list()) }, [])
  const [mobileMenu, setMobileMenu] = useState(false)
  const [readback, setReadback] = useState(false)

  const filtered = useMemo(() => beneficiaries.filter((beneficiary) =>
    (filter === 'All' || beneficiary.category === filter) &&
    `${beneficiary.id} ${beneficiary.name}`.toLowerCase().includes(query.toLowerCase())), [filter, query])

  const safetyAssessment = safetyService.assess(scenario.transcript, scenario.lang as 'kn' | 'hi' | 'en')
  const danger = safetyAssessment.flagged
  const navigate = (nextPage: AppPage) => { if (nextPage === 'record') setConfirmed(false); setPage(nextPage); setMobileMenu(false) }
  const chooseBeneficiary = (beneficiary: Beneficiary) => {
    setSelected(beneficiary)
    setVisitType(visitTypeFor(beneficiary))
  }
  const chooseVisitType = (type: string) => {
    setVisitType(type)
    const category = type.includes('Pregnancy') ? 'Pregnant' : 'Newborn'
    if (selected.category !== category) {
      const matchingBeneficiary = beneficiaries.find((person) => person.category === category)
      if (matchingBeneficiary) setSelected(matchingBeneficiary)
    }
  }
  const begin = (beneficiary = selected, requestedVisitType?: string) => {
    setSelected(beneficiary)
    const defaultType = visitTypeFor(beneficiary)
    setScenario(scenarios.find((sample) => sample.type === defaultType) || scenarios[0])
    setWeight('')
    setVaccines('')
    setNextDate('')
    setNotes('')
    setVisitType(requestedVisitType || visitTypeFor(beneficiary))
    setCorrection(false)
    setConfirmed(false)
    setDangerAcknowledged(false)
    setDraftId(crypto.randomUUID())
    setSeconds(0)
    setRecording(false)
    navigate('voice')
  }
  const loadScenario = (nextScenario: Scenario) => {
    const category = nextScenario.type.includes('Pregnancy') ? 'Pregnant' : 'Newborn'
    const matchingBeneficiary = beneficiaries.find((person) => person.category === category)
    if (matchingBeneficiary) setSelected(matchingBeneficiary)
    setScenario(nextScenario)
    setConfirmed(false)
    setDangerAcknowledged(false)
    const extracted = extractionService.extract(nextScenario.transcript, nextScenario.lang as 'kn' | 'hi' | 'en')
    setWeight(extracted.weightKg === null ? nextScenario.weight || '' : String(extracted.weightKg))
    setVisitType(extracted.visitType || nextScenario.type)
    setVaccines(extracted.vaccinationsDue?.join(', ') || nextScenario.vaccines || '')
    setNextDate(extracted.nextVisitDate || nextScenario.date || '')
    setNotes('')
  }
  const resetScenario = () => loadScenario(scenarios.find((sample) => sample.type === visitTypeFor(selected)) || scenarios[0])
  const openRecord = (record: VisitRecord) => {
    const beneficiary = beneficiaries.find((person) => person.id === record.beneficiaryId) || beneficiaries[0]
    const recordScenario = scenarios.find((sample) => sample.type === record.type && sample.danger === record.danger) || scenarios.find((sample) => sample.type === record.type) || scenarios[0]
    setSelected(beneficiary)
    setScenario(recordScenario)
    setWeight(record.weight)
    setVisitType(record.type)
    setNextDate(record.nextDate)
    setVaccines(record.vaccines || recordScenario.vaccines || '')
    setNotes(record.notes || '')
    setConfirmed(false)
    setDangerAcknowledged(false)
    setDraftId(record.draftId || crypto.randomUUID())
    setCorrection(false)
    navigate('review')
  }
  const applyCorrection = () => {
    if (!correctionValue.trim()) return
    const value = correctionValue.trim()
    if (correctionField === 'weight') setWeight(value)
    if (correctionField === 'vaccines') setVaccines(value)
    if (correctionField === 'nextDate') setNextDate(value)
    if (correctionField === 'notes') setNotes(value)
    setCorrectionValue('')
    setCorrection(false)
    setConfirmed(false)
  }
  const save = () => {
    if (!confirmed || (danger && !dangerAcknowledged) || (!danger && (!weight.trim() || !nextDate.trim()))) return
    const record: VisitRecord = {
      id: `V-${draftId.slice(0, 8)}`,
      draftId,
      beneficiaryId: selected.id,
      type: visitType,
      date: new Intl.DateTimeFormat('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }).format(new Date()),
      nextDate: danger ? nextDate || 'Immediate referral' : nextDate,
      status: danger ? 'Flagged' : 'Completed',
      danger,
      dangerFlags: safetyAssessment.signs,
      weight,
      vaccines,
      notes,
    }
    mockVisitStore.save(record)
    setSavedRecords(mockVisitStore.list())
    navigate('saved')
  }
  const playDemo = () => {
    setReadback(true)
    window.setTimeout(() => setReadback(false), 1800)
  }

  return {
    lang, setLang, page, navigate, selected, setSelected, chooseBeneficiary, chooseVisitType, filter, setFilter,
    followFilter, setFollowFilter, query, setQuery, historyQuery, setHistoryQuery, scenario,
    setScenario, recording, setRecording, setSeconds, weight, setWeight, visitType, setVisitType,
    vaccines, setVaccines, nextDate, setNextDate, notes, setNotes, savedRecords, correction,
    setCorrection, correctionField, setCorrectionField, correctionValue, setCorrectionValue, applyCorrection,
    confirmed, setConfirmed, dangerAcknowledged, setDangerAcknowledged, mobileMenu, setMobileMenu, readback, setReadback, filtered, danger, begin,
    loadScenario, resetScenario, openRecord, save, playDemo, safetyAssessment,
  }
}
