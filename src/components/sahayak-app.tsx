'use client'

import { useState } from 'react'
import {
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  Bell,
  CalendarDays,
  CheckCircle2,
  ChevronDown,
  ClipboardList,
  Clock3,
  Heart,
  Home,
  Languages,
  Menu,
  Mic,
  Search,
  Settings,
  ShieldCheck,
  Users,
} from 'lucide-react'

import { copy, type Language } from '@/src/data/translations'
import { SahayakLiveScreen } from '@/src/components/sahayak-live-screen'
import { useSahayakApp, type AppPage } from '@/src/hooks/use-sahayak-app'
import type { Alert, Beneficiary, Visit } from '@/src/services/api.service'

type Lang = Language

const pageIcons = {
  home: Home,
  people: Users,
  follow: CalendarDays,
  history: ClipboardList,
  alerts: AlertTriangle,
  profile: Settings,
} satisfies Record<Exclude<AppPage, 'voice'>, typeof Home>

const labels: Record<Lang, {
  overview: string
  healthRecords: string
  followUps: string
  safetyAlerts: string
  fieldWorker: string
  allCategories: string
  child: string
  other: string
  noBeneficiaries: string
  noVisits: string
  noFollowUps: string
  noAlerts: string
  loading: string
  backendOnline: string
  backendUnavailable: string
  lastVisit: string
  nextVisit: string
  village: string
  referral: string
  acknowledge: string
  markComplete: string
  reschedule: string
  details: string
  visitId: string
  back: string
  historySearch: string
  followUpDate: string
  status: string
  due: string
  created: string
  reviewNeeded: string
  currentData: string
  backendProfileNote: string
  offlineQueue: string
  all: string
  retry: string
  fromDate: string
  toDate: string
}> = {
  en: {
    overview: 'Dashboard',
    healthRecords: 'Visit history',
    followUps: 'Follow-ups',
    safetyAlerts: 'Safety alerts',
    fieldWorker: 'ASHA field worker',
    allCategories: 'All categories',
    child: 'Child',
    other: 'Other',
    noBeneficiaries: 'No beneficiaries match this search.',
    noVisits: 'No visits have been saved yet.',
    noFollowUps: 'No follow-ups match this filter.',
    noAlerts: 'There are no open safety alerts.',
    loading: 'Loading records from SAHAYAK…',
    backendOnline: 'Backend connected',
    backendUnavailable: 'Backend unavailable',
    lastVisit: 'Last visit',
    nextVisit: 'Next follow-up',
    village: 'Village',
    referral: 'Referral status',
    acknowledge: 'Acknowledge',
    markComplete: 'Mark complete',
    reschedule: 'Save date',
    details: 'Visit details',
    visitId: 'Visit ID',
    back: 'Back to dashboard',
    historySearch: 'Search ID, name, or visit type',
    followUpDate: 'Due date',
    status: 'Status',
    due: 'Due',
    created: 'Recorded',
    reviewNeeded: 'This data is read from the SAHAYAK backend.',
    currentData: 'Current SQLite records',
    backendProfileNote: 'Worker account details are not provided by the backend.',
    offlineQueue: 'Open offline audio queue',
    all: 'All',
    retry: 'Retry',
    fromDate: 'From',
    toDate: 'To',
  },
  kn: {
    overview: 'ಡ್ಯಾಶ್‌ಬೋರ್ಡ್',
    healthRecords: 'ಭೇಟಿ ಇತಿಹಾಸ',
    followUps: 'ಮುಂದಿನ ಭೇಟಿಗಳು',
    safetyAlerts: 'ಸುರಕ್ಷತಾ ಎಚ್ಚರಿಕೆಗಳು',
    fieldWorker: 'ಆಶಾ ಕ್ಷೇತ್ರ ಕಾರ್ಯಕರ್ತೆ',
    allCategories: 'ಎಲ್ಲಾ ವರ್ಗಗಳು',
    child: 'ಮಗು',
    other: 'ಇತರೆ',
    noBeneficiaries: 'ಈ ಹುಡುಕಾಟಕ್ಕೆ ಫಲಾನುಭವಿಗಳು ಕಂಡುಬಂದಿಲ್ಲ.',
    noVisits: 'ಇನ್ನೂ ಯಾವುದೇ ಭೇಟಿಯನ್ನು ಉಳಿಸಲಾಗಿಲ್ಲ.',
    noFollowUps: 'ಈ ಫಿಲ್ಟರ್‌ಗೆ ಮುಂದಿನ ಭೇಟಿಗಳಿಲ್ಲ.',
    noAlerts: 'ತೆರೆದ ಸುರಕ್ಷತಾ ಎಚ್ಚರಿಕೆಗಳಿಲ್ಲ.',
    loading: 'SAHAYAK ದಾಖಲೆಗಳನ್ನು ಲೋಡ್ ಮಾಡಲಾಗುತ್ತಿದೆ…',
    backendOnline: 'ಬ್ಯಾಕೆಂಡ್ ಸಂಪರ್ಕಗೊಂಡಿದೆ',
    backendUnavailable: 'ಬ್ಯಾಕೆಂಡ್ ಲಭ್ಯವಿಲ್ಲ',
    lastVisit: 'ಕೊನೆಯ ಭೇಟಿ',
    nextVisit: 'ಮುಂದಿನ ಭೇಟಿ',
    village: 'ಗ್ರಾಮ',
    referral: 'ರೆಫರಲ್ ಸ್ಥಿತಿ',
    acknowledge: 'ಸ್ವೀಕರಿಸಿ',
    markComplete: 'ಪೂರ್ಣಗೊಳಿಸಿ',
    reschedule: 'ದಿನಾಂಕ ಉಳಿಸಿ',
    details: 'ಭೇಟಿಯ ವಿವರಗಳು',
    visitId: 'ಭೇಟಿ ID',
    back: 'ಡ್ಯಾಶ್‌ಬೋರ್ಡ್‌ಗೆ ಹಿಂತಿರುಗಿ',
    historySearch: 'ID, ಹೆಸರು ಅಥವಾ ಭೇಟಿ ಪ್ರಕಾರ ಹುಡುಕಿ',
    followUpDate: 'ನಿಗದಿತ ದಿನಾಂಕ',
    status: 'ಸ್ಥಿತಿ',
    due: 'ನಿಗದಿತ',
    created: 'ದಾಖಲಿಸಿದ',
    reviewNeeded: 'ಈ ಡೇಟಾವನ್ನು SAHAYAK ಬ್ಯಾಕೆಂಡ್‌ನಿಂದ ಓದಲಾಗಿದೆ.',
    currentData: 'ಪ್ರಸ್ತುತ SQLite ದಾಖಲೆಗಳು',
    backendProfileNote: 'ಕಾರ್ಯಕರ್ತೆಯ ಖಾತೆ ವಿವರಗಳನ್ನು ಬ್ಯಾಕೆಂಡ್ ಒದಗಿಸಿಲ್ಲ.',
    offlineQueue: 'ಆಫ್‌ಲೈನ್ ಆಡಿಯೊ ಸರದಿಯನ್ನು ತೆರೆಯಿರಿ',
    all: 'ಎಲ್ಲಾ',
    retry: 'ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ',
    fromDate: 'ಇಂದಿನಿಂದ',
    toDate: 'ಇಲ್ಲಿಯವರೆಗೆ',
  },
  hi: {
    overview: 'डैशबोर्ड',
    healthRecords: 'विज़िट इतिहास',
    followUps: 'फ़ॉलो-अप',
    safetyAlerts: 'सुरक्षा चेतावनी',
    fieldWorker: 'आशा फील्ड वर्कर',
    allCategories: 'सभी श्रेणियाँ',
    child: 'बच्चा',
    other: 'अन्य',
    noBeneficiaries: 'इस खोज में कोई लाभार्थी नहीं मिला।',
    noVisits: 'अभी तक कोई विज़िट सेव नहीं हुई है।',
    noFollowUps: 'इस फ़िल्टर में कोई फ़ॉलो-अप नहीं है।',
    noAlerts: 'कोई खुली सुरक्षा चेतावनी नहीं है।',
    loading: 'SAHAYAK रिकॉर्ड लोड हो रहे हैं…',
    backendOnline: 'बैकएंड कनेक्ट है',
    backendUnavailable: 'बैकएंड उपलब्ध नहीं है',
    lastVisit: 'पिछली विज़िट',
    nextVisit: 'अगला फ़ॉलो-अप',
    village: 'गाँव',
    referral: 'रेफ़रल स्थिति',
    acknowledge: 'स्वीकार करें',
    markComplete: 'पूरा करें',
    reschedule: 'तारीख सेव करें',
    details: 'विज़िट विवरण',
    visitId: 'विज़िट ID',
    back: 'डैशबोर्ड पर वापस',
    historySearch: 'ID, नाम या विज़िट प्रकार खोजें',
    followUpDate: 'नियत तारीख',
    status: 'स्थिति',
    due: 'नियत',
    created: 'दर्ज',
    reviewNeeded: 'यह डेटा SAHAYAK बैकएंड से पढ़ा गया है।',
    currentData: 'वर्तमान SQLite रिकॉर्ड',
    backendProfileNote: 'बैकएंड में कार्यकर्ता खाते की जानकारी उपलब्ध नहीं है।',
    offlineQueue: 'ऑफ़लाइन ऑडियो कतार खोलें',
    all: 'सभी',
    retry: 'फिर कोशिश करें',
    fromDate: 'से',
    toDate: 'तक',
  },
}

