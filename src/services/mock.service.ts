import type { VisitRecord } from '../types/visit'

const STORAGE_KEY = 'sahayak-demo-visits-v1'

const readRecords = (): VisitRecord[] => {
  if (typeof window === 'undefined') return []
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    const parsed: unknown = stored ? JSON.parse(stored) : []
    return Array.isArray(parsed) ? parsed as VisitRecord[] : []
  } catch {
    return []
  }
}

export const mockVisitStore = {
  list: readRecords,
  save: (record: VisitRecord) => {
    const records = readRecords()
    const existingIndex = records.findIndex((item) => item.draftId === record.draftId || item.id === record.id)
    const existing = existingIndex >= 0 ? records[existingIndex] : undefined
    const savedRecord = existing
      ? { ...existing, ...record, danger: existing.danger || record.danger, dangerFlags: [...new Set([...existing.dangerFlags, ...record.dangerFlags])] }
      : record
    const updated = existingIndex >= 0
      ? records.map((item, index) => index === existingIndex ? savedRecord : item)
      : [savedRecord, ...records]
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(updated))
    return savedRecord
  },
}
