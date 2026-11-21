
'use client'

import { useEffect, useRef, useState } from 'react'
import {
  Activity,
  AlertTriangle,
  ArrowLeft,
  AudioLines,
  ChevronDown,
  Mic,
  ShieldCheck,
  Sparkles,
  Square,
} from 'lucide-react'

import type { Language } from '@/src/data/translations'
import { notifyDataUpdated } from '@/src/services/api.service'

import {
  LiveVoiceController,
  type VoiceEvent,
  type VoiceStatus,
} from '@/src/services/live-voice-controller'

type Props = {
  lang: Language
  setLang: (language: Language) => void
  onBack: () => void
  selectedId: string
}

type Message = {
  role: 'user' | 'assistant'
  text: string
}

type Alert = {
  id: number
  text: string
  acknowledged: boolean
}

const statusLabels: Record<VoiceStatus, string> = {
  disconnected: 'Ready when you are',
  connecting: 'Connecting to SAHAYAK...',
  listening: 'Listening to you...',
  thinking: 'Understanding your response...',
  speaking: 'SAHAYAK is speaking...',
  error: 'Connection or processing error',
}

export function SahayakLiveScreen(props: Props) {
  const { lang, setLang, onBack } = props

  const controller = useRef<LiveVoiceController | null>(null)
  const transcriptEnd = useRef<HTMLDivElement | null>(null)

  const [status, setStatus] =
    useState<VoiceStatus>('disconnected')

  const [messages, setMessages] =
    useState<Message[]>([])

  const [visit, setVisit] =
    useState<Record<string, unknown>>({})

  const [beneficiary, setBeneficiary] =
    useState<Record<string, unknown>>({})

  const [alerts, setAlerts] =
    useState<Alert[]>([])

  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)
  const [visitId, setVisitId] =
    useState<number | null>(null)
  const [awaitingConfirmation, setAwaitingConfirmation] =
    useState(false)
  const [currentQuestion, setCurrentQuestion] = useState('')
  const [skippedFields, setSkippedFields] = useState<string[]>([])

  const active =
    status !== 'disconnected' && status !== 'error'

  useEffect(() => {
    return () => {
      controller.current?.disconnect()
      controller.current = null
    }
  }, [])

  useEffect(() => {
    transcriptEnd.current?.scrollIntoView({
      behavior: 'smooth',
      block: 'nearest',
    })
  }, [messages])

  function handleEvent(event: VoiceEvent) {
    switch (event.type) {
      case 'session_started':
        setBeneficiary(event.beneficiary || {})
        break

      case 'transcript_final':
        if (event.text) {
          setError('')
          const text = event.text

          setMessages(previous => [
            ...previous,
            { role: 'user', text },
          ])
        }
        break

      case 'spoken_reply':
        if (event.text) {
          const text = event.text

          setMessages(previous => [
            ...previous,
            { role: 'assistant', text },
          ])
        }
        break

      case 'visit_draft':
      case 'beneficiary_clarification':
        if (event.visit) {
          setVisit(event.visit)
          setSaved(false)
          setVisitId(null)
        }

        setBeneficiary(event.beneficiary || {})
        setAwaitingConfirmation(
          event.awaiting_confirmation === true
        )
        setCurrentQuestion(
          typeof event.current_question === 'string'
            ? event.current_question
            : ''
        )
        setSkippedFields(
          Array.isArray(event.skipped_fields)
            ? event.skipped_fields.map(String)
            : []
        )
        break

      case 'visit_saved':
        setSaved(true)
        setAwaitingConfirmation(false)
        setVisitId(
          typeof event.visit_id === 'number'
            ? event.visit_id
            : null
        )
        notifyDataUpdated()
        break

      case 'danger_sign_detected':
        if (typeof event.alert_id === 'number') {
          const id = event.alert_id

          setAlerts(previous => [
            ...previous,
            {
              id,
              text: String(
                event.recommended_action ||
                event.matched_sign ||
                'Urgent safety alert. Arrange referral.'
              ),
              acknowledged: false,
            },
          ])
        }
        break

      case 'danger_alert_acknowledged':
        if (event.acknowledged === true) {
          setAlerts(previous =>
            previous.map(alert =>
              alert.id === event.alert_id
                ? { ...alert, acknowledged: true }
                : alert
            )
          )
        }
        break

      case 'session_error':
        setError(
          event.message || 'Voice processing failed'
        )
        break
    }
  }

  async function startVisit() {
    controller.current?.disconnect()

    setError('')
    setMessages([])
    setVisit({})
    setBeneficiary({})
    setAlerts([])
    setSaved(false)
    setAwaitingConfirmation(false)
    setCurrentQuestion('')
    setSkippedFields([])

    const voice = new LiveVoiceController({
      onStatus: setStatus,
      onEvent: handleEvent,
      language: lang,
      beneficiaryId:
        props.selectedId || undefined,
    })

    controller.current = voice

    await voice.connect()
  }

  function endVisit() {
    controller.current?.disconnect()
    controller.current = null
  }

  function goBack() {
    endVisit()
    onBack()
  }

  function display(value: unknown): string {
    if (value === null || value === undefined) {
      return ''
    }

    if (Array.isArray(value)) {
      return value.length
        ? value.join(', ')
        : 'None'
    }

    return String(value)
  }

  const fields = [
    {
      label: 'Beneficiary ID',
      value: display(
        beneficiary.beneficiary_id ||
        visit.beneficiary_id
      ),
    },
    {
      label: 'Beneficiary',
      value: display(
        beneficiary.name ||
        visit.beneficiary_name
      ),
    },
    {
      label: 'Visit type',
      value: display(visit.visit_type),
    },
    {
      label: 'Weight',
      value:
        visit.weight_kg != null
          ? `${visit.weight_kg} kg`
          : '',
    },
    {
      label: 'Vaccinations due',
      value: display(visit.vaccinations_due),
    },
    {
      label: 'Next visit',
      value: display(visit.next_visit_date),
    },
  ]

  return (
    <section
      className="live-screen"
      aria-labelledby="live-title"
    >
      <header className="live-header">
        <button
          className="live-back"
          onClick={goBack}
        >
          <ArrowLeft size={17} />
          <span>Back to dashboard</span>
        </button>

        <div className="live-brand">
          <span className="live-brand-mark">
            <Activity size={18} />
          </span>

          <span>
            <b>SAHAYAK</b>
            <small>COMMUNITY HEALTH</small>
          </span>
        </div>

        <label className="live-language">
          <select
            aria-label="Interface language"
            value={lang}
            disabled={active}
            onChange={event =>
              setLang(event.target.value as Language)
            }
          >
            <option value="kn">ಕನ್ನಡ</option>
            <option value="hi">हिन्दी</option>
            <option value="en">English</option>
          </select>
          <ChevronDown size={14} />
        </label>
      </header>

      {alerts.map(alert => (
        <div
          key={alert.id}
          className="live-danger"
          role="alert"
        >
          <div className="live-danger-icon">
            <AlertTriangle size={21} />
          </div>

          <div className="live-danger-copy">
            <strong>Urgent safety alert</strong>
            <p>{alert.text}</p>

            <small>
              Referral instruction only.
              No diagnosis or treatment advice.
            </small>

            <label className="live-ack">
              <input
                type="checkbox"
                checked={alert.acknowledged}
                disabled={alert.acknowledged || !active}
                onChange={() =>
                  controller.current?.acknowledgeAlert(
                    alert.id
                  )
                }
              />

              <span>
                I acknowledge this safety alert.
              </span>
            </label>
          </div>
        </div>
      ))}

      <div className="live-content">
        <div className="live-main-column">
          <div className="live-intro">
            <span className="live-kicker">
              <span className="live-kicker-dot" />
              Gnani Prisma STT · Timbre TTS · Groq AI
            </span>

            <h1 id="live-title">SAHAYAK Live</h1>

            <p>
              A calmer way to capture every visit
            </p>
          </div>

          <div className="live-orb-area">
            <div
              className="live-orb-rings"
              aria-hidden="true"
              style={{
                opacity: active ? 1 : 0.75,
                transform:
                  status === 'speaking'
                    ? 'scale(1.08)'
                    : 'scale(1)',
                transition: 'transform 300ms ease',
              }}
            >
              <span />
              <span />
              <span />

              <div className="live-orb">
                <AudioLines size={36} />
              </div>
            </div>

            <p
              className="live-orb-caption"
              role="status"
              aria-live="polite"
            >
              {statusLabels[status]}
            </p>

            <button
              className="live-start"
              onClick={
                active ? endVisit : startVisit
              }
            >
              {active
                ? <Square size={19} />
                : <Mic size={19} />}

              {active
                ? 'End conversation'
                : 'Start voice visit'}
            </button>

            {error && (
              <p className="live-error" role="alert">
                {error}
              </p>
            )}

            <p className="live-interrupt">
              <ShieldCheck size={15} />
              {status === 'listening'
                ? 'Speak naturally. Pause when finished.'
                : 'Automatic voice turn-taking'}
            </p>
          </div>

          <div className="live-record-card">
            <div className="live-card-heading">
              <div>
                <span className="live-card-eyebrow">
                  <Sparkles size={13} />
                  Real-time extraction
                </span>

                <h2>Visit summary</h2>
              </div>

              <span className="live-capture-pill">
                <span />
                {saved
                  ? `Saved${visitId ? ` · ID ${visitId}` : ''}`
                  : awaitingConfirmation
                    ? 'Awaiting confirmation'
                    : 'Unsaved draft'}
              </span>
            </div>

            <div
              className="live-fields"
              aria-live="polite"
            >
              {fields.map(field => (
                <div
                  className="live-field"
                  key={field.label}
                >
                  <span>{field.label}</span>

                  <b
                    className={
                      field.value ? '' : 'is-empty'
                    }
                  >
                    {field.value || 'Not yet captured'}
                  </b>
                </div>
              ))}
            </div>

            <div className="live-missing-info" aria-live="polite">
              <b>
                {awaitingConfirmation
                  ? 'Review complete — awaiting your confirmation'
                  : currentQuestion
                    ? `Next information requested: ${currentQuestion}`
                    : 'Missing information'}
              </b>
              {skippedFields.length > 0 && (
                <span>Skipped optional fields: {skippedFields.join(', ')}</span>
              )}
            </div>

            <p className="live-readonly-note">
              {saved
                ? 'The backend confirmed that this visit was saved.'
                : 'Review extracted information carefully. Speak to correct any field before confirming.'}
            </p>
          </div>
        </div>

        <aside className="live-side-column">
          <div className="live-connect-card">
            <span className="live-connect-icon">
              <Mic size={17} />
            </span>

            <div>
              <b>{statusLabels[status]}</b>
              <small>
                {active
                  ? 'Voice session active'
                  : 'Voice session inactive'}
              </small>
            </div>

            <span
              className="live-connection-dot"
              style={{
                background: active
                  ? '#2dd4bf'
                  : '#64748b',
              }}
            />
          </div>

          <section className="live-demo-card">
            <div className="live-demo-heading">
              <span>LIVE CONVERSATION</span>
              <span className="live-demo-dot" />
            </div>

            <h2>Your conversation</h2>

            <div
              style={{
                maxHeight: 480,
                overflowY: 'auto',
                display: 'flex',
                flexDirection: 'column',
                gap: 14,
                padding: '12px 0',
              }}
              aria-live="polite"
            >
              {messages.length === 0 && (
                <p>
                  Start a voice visit and tell SAHAYAK
                  about your household visit.
                  Your conversation will appear here.
                </p>
              )}

              {messages.map((message, index) => (
                <div
                  key={index}
                  style={{
                    alignSelf:
                      message.role === 'user'
                        ? 'flex-end'
                        : 'flex-start',
                    maxWidth: '92%',
                    borderRadius: 14,
                    padding: '12px 15px',
                    background:
                      message.role === 'user'
                        ? 'rgba(20,184,166,0.16)'
                        : 'rgba(255,255,255,0.06)',
                    border:
                      '1px solid rgba(255,255,255,0.08)',
                  }}
                >
                  <small
                    style={{
                      fontWeight: 700,
                      color:
                        message.role === 'user'
                          ? '#94a3b8'
                          : '#5eead4',
                    }}
                  >
                    {message.role === 'user'
                      ? 'YOU'
                      : 'SAHAYAK AI'}
                  </small>

                  <p
                    style={{
                      marginTop: 6,
                      lineHeight: 1.6,
                      overflowWrap: 'anywhere',
                      whiteSpace: 'pre-wrap',
                    }}
                  >
                    {message.text}
                  </p>
                </div>
              ))}

              <div ref={transcriptEnd} />
            </div>
          </section>
        </aside>
      </div>
    </section>
  )
}