function formatDate(value: string | null | undefined, lang: Lang) {
  if (!value) return '—'
  const dateOnly = /^\d{4}-\d{2}-\d{2}$/.test(value)
  const normalized = dateOnly
    ? `${value}T00:00:00`
    : `${value.replace(' ', 'T')}${/[zZ]|[+-]\d{2}:\d{2}$/.test(value) ? '' : 'Z'}`
  const date = new Date(normalized)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat(
    lang === 'kn' ? 'kn-IN' : lang === 'hi' ? 'hi-IN' : 'en-GB',
    { day: 'numeric', month: 'short', year: 'numeric' }
  ).format(date)
}

function statusClass(status: string) {
  if (status === 'completed') return 'status-done'
  if (status === 'overdue') return 'status-overdue'
  if (status === 'pending') return 'status-upcoming'
  return 'status-review'
}

function categoryName(category: string) {
  return category
    .replaceAll('_', ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function visitName(visit: Visit) {
  return visit.visit_type
    ? categoryName(visit.visit_type)
    : 'Household visit'
}

function beneficiaryName(beneficiary: Beneficiary | null) {
  return beneficiary?.name || beneficiary?.beneficiary_id || '—'
}

function initials(name: string) {
  return name.trim().slice(0, 1).toUpperCase() || '•'
}

function VisitSummary({
  visit,
  lang,
  onClose,
}: {
  visit: Visit
  lang: Lang
  onClose: () => void
}) {
  const t = labels[lang]
  return (
    <section className="panel visit-detail-panel">
      <div className="panel-heading">
        <div>
          <h2>{t.details} · {t.visitId} {visit.id}</h2>
          <p>{visit.beneficiary_name} · {visit.beneficiary_id}</p>
        </div>
        <button className="text-button" onClick={onClose}>×</button>
      </div>
      <div className="visit-detail-grid">
        <div><small>{t.created}</small><b>{formatDate(visit.created_at, lang)}</b></div>
        <div><small>{copy[lang].visitType}</small><b>{visitName(visit)}</b></div>
        <div><small>{copy[lang].weight}</small><b>{visit.weight_kg == null ? '—' : `${visit.weight_kg} kg`}</b></div>
        <div><small>{copy[lang].vaccines}</small><b>{visit.vaccinations_due?.join(', ') || '—'}</b></div>
        <div><small>{t.nextVisit}</small><b>{formatDate(visit.next_visit_date, lang)}</b></div>
        {visit.alerts.map((alert) => (
          <div className="visit-detail-alert" key={alert.id}>
            <small>{labels[lang].safetyAlerts}</small>
            <b>{alert.recommended_action || alert.transcript}</b>
          </div>
        ))}
      </div>
    </section>
  )
}

export default function SahayakApp() {
  const app = useSahayakApp()
  const t = copy[app.lang]
  const text = labels[app.lang]
  const [followUpDates, setFollowUpDates] = useState<Record<number, string>>({})
  const navPages: Exclude<AppPage, 'voice'>[] = [
    'home',
    'people',
    'follow',
    'history',
    'alerts',
    'profile',
  ]
  const navText: Record<Exclude<AppPage, 'voice'>, string> = {
    home: text.overview,
    people: t.beneficiaries,
    follow: text.followUps,
    history: text.healthRecords,
    alerts: text.safetyAlerts,
    profile: t.settings,
  }
  const today = new Date().toLocaleDateString(
    app.lang === 'kn' ? 'kn-IN' : app.lang === 'hi' ? 'hi-IN' : 'en-GB',
    { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric', timeZone: 'Asia/Kolkata' }
  )
  const pendingAlerts = app.alerts.filter(
    (alert) => alert.referral_status !== 'completed'
  ).length

  if (app.page === 'voice') {
    return (
      <div className={`app-shell lang-${app.lang} live-mode`} lang={app.lang}>
        <SahayakLiveScreen
          lang={app.lang}
          setLang={app.setLang}
          onBack={() => app.navigate('home')}
          selectedId={app.selected?.beneficiary_id || ''}
        />
      </div>
    )
  }

  const renderVisitRow = (visit: Visit) => (
    <button
      className="visit-row"
      key={visit.id}
      onClick={() => app.setSelectedVisit(visit)}
    >
      <div className="person-avatar rose">
        {initials(visit.beneficiary_name)}
      </div>
      <div className="visit-person">
        <b>{visit.beneficiary_name}</b>
        <small>{visit.beneficiary_id} · {visitName(visit)}</small>
      </div>
      <div className="visit-time">
        <CalendarDays size={14} />
        {formatDate(visit.created_at, app.lang)}
      </div>
      <span className={`status ${visit.alerts.length ? 'status-flagged' : 'status-done'}`}>
        {visit.alerts.length ? text.safetyAlerts : t.completed}
      </span>
      <ArrowRight className="row-arrow" size={16} />
    </button>
  )

  return (
    <div className={`app-shell lang-${app.lang}`} lang={app.lang}>
      <aside className={`sidebar ${app.mobileMenu ? 'mobile-open' : ''}`}>
        <a
          className="brand"
          href="#home"
          onClick={(event) => {
            event.preventDefault()
            app.navigate('home')
          }}
        >
          <span className="brand-mark"><Heart size={21} fill="currentColor" /></span>
          <span><b>SAHAYAK</b><small>{t.communityHealth}</small></span>
        </a>
        <div className="worker-chip">
          <div className="avatar">S</div>
          <div><b>{text.fieldWorker}</b><small>{text.currentData}</small></div>
        </div>
        <div className="nav-caption">{t.workspaceNav}</div>
        <nav className="side-nav">
          {navPages.map((key) => {
            const Icon = pageIcons[key]
            return (
              <button
                key={key}
                onClick={() => app.navigate(key)}
                className={`nav-link ${app.page === key ? 'active' : ''}`}
              >
                <Icon size={18} />
                <span>{navText[key]}</span>
                {key === 'alerts' && pendingAlerts > 0 && (
                  <i className="nav-count">{pendingAlerts}</i>
                )}
              </button>
            )
          })}
        </nav>
        <div className="sidebar-bottom">
          <a className="offline-link" href="/offline">{text.offlineQueue}<ArrowRight size={14} /></a>
          <div className="version">SAHAYAK AI <span>v0.1.0</span></div>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <button
            className="mobile-menu"
            aria-label="Open navigation"
            onClick={() => app.setMobileMenu(!app.mobileMenu)}
          >
            <Menu />
          </button>
          <div className="breadcrumb">
            {t.workspace} <span>/</span> <strong>{navText[app.page]}</strong>
          </div>
          <div className="top-actions">
            <span className={`backend-pill ${app.error ? 'offline' : 'online'}`}>
              <i />
              {app.error ? text.backendUnavailable : text.backendOnline}
            </span>
            <label className="language-select">
              <Languages size={16} />
              <select
                value={app.lang}
                onChange={(event) => app.setLang(event.target.value as Lang)}
                aria-label={t.language}
              >
                <option value="kn">ಕನ್ನಡ</option>
                <option value="hi">हिन्दी</option>
                <option value="en">English</option>
              </select>
              <ChevronDown size={14} />
            </label>
            <button className="icon-btn" aria-label={text.safetyAlerts} onClick={() => app.navigate('alerts')}>
              <Bell size={18} />
              {pendingAlerts > 0 && <i />}
            </button>
            <div className="top-avatar">S</div>
          </div>
        </header>
        {app.mobileMenu && (
          <div className="mobile-menu-panel">
            {navPages.map((key) => {
              const Icon = pageIcons[key]
              return (
                <button key={key} onClick={() => app.navigate(key)}>
                  <Icon size={18} />
                  {navText[key]}
                </button>
              )
            })}
          </div>
        )}

        <div className="content-wrap">
          {app.error && (
            <div className="api-error" role="alert">
              <AlertCircle size={18} />
              <span>{app.error}</span>
              <button onClick={() => void app.refresh()}>{text.retry}</button>
            </div>
          )}
          {app.loading && !app.dashboard ? (
            <div className="api-loading" role="status">{text.loading}</div>
          ) : (
            <>
              {app.page === 'home' && (
                <>
                  <section className="welcome-row">
                    <div>
                      <div className="eyebrow">{today}<span className="eyebrow-line" /></div>
                      <h1>{t.welcome}</h1>
                      <p>{t.dashboard}</p>
                    </div>
                    <button className="button-primary start-home" onClick={() => app.begin()}>
                      <Mic size={19} />{t.start}<ArrowRight size={17} />
                    </button>
                  </section>
                  <section className="stats-grid">
                    {[
                      { label: t.visits, value: (app.dashboard?.stats.visits_today || 0) + (app.dashboard?.stats.scheduled_today || 0), icon: CalendarDays, cls: 'teal' },
                      { label: t.completed, value: app.dashboard?.stats.visits_today || 0, icon: CheckCircle2, cls: 'green' },
                      { label: text.followUps, value: app.dashboard?.stats.upcoming_follow_ups || 0, icon: Clock3, cls: 'amber' },
                      { label: t.danger, value: app.dashboard?.stats.urgent_referrals || 0, icon: AlertCircle, cls: 'red' },
                    ].map((stat) => (
                      <article key={stat.label} className="stat-card">
                        <div className={`stat-icon ${stat.cls}`}><stat.icon size={19} /></div>
                        <div className="stat-label">{stat.label}</div>
                        <div className="stat-bottom"><strong>{stat.value}</strong><span>{text.currentData}</span></div>
                      </article>
                    ))}
                  </section>
                  <div className="dashboard-grid">
                    <section className="panel visits-panel">
                      <div className="panel-heading">
                        <div><h2>{t.today}</h2><p>{t.householdVisits}</p></div>
                        <button className="text-button" onClick={() => app.navigate('history')}>{t.viewAll}<ArrowRight size={15} /></button>
                      </div>
                      <div className="visit-list">
                        {(app.dashboard?.today_visits || []).map(renderVisitRow)}
                        {(!app.dashboard?.today_visits.length) && (
                          <p className="empty-state">{text.noVisits}</p>
                        )}
                      </div>
                      <button className="list-footer" onClick={() => app.navigate('people')}>
                        <Users size={16} /> {t.beneficiaries}<ArrowRight size={15} />
                      </button>
                    </section>
                    <section className="panel follow-panel">
                      <div className="panel-heading">
                        <div><h2>{text.followUps}</h2><p>{t.keepOnTrack}</p></div>
                        <button className="round-link" onClick={() => app.navigate('follow')} aria-label={t.viewAll}><ArrowRight size={16} /></button>
                      </div>
                      <div className="follow-list">
                        {(app.dashboard?.upcoming_follow_ups || []).map((followUp) => (
                          <button
                            className="follow-row"
                            key={followUp.id}
                            onClick={() => app.navigate('follow')}
                          >
                            <div className={`date-tile ${followUp.status === 'overdue' ? 'soon' : ''}`}>
                              <b>{new Date(`${followUp.scheduled_date}T00:00:00`).getDate()}</b>
                              <small>{new Date(`${followUp.scheduled_date}T00:00:00`).toLocaleDateString(undefined, { month: 'short' })}</small>
                            </div>
                            <div><b>{followUp.beneficiary_name}</b><small>{followUp.beneficiary_id} · {followUp.reason}</small></div>
                            <ChevronDown size={16} className="rotate-icon" />
                          </button>
                        ))}
                        {(!app.dashboard?.upcoming_follow_ups.length) && <p className="empty-state">{text.noFollowUps}</p>}
                      </div>
                      <div className="safe-note"><ShieldCheck size={17} /><span>{text.reviewNeeded}</span></div>
                    </section>
                  </div>
                  {app.dashboard?.urgent_alerts.length ? (
                    <section className="panel home-alert-panel">
                      <div className="panel-heading">
                        <div><h2>{text.safetyAlerts}</h2><p>{t.requiresAttention}</p></div>
                        <button className="text-button" onClick={() => app.navigate('alerts')}>{t.viewAll}<ArrowRight size={15} /></button>
                      </div>
                      {app.dashboard.urgent_alerts.map((alert) => (
                        <AlertRow
                          key={alert.id}
                          alert={alert}
                          lang={app.lang}
                          busy={app.busyAction}
                          acknowledge={app.acknowledgeAlert}
                          updateStatus={app.updateReferralStatus}
                        />
                      ))}
                    </section>
                  ) : null}
                </>
              )}

              {app.page === 'people' && (
                <>
                  <div className="page-heading">
                    <div><div className="eyebrow">{t.community}</div><h1>{t.beneficiaries}</h1><p>{t.findPerson}</p></div>
                    <button className="button-primary" onClick={() => app.begin()}><Mic size={17} />{t.startVisit}</button>
                  </div>
                  <div className="filter-bar">
                    <div className="search-box"><Search size={18} /><input value={app.query} onChange={(event) => app.setQuery(event.target.value)} placeholder={t.search} /></div>
                    <div className="filter-pills">
                      {[
                        ['All', text.all],
                        ['Pregnant', t.pregnant],
                        ['Newborn', t.newborn],
                        ['Child', text.child],
                        ['Other', text.other],
                      ].map(([value, label]) => (
                        <button key={value} onClick={() => app.setFilter(value)} className={app.filter === value ? 'selected' : ''}>{label}</button>
                      ))}
                    </div>
                  </div>
                  <div className="beneficiary-grid">
                    {app.filteredBeneficiaries.map((beneficiary) => (
                      <button
                        className={`beneficiary-card ${app.selected?.beneficiary_id === beneficiary.beneficiary_id ? 'chosen' : ''}`}
                        key={beneficiary.beneficiary_id}
                        onClick={() => app.chooseBeneficiary(beneficiary)}
                      >
                        <div className="beneficiary-top">
                          <div className="person-avatar rose">{initials(beneficiary.name)}</div>
                          <span className="category-tag">{categoryName(beneficiary.category)}</span>
                        </div>
                        <h3>{beneficiary.name}</h3>
                        <span className="beneficiary-id">{beneficiary.beneficiary_id}</span>
                        <div className="beneficiary-info">
                          <div><small>{text.village}</small><b>{beneficiary.village}</b></div>
                          <div><small>{text.lastVisit}</small><b>{formatDate(beneficiary.last_visit, app.lang)}</b></div>
                        </div>
                        <div className="beneficiary-footer">
                          <span><CalendarDays size={14} /> {text.nextVisit}: {formatDate(beneficiary.next_visit, app.lang)}</span>
                          <span className="select-circle"><ArrowRight size={14} /></span>
                        </div>
                      </button>
                    ))}
                    {!app.filteredBeneficiaries.length && <p className="empty-state">{text.noBeneficiaries}</p>}
                  </div>
                  {app.selected && (
                    <section className="selected-strip">
                      <div><b>{app.selected.beneficiary_id}</b><span> · {app.selected.name} · {app.selected.village}</span></div>
                      <button className="button-primary" onClick={() => app.begin(app.selected)}>{t.startVisit}<ArrowRight size={17} /></button>
                    </section>
                  )}
                </>
              )}

              {app.page === 'follow' && (
                <>
                  <div className="page-heading">
                    <div><div className="eyebrow">{t.stayOnTrack}</div><h1>{text.followUps}</h1><p>{t.upcomingVisits}</p></div>
                    <button className="button-primary" onClick={() => app.begin()}><Mic size={17} />{t.start}</button>
                  </div>
                  <div className="filter-bar">
                    <div className="filter-pills">
                      {['All', 'Upcoming', 'Overdue', 'Completed'].map((filter) => (
                        <button key={filter} onClick={() => app.setFollowFilter(filter)} className={app.followFilter === filter ? 'selected' : ''}>
                          {filter === 'All' ? text.all : filter === 'Upcoming' ? t.upcomingStatus : filter === 'Overdue' ? t.overdueStatus : t.completed}
                        </button>
                      ))}
                    </div>
                    <div className="filter-count">{app.filteredFollowUps.length} {t.followups}</div>
                  </div>
                  <div className="panel table-panel">
                    <div className="table-header"><span>{t.beneficiary.toUpperCase()}</span><span>{t.visitCategory}</span><span>{text.due.toUpperCase()}</span><span>{text.status.toUpperCase()}</span><span /></div>
                    {app.filteredFollowUps.map((followUp) => (
                      <div className="table-row follow-up-table-row" key={followUp.id}>
                        <div className="table-person">
                          <div className="person-avatar rose">{initials(followUp.beneficiary_name)}</div>
                          <div><b>{followUp.beneficiary_name}</b><small>{followUp.beneficiary_id}</small></div>
                        </div>
                        <span>{followUp.reason}</span>
                        <label className="follow-date-field">
                          <span className="sr-only">{text.followUpDate}</span>
                          <input
                            type="date"
                            value={followUpDates[followUp.id] || followUp.scheduled_date}
                            onChange={(event) => setFollowUpDates((dates) => ({ ...dates, [followUp.id]: event.target.value }))}
                          />
                        </label>
                        <span className={`status ${statusClass(followUp.status)}`}>{followUp.status}</span>
                        <div className="follow-up-actions">
                          {followUp.status !== 'completed' && (
                            <>
                              <button disabled={app.busyAction || !(followUpDates[followUp.id] || followUp.scheduled_date)} onClick={() => void app.updateFollowUp(followUp.id, { scheduled_date: followUpDates[followUp.id] || followUp.scheduled_date })}>{text.reschedule}</button>
                              <button disabled={app.busyAction} onClick={() => void app.updateFollowUp(followUp.id, { status: 'completed' })}>{text.markComplete}</button>
                            </>
                          )}
                        </div>
                      </div>
                    ))}
                    {!app.filteredFollowUps.length && <p className="empty-state">{text.noFollowUps}</p>}
                  </div>
                </>
              )}

              {app.page === 'history' && (
                <>
                  <div className="page-heading">
                    <div><div className="eyebrow">{t.yourRegister}</div><h1>{text.healthRecords}</h1><p>{t.historyDescription}</p></div>
                    <button className="button-primary" onClick={() => app.begin()}><Mic size={17} />{t.start}</button>
                  </div>
                  <div className="filter-bar">
                    <div className="search-box"><Search size={18} /><input value={app.historyQuery} onChange={(event) => app.setHistoryQuery(event.target.value)} placeholder={text.historySearch} /></div>
                    <div className="history-date-filters">
                      <label>{text.fromDate}<input type="date" value={app.historyFrom} onChange={(event) => app.setHistoryFrom(event.target.value)} /></label>
                      <label>{text.toDate}<input type="date" value={app.historyTo} onChange={(event) => app.setHistoryTo(event.target.value)} /></label>
                    </div>
                    <div className="filter-count">{app.filteredVisits.length} {t.records}</div>
                  </div>
                  {app.selectedVisit && <VisitSummary visit={app.selectedVisit} lang={app.lang} onClose={() => app.setSelectedVisit(null)} />}
                  <div className="panel table-panel">
                    <div className="table-header history-head"><span>{text.created.toUpperCase()}</span><span>{t.beneficiary.toUpperCase()}</span><span>{t.type.toUpperCase()}</span><span>{text.status.toUpperCase()}</span><span /></div>
                    {app.filteredVisits.map((visit) => (
                      <button className="table-row history-row" key={visit.id} onClick={() => app.setSelectedVisit(visit)}>
                        <span>{formatDate(visit.created_at, app.lang)}</span>
                        <div className="table-person"><div className="person-avatar rose">{initials(visit.beneficiary_name)}</div><div><b>{visit.beneficiary_name}</b><small>{visit.beneficiary_id}</small></div></div>
                        <span>{visitName(visit)}</span>
                        <span className={`status ${visit.alerts.length ? 'status-flagged' : 'status-done'}`}>{visit.alerts.length ? text.safetyAlerts : t.completed}</span>
                        <ArrowRight size={16} />
                      </button>
                    ))}
                    {!app.filteredVisits.length && <p className="empty-state">{text.noVisits}</p>}
                  </div>
                </>
              )}

              {app.page === 'alerts' && (
                <>
                  <div className="page-heading">
                    <div><div className="eyebrow">{t.requiresAttention}</div><h1>{text.safetyAlerts}</h1><p>{text.reviewNeeded}</p></div>
                  </div>
                  <div className="panel alerts-panel">
                    {app.alerts.map((alert) => (
                      <AlertRow
                        key={alert.id}
                        alert={alert}
                        lang={app.lang}
                        busy={app.busyAction}
                        acknowledge={app.acknowledgeAlert}
                        updateStatus={app.updateReferralStatus}
                      />
                    ))}
                    {!app.alerts.length && <p className="empty-state">{text.noAlerts}</p>}
                  </div>
                </>
              )}

              {app.page === 'profile' && (
                <>
                  <div className="page-heading">
                    <div><div className="eyebrow">{text.currentData}</div><h1>{t.profile} & {t.settings}</h1><p>{text.backendProfileNote}</p></div>
                  </div>
                  <div className="settings-layout">
                    <section className="panel profile-card">
                      <div className="profile-cover"><div className="profile-avatar-large">S</div></div>
                      <div className="profile-body">
                        <h2>{text.fieldWorker}</h2>
                        <p>{text.currentData}</p>
                        <div className="profile-stats">
                          <div><b>{app.visits.length}</b><small>{t.visits}</small></div>
                          <div><b>{app.beneficiaries.length}</b><small>{t.beneficiaries}</small></div>
                        </div>
                      </div>
                    </section>
                    <section className="panel settings-card">
                      <div className="panel-heading"><div><h2>{t.languageAccess}</h2><p>{t.chooseSpeaks}</p></div><Languages size={20} /></div>
                      <label className="setting-row"><span><b>{t.language}</b><small>{t.instructionsReadback}</small></span><select value={app.lang} onChange={(event) => app.setLang(event.target.value as Lang)}><option value="kn">ಕನ್ನಡ</option><option value="hi">हिन्दी</option><option value="en">English</option></select></label>
                      <div className="about-box"><div className="brand-mark small-mark"><Heart size={17} fill="currentColor" /></div><div><b>SAHAYAK AI</b><p>{text.reviewNeeded}</p></div><span>v0.1.0</span></div>
                    </section>
                  </div>
                </>
              )}
            </>
          )}
        </div>
        <footer className="mobile-nav">
          {navPages.slice(0, 4).map((key) => {
            const Icon = pageIcons[key]
            return <button key={key} onClick={() => app.navigate(key)} className={app.page === key ? 'active' : ''}><Icon size={19} /><span>{navText[key]}</span></button>
          })}
        </footer>
      </main>
    </div>
  )
}

function AlertRow({
  alert,
  lang,
  busy,
  acknowledge,
  updateStatus,
}: {
  alert: Alert
  lang: Lang
  busy: boolean
  acknowledge: (id: number) => Promise<void>
  updateStatus: (
    id: number,
    status: 'not_started' | 'referred' | 'follow_up_pending' | 'completed'
  ) => Promise<void>
}) {
  const text = labels[lang]
  return (
    <article className="alert-data-row">
      <div className="alert-data-icon"><AlertTriangle size={18} /></div>
      <div className="alert-data-copy">
        <b>{alert.beneficiary_id || text.safetyAlerts} · {categoryName(alert.danger_type)}</b>
        <p>{alert.recommended_action || alert.transcript}</p>
        <small>{formatDate(alert.created_at, lang)}{alert.visit_id ? ` · Visit ${alert.visit_id}` : ''}</small>
      </div>
      <div className="alert-data-actions">
        {!alert.acknowledged && <button disabled={busy} onClick={() => void acknowledge(alert.id)}>{text.acknowledge}</button>}
        <label>
          <span className="sr-only">{text.referral}</span>
          <select
            value={alert.referral_status}
            disabled={busy}
            onChange={(event) => void updateStatus(
              alert.id,
              event.target.value as 'not_started' | 'referred' | 'follow_up_pending' | 'completed'
            )}
          >
            <option value="not_started">Not started</option>
            <option value="referred">Referred</option>
            <option value="follow_up_pending">Follow-up pending</option>
            <option value="completed">{copy[lang].completed}</option>
          </select>
        </label>
      </div>
    </article>
  )
}
