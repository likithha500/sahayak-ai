'use client'

import { useCallback, useEffect, useState } from 'react'
import type { Language } from '@/src/data/translations'
import {
  apiService,
  subscribeToDataUpdates,
  type Alert,
  type Beneficiary,
  type Dashboard,
  type FollowUp,
  type Visit,
} from '@/src/services/api.service'

export type AppPage =
  | 'home'
  | 'people'
  | 'follow'
  | 'history'
  | 'alerts'
  | 'profile'
  | 'voice'

export function useSahayakApp() {
  const [lang, setLang] = useState<Language>('kn')
  const [page, setPage] = useState<AppPage>('home')
  const [beneficiaries, setBeneficiaries] = useState<Beneficiary[]>([])
  const [visits, setVisits] = useState<Visit[]>([])
  const [followUps, setFollowUps] = useState<FollowUp[]>([])
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [dashboard, setDashboard] = useState<Dashboard | null>(null)
  const [selected, setSelected] = useState<Beneficiary | null>(null)
  const [selectedVisit, setSelectedVisit] = useState<Visit | null>(null)
  const [filter, setFilter] = useState('All')
  const [followFilter, setFollowFilter] = useState('All')
  const [query, setQuery] = useState('')
  const [historyQuery, setHistoryQuery] = useState('')
  const [historyFrom, setHistoryFrom] = useState('')
  const [historyTo, setHistoryTo] = useState('')
  const [mobileMenu, setMobileMenu] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busyAction, setBusyAction] = useState(false)

  const refresh = useCallback(async () => {
    try {
      const [nextDashboard, nextBeneficiaries, nextVisits, nextFollowUps, nextAlerts] =
        await Promise.all([
          apiService.getDashboard(),
          apiService.getBeneficiaries(),
          apiService.getVisits(),
          apiService.getFollowUps(),
          apiService.getAlerts(),
        ])
      setDashboard(nextDashboard)
      setBeneficiaries(nextBeneficiaries)
      setVisits(nextVisits)
      setFollowUps(nextFollowUps)
      setAlerts(nextAlerts)
      setError('')
      setSelected((current) =>
        current
          ? nextBeneficiaries.find(
              (person) => person.beneficiary_id === current.beneficiary_id
            ) || null
          : null
      )
      setSelectedVisit((current) =>
        current
          ? nextVisits.find((visit) => visit.id === current.id) || null
          : null
      )
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : 'Unable to load records from the SAHAYAK backend.'
      )
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
    return subscribeToDataUpdates(() => void refresh())
  }, [refresh])

  const navigate = (nextPage: AppPage) => {
    setPage(nextPage)
    setMobileMenu(false)
    if (nextPage !== 'voice') void refresh()
  }

  const chooseBeneficiary = (beneficiary: Beneficiary) => {
    setSelected(beneficiary)
  }

  const begin = (beneficiary = selected) => {
    setSelected(beneficiary)
    setPage('voice')
    setMobileMenu(false)
  }

  const filteredBeneficiaries = beneficiaries.filter((beneficiary) => {
    const category = beneficiary.category.toLowerCase()
    const categoryMatch =
      filter === 'All' ||
      (filter === 'Pregnant' && category.includes('preg')) ||
      (filter === 'Newborn' && category.includes('newborn')) ||
      (filter === 'Child' && category.includes('child')) ||
      (filter === 'Other' &&
        !['pregnant', 'pregnancy', 'newborn', 'child'].some((item) =>
          category.includes(item)
        ))
    const queryMatch =
      `${beneficiary.beneficiary_id} ${beneficiary.name} ${beneficiary.village}`
        .toLowerCase()
        .includes(query.toLowerCase())
    return categoryMatch && queryMatch
  })

  const updateFollowUp = async (
    id: number,
    update: { scheduled_date?: string; status?: 'pending' | 'completed' }
  ) => {
    setBusyAction(true)
    setError('')
    try {
      await apiService.updateFollowUp(id, update)
      await refresh()
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : 'Follow-up update failed.'
      )
    } finally {
      setBusyAction(false)
    }
  }

  const acknowledgeAlert = async (id: number) => {
    setBusyAction(true)
    setError('')
    try {
      await apiService.acknowledgeAlert(id)
      await refresh()
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : 'Alert update failed.'
      )
    } finally {
      setBusyAction(false)
    }
  }

  const updateReferralStatus = async (
    id: number,
    status: 'not_started' | 'referred' | 'follow_up_pending' | 'completed'
  ) => {
    setBusyAction(true)
    setError('')
    try {
      await apiService.updateReferralStatus(id, status)
      await refresh()
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : 'Referral update failed.'
      )
    } finally {
      setBusyAction(false)
    }
  }

  const filteredFollowUps = followUps.filter((followUp) => {
    if (followFilter === 'All') return true
    if (followFilter === 'Upcoming') return followUp.status === 'pending'
    return followUp.status === followFilter.toLowerCase()
  })

  const filteredVisits = visits.filter((visit) => {
    const matchesText =
      `${visit.beneficiary_id} ${visit.beneficiary_name} ${visit.visit_type || ''}`
        .toLowerCase()
        .includes(historyQuery.toLowerCase())
    const visitDate = visit.created_at?.slice(0, 10) || ''
    return (
      matchesText &&
      (!historyFrom || visitDate >= historyFrom) &&
      (!historyTo || visitDate <= historyTo)
    )
  })

  return {
    lang,
    setLang,
    page,
    navigate,
    beneficiaries,
    visits,
    followUps,
    alerts,
    dashboard,
    selected,
    chooseBeneficiary,
    selectedVisit,
    setSelectedVisit,
    filter,
    setFilter,
    followFilter,
    setFollowFilter,
    query,
    setQuery,
    historyQuery,
    setHistoryQuery,
    historyFrom,
    setHistoryFrom,
    historyTo,
    setHistoryTo,
    mobileMenu,
    setMobileMenu,
    loading,
    error,
    setError,
    busyAction,
    refresh,
    begin,
    filteredBeneficiaries,
    filteredFollowUps,
    filteredVisits,
    updateFollowUp,
    acknowledgeAlert,
    updateReferralStatus,
  }
}
