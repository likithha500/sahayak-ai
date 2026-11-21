'use client'

import { useEffect, useRef, useState } from 'react'
import { Activity, AlertTriangle, ArrowLeft, AudioLines, Check, ChevronDown, CircleHelp, Mic, ShieldCheck, Sparkles } from 'lucide-react'
import type { Language } from '@/src/data/translations'
import type { Scenario } from '@/src/data/mock'

type LiveEventMap = {
  session_connected: { sessionId: string }
  listening_started: Record<string, never>
  transcript_partial: { text: string; language: Language }
  transcript_final: { text: string; language: Language }
  agent_speaking_started: { messageId: string }
  agent_audio_chunk: { messageId: string; audio: ArrayBuffer }
  agent_interrupted: { messageId: string }
  record_updated: { field: string; value: string }
  clarification_requested: { field: string; prompt: string }
  danger_sign_detected: { sign: string; instruction: Record<Language, string> }
  confirmation_requested: Record<string, never>
  visit_saved: { visitId: string }
  session_error: { message: string; recoverable: boolean }
}

export type LiveEvent = { [K in keyof LiveEventMap]: { type: K } & LiveEventMap[K] }[keyof LiveEventMap]
export interface SahayakVoiceController {
  connect(options: { language: Language; onEvent: (event: LiveEvent) => void }): Promise<void>
  disconnect(): void
  cancelAgentAudio(): void
}

type Props = {
  lang: Language
  setLang: (language: Language) => void
  onBack: () => void
  onReview: () => void
  onSaved?: () => void
  scenario: Scenario
  scenarios: Scenario[]
  loadScenario: (scenario: Scenario) => void
  selectedId: string
  beneficiaryName: string
  visitType: string
  weight: string
  vaccines: string
  nextDate: string
  danger: boolean
  dangerAlert?: string
  dangerAcknowledged: boolean
  setDangerAcknowledged: (value: boolean) => void
}

const ui = {
  en: { live: 'SAHAYAK Live', subtitle: 'A calmer way to capture every visit', ready: 'Ready when you are', start: 'Start voice visit', unavailable: 'Live voice is not connected yet. Your visit is safe; connect the Gnani streaming controller to begin.', language: 'Conversation language', connected: 'Backend connection required', reading: 'Visit summary', unknown: 'Not yet captured', id: 'Beneficiary ID', name: 'Beneficiary', type: 'Visit type', weight: 'Weight', vaccine: 'Vaccinations due', date: 'Next visit', review: 'Review visit details', back: 'Back to dashboard', demo: 'Visual demo', demoNote: 'Sample scenario only · not from microphone audio', choose: 'Explore a sample conversation', demoTranscript: 'Sample transcript', referral: 'Urgent PHC referral required', noAdvice: 'Referral instruction only. No diagnosis or treatment advice.', acknowledge: 'I acknowledge this alert and understand PHC referral is required.', interrupted: 'You can interrupt the assistant at any time', connection: 'Gnani Prisma STT · Timbre TTS pending', editNote: 'This record preview is read-only. Corrections will be spoken when voice streaming is connected.' },
  hi: { live: 'SAHAYAK Live', subtitle: 'हर विज़िट दर्ज करने का सहज तरीका', ready: 'जब आप तैयार हों', start: 'वॉइस विज़िट शुरू करें', unavailable: 'लाइव वॉइस अभी कनेक्ट नहीं है। विज़िट सुरक्षित है; शुरू करने के लिए Gnani streaming controller कनेक्ट करें।', language: 'बातचीत की भाषा', connected: 'बैकएंड कनेक्शन ज़रूरी', reading: 'विज़िट सारांश', unknown: 'अभी दर्ज नहीं', id: 'लाभार्थी ID', name: 'लाभार्थी', type: 'विज़िट का प्रकार', weight: 'वज़न', vaccine: 'बाकी टीके', date: 'अगली विज़िट', review: 'विज़िट विवरण देखें', back: 'डैशबोर्ड पर वापस', demo: 'विज़ुअल डेमो', demoNote: 'केवल नमूना · माइक्रोफ़ोन ऑडियो से नहीं', choose: 'नमूना बातचीत देखें', demoTranscript: 'नमूना ट्रांसक्रिप्ट', referral: 'तत्काल PHC रेफ़रल ज़रूरी', noAdvice: 'केवल रेफ़रल निर्देश। कोई निदान या उपचार सलाह नहीं।', acknowledge: 'मैंने चेतावनी समझ ली है और PHC रेफ़रल की ज़रूरत स्वीकार करता/करती हूँ।', interrupted: 'आप सहायक को कभी भी रोक सकते हैं', connection: 'Gnani Prisma STT · Timbre TTS लंबित', editNote: 'यह रिकॉर्ड केवल देखने के लिए है। वॉइस स्ट्रीमिंग जुड़ने पर सुधार बोलकर होंगे।' },
  kn: { live: 'SAHAYAK Live', subtitle: 'ಪ್ರತಿ ಭೇಟಿಯನ್ನು ದಾಖಲಿಸುವ ಸುಲಭ ವಿಧಾನ', ready: 'ನೀವು ಸಿದ್ಧರಾದಾಗ', start: 'ಧ್ವನಿ ಭೇಟಿ ಪ್ರಾರಂಭಿಸಿ', unavailable: 'ಲೈವ್ ಧ್ವನಿ ಇನ್ನೂ ಸಂಪರ್ಕಗೊಂಡಿಲ್ಲ. ನಿಮ್ಮ ಭೇಟಿ ಸುರಕ್ಷಿತವಾಗಿದೆ; ಪ್ರಾರಂಭಿಸಲು Gnani streaming controller ಸಂಪರ್ಕಿಸಿ.', language: 'ಸಂಭಾಷಣೆಯ ಭಾಷೆ', connected: 'ಬ್ಯಾಕೆಂಡ್ ಸಂಪರ್ಕ ಅಗತ್ಯ', reading: 'ಭೇಟಿ ಸಾರಾಂಶ', unknown: 'ಇನ್ನೂ ದಾಖಲಿಸಿಲ್ಲ', id: 'ಫಲಾನುಭವಿ ID', name: 'ಫಲಾನುಭವಿ', type: 'ಭೇಟಿ ಪ್ರಕಾರ', weight: 'ತೂಕ', vaccine: 'ಬಾಕಿ ಲಸಿಕೆಗಳು', date: 'ಮುಂದಿನ ಭೇಟಿ', review: 'ಭೇಟಿ ವಿವರಗಳನ್ನು ಪರಿಶೀಲಿಸಿ', back: 'ಡ್ಯಾಶ್‌ಬೋರ್ಡ್‌ಗೆ ಹಿಂತಿರುಗಿ', demo: 'ದೃಶ್ಯ ಡೆಮೋ', demoNote: 'ಮಾದರಿ ಸನ್ನಿವೇಶ ಮಾತ್ರ · ಮೈಕ್ರೊಫೋನ್‌ನಿಂದಲ್ಲ', choose: 'ಮಾದರಿ ಸಂಭಾಷಣೆಯನ್ನು ನೋಡಿ', demoTranscript: 'ಮಾದರಿ ಪ್ರತಿಲಿಪಿ', referral: 'ತುರ್ತು PHC ರೆಫರಲ್ ಅಗತ್ಯ', noAdvice: 'ರೆಫರಲ್ ಸೂಚನೆ ಮಾತ್ರ. ರೋಗನಿರ್ಣಯ ಅಥವಾ ಚಿಕಿತ್ಸೆ ಸಲಹೆ ಇಲ್ಲ.', acknowledge: 'ಈ ಎಚ್ಚರಿಕೆಯನ್ನು ಅಂಗೀಕರಿಸಿದ್ದೇನೆ ಮತ್ತು PHC ರೆಫರಲ್ ಅಗತ್ಯವನ್ನು ಅರ್ಥಮಾಡಿಕೊಂಡಿದ್ದೇನೆ.', interrupted: 'ನೀವು ಸಹಾಯಕನನ್ನು ಯಾವಾಗ ಬೇಕಾದರೂ ತಡೆಯಬಹುದು', connection: 'Gnani Prisma STT · Timbre TTS ಸಂಪರ್ಕ ಬಾಕಿ', editNote: 'ಈ ದಾಖಲೆ ಓದಲು ಮಾತ್ರ. ಧ್ವನಿ ಸ್ಟ್ರೀಮಿಂಗ್ ಸಂಪರ್ಕಿಸಿದಾಗ ತಿದ್ದುಪಡಿಗಳನ್ನು ಮಾತನಾಡಬಹುದು.' },
} as const

export function SahayakLiveScreen(props: Props) {
  const { lang, setLang, onBack, onReview, onSaved, scenario, scenarios, loadScenario, selectedId, beneficiaryName, visitType, weight, vaccines, nextDate, danger, dangerAlert, dangerAcknowledged, setDangerAcknowledged } = props
  const t = ui[lang]
  const [connectionError, setConnectionError] = useState(false)
  const [liveStatus, setLiveStatus] = useState('')
  const [isListening, setIsListening] = useState(false)
  const [transcript, setTranscript] = useState('')
  const [voiceError, setVoiceError] = useState('')
  const socketRef = useRef<WebSocket | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const contextRef = useRef<AudioContext | null>(null)
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null)
  const processorRef = useRef<ScriptProcessorNode | null>(null)
  const muteRef = useRef<GainNode | null>(null)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const listeningRef = useRef(false)
  const transcriptRef = useRef('')

  const cleanupAudio = () => {
    listeningRef.current = false
    if (timerRef.current) clearInterval(timerRef.current)
    timerRef.current = null
    if (processorRef.current) processorRef.current.onaudioprocess = null
    processorRef.current?.disconnect()
    sourceRef.current?.disconnect()
    muteRef.current?.disconnect()
    processorRef.current = null
    sourceRef.current = null
    muteRef.current = null
    streamRef.current?.getTracks().forEach(track => track.stop())
    streamRef.current = null
    void contextRef.current?.close()
    contextRef.current = null
  }

  const stopVoice = () => {
    cleanupAudio()
    const socket = socketRef.current
    socketRef.current = null
    if (socket?.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: 'stop_stt' }))
      setTimeout(() => socket.close(), 2500)
    } else socket?.close()
    setIsListening(false)
    setLiveStatus('Recording stopped')
  }

  useEffect(() => () => {
    listeningRef.current = false
    if (timerRef.current) clearInterval(timerRef.current)
    if (processorRef.current) processorRef.current.onaudioprocess = null
    processorRef.current?.disconnect()
    sourceRef.current?.disconnect()
    muteRef.current?.disconnect()
    streamRef.current?.getTracks().forEach(track => track.stop())
    void contextRef.current?.close()
    socketRef.current?.close()
  }, [])

  const startVoice = async () => {
    setVoiceError('')
    setConnectionError(false)
    setLiveStatus('Connecting to Gnani Prisma...')
    let socket: WebSocket | null = null
    let stream: MediaStream | null = null
    try {
      if (!navigator.mediaDevices?.getUserMedia) throw new Error('Microphone access requires localhost or HTTPS')
      stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } })
      streamRef.current = stream
      const url = process.env.NEXT_PUBLIC_WS_URL || `ws://${window.location.hostname}:8000/ws/voice`
      socket = new WebSocket(url)
      socketRef.current = socket
      await new Promise<void>((resolve, reject) => {
        const timeout = window.setTimeout(() => reject(new Error('Voice connection timed out')), 18000)
        socket!.onopen = () => socket!.send(JSON.stringify({ type: 'start_stt' }))
        socket!.onmessage = (message) => {
          try {
            const event = JSON.parse(message.data)
            if (event.type === 'stt_connected') {
              clearTimeout(timeout)
              resolve()
            } else if (event.type === 'stt_transcript' && typeof event.text === 'string') {
              transcriptRef.current = `${transcriptRef.current} ${event.text}`.trim()
              setTranscript(transcriptRef.current)
              socket!.send(JSON.stringify({ type: 'transcript_final', text: event.text }))
            } else if (event.type === 'session_error') {
              setVoiceError(event.message || 'Voice service error')
              if (!listeningRef.current) {
                clearTimeout(timeout)
                reject(new Error(event.message || 'Unable to start STT'))
              }
            } else if (event.type === 'danger_sign_detected') {
              setVoiceError('Urgent danger sign detected. Follow the PHC referral instructions.')
            }
          } catch (error) {
            if (error instanceof SyntaxError) setVoiceError('Invalid server response')
          }
        }
        socket!.onerror = () => { clearTimeout(timeout); reject(new Error('Could not connect to FastAPI WebSocket')) }
        socket!.onclose = () => {
          if (listeningRef.current) {
            cleanupAudio()
            setIsListening(false)
            setVoiceError('Voice connection closed')
          }
        }
      })

      const context = new AudioContext()
      contextRef.current = context
      await context.resume()
      const source = context.createMediaStreamSource(stream)
      const processor = context.createScriptProcessor(4096, 1, 1)
      const mute = context.createGain()
      mute.gain.value = 0
      source.connect(processor)
      processor.connect(mute)
      mute.connect(context.destination)
      sourceRef.current = source
      processorRef.current = processor
      muteRef.current = mute
      const queue: ArrayBuffer[] = []
      const pending: number[] = []
      let phase = 0
      processor.onaudioprocess = event => {
        if (!listeningRef.current) return
        const input = event.inputBuffer.getChannelData(0)
        const step = context.sampleRate / 16000
        while (phase < input.length) {
          const index = Math.min(Math.floor(phase), input.length - 1)
          const next = Math.min(index + 1, input.length - 1)
          const sample = input[index] + (input[next] - input[index]) * (phase - index)
          pending.push(sample)
          if (pending.length === 512) {
            const frame = new ArrayBuffer(1024)
            const view = new DataView(frame)
            for (let i = 0; i < 512; i++) {
              const value = Math.max(-1, Math.min(1, pending[i]))
              view.setInt16(i * 2, value < 0 ? Math.round(value * 32768) : Math.round(value * 32767), true)
            }
            pending.length = 0
            queue.push(frame)
          }
          phase += step
        }
        phase -= input.length
      }
      listeningRef.current = true
      timerRef.current = setInterval(() => {
        if (socket?.readyState === WebSocket.OPEN) {
          if (queue.length) socket.send(queue.shift()!)
          else socket.send(new ArrayBuffer(1024))
        }
      }, 32)
      setIsListening(true)
      setLiveStatus('Listening — speak into your microphone')
    } catch (error) {
      cleanupAudio()
      socket?.close()
      socketRef.current = null
      setIsListening(false)
      setConnectionError(true)
      setVoiceError(error instanceof Error ? error.message : 'Unable to start live voice')
      setLiveStatus('')
    }
  }
  const [enteredId, setEnteredId] = useState('')
  const [matched, setMatched] = useState<{ beneficiary_id: string; name: string; category: string; village: string } | null>(null)
  const [registerMode, setRegisterMode] = useState(false)
  const [newName, setNewName] = useState('')
  const [newCategory, setNewCategory] = useState('general')
  const [newVillage, setNewVillage] = useState('')
  const [editableTranscript, setEditableTranscript] = useState('')
  const [draft, setDraft] = useState<{ visit_type: string | null; weight_kg: number | null; vaccinations_due: string[] | null; next_visit_date: string | null } | null>(null)
  const [working, setWorking] = useState(false)
  const [isExtracting, setIsExtracting] = useState(false)
  const [extractionStatus, setExtractionStatus] = useState('')
  const [saveMessage, setSaveMessage] = useState('')
  const [dangerWarnings, setDangerWarnings] = useState<string[]>([])
  const [acknowledgeDanger, setAcknowledgeDanger] = useState(false)
  const api = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000'
  const requestJson = async (path: string, init?: RequestInit) => {
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), 25000)
    try {
      const response = await fetch(`${api}${path}`, { ...init, signal: controller.signal })
      const body = await response.json().catch(() => { throw new Error('Backend returned invalid JSON') })
      if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : `HTTP ${response.status}`)
      return body
    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') throw new Error('Request timed out after 25 seconds. Check FastAPI/Groq and retry.')
      if (error instanceof TypeError) throw new Error('Cannot reach FastAPI. Check backend port 8000 and CORS.')
      throw error
    } finally { clearTimeout(timeout) }
  }
  const jsonPost = (value: unknown): RequestInit => ({ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(value) })
  const findId = async () => {
    setWorking(true); setSaveMessage(''); setMatched(null)
    try { const result = await requestJson(`/api/beneficiaries/${encodeURIComponent(enteredId.trim())}`); setMatched(result); setRegisterMode(false) }
    catch (e) { setRegisterMode(true); setSaveMessage(e instanceof Error ? e.message : 'Lookup failed') }
    finally { setWorking(false) }
  }
  const registerId = async () => {
    setWorking(true); setSaveMessage('')
    try { const result = await requestJson('/api/beneficiaries/register', jsonPost({ beneficiary_id: enteredId, name: newName, category: newCategory, village: newVillage })); setMatched(result); setRegisterMode(false) }
    catch (e) { setSaveMessage(e instanceof Error ? e.message : 'Registration failed') }
    finally { setWorking(false) }
  }
  const extractDetails = async () => {
    const text = (editableTranscript || transcript).trim()
    if (!text) { setExtractionStatus('Error: Enter or record a transcript before extracting.'); return }
    setIsExtracting(true); setExtractionStatus('Extracting visit details with Qwen...'); setSaveMessage(''); setDraft(null)
    try {
      const result = await requestJson('/api/extract', jsonPost({ text }))
      if (!result?.visit || typeof result.visit !== 'object') throw new Error('Qwen returned no visit object')
      const extracted = result.visit
      if (extracted.visit_type == null && extracted.weight_kg == null && extracted.next_visit_date == null && (!Array.isArray(extracted.vaccinations_due) || extracted.vaccinations_due.length === 0)) {
        throw new Error('Qwen could not extract any visit details. Please clarify the transcript and retry.')
      }
      setDraft({ visit_type: extracted.visit_type ?? null, weight_kg: extracted.weight_kg ?? null, vaccinations_due: extracted.vaccinations_due ?? null, next_visit_date: extracted.next_visit_date ?? null })
      setExtractionStatus('Qwen extraction successful. Review the fields below. Match a beneficiary ID before saving.')
      const risky = /\b(bleeding|high fever|very high fever)\b/i.test(text)
      setDangerWarnings(risky ? ['Possible danger sign in transcript. Follow urgent PHC referral instructions; review before saving.'] : [])
      setAcknowledgeDanger(false)
    } catch (e) { setExtractionStatus(`Qwen extraction failed: ${e instanceof Error ? e.message : 'Unknown error'}`) }
    finally { setIsExtracting(false) }
  }
  const saveDetails = async () => {
    if (!matched) { setSaveMessage('Cannot save: enter the full beneficiary ID (e.g. ASHA103), click Find ID, and confirm the name shown.'); return }
    if (!draft) { setSaveMessage('Cannot save: click Extract visit details with Qwen first.'); return }
    if (!draft.visit_type) { setSaveMessage('Cannot save: select a visit type in the Visit summary.'); return }
    if (!(editableTranscript || transcript).trim()) { setSaveMessage('Cannot save: transcript is empty.'); return }
    if (dangerWarnings.length > 0 && !acknowledgeDanger) { setSaveMessage('Cannot save: acknowledge the urgent referral warning first.'); return }
    setWorking(true); setSaveMessage('')
    try {
      const result = await requestJson('/api/visits/confirm', jsonPost({ beneficiary_id: matched.beneficiary_id, visit: { ...draft, beneficiary_id: matched.beneficiary_id, beneficiary_name: matched.name }, transcript: (editableTranscript || transcript).trim(), acknowledge_danger: acknowledgeDanger }))
      setSaveMessage(`Saved successfully! Visit #${result.visit_id} for ${matched.name} (${result.beneficiary_id})`)
      setDraft(null)
      onSaved?.()
    } catch (e) { setSaveMessage(e instanceof Error ? e.message : 'Save failed') }
    finally { setWorking(false) }
  }
  const fields = [
    { label: t.id, value: matched?.beneficiary_id || '' },
    { label: t.name, value: matched?.name || '' },
    { label: t.type, value: draft?.visit_type || '' },
    { label: t.weight, value: draft?.weight_kg != null ? `${draft.weight_kg} kg` : '' },
    { label: t.vaccine, value: draft?.vaccinations_due?.join(', ') || '' },
    { label: t.date, value: draft?.next_visit_date || '' },
  ]

  return <section className="live-screen" aria-labelledby="live-title">
    <header className="live-header">
      <button className="live-back" onClick={onBack}><ArrowLeft size={17} /><span>{t.back}</span></button>
      <a className="live-brand" href="#live" onClick={(event) => event.preventDefault()}><span className="live-brand-mark"><Activity size={18} /></span><span><b>SAHAYAK</b><small>COMMUNITY HEALTH</small></span></a>
      <label className="live-language"><span className="sr-only">{t.language}</span><select aria-label={t.language} value={lang} onChange={(event) => setLang(event.target.value as Language)}><option value="kn">ಕನ್ನಡ</option><option value="hi">हिन्दी</option><option value="en">English</option></select><ChevronDown size={14} /></label>
    </header>

    {danger && <div className="live-danger" role="alert"><div className="live-danger-icon"><AlertTriangle size={21} /></div><div className="live-danger-copy"><strong>{t.referral}</strong><p>{dangerAlert || t.noAdvice}</p><small>{t.noAdvice}</small><label className="live-ack"><input type="checkbox" checked={dangerAcknowledged} onChange={(event) => setDangerAcknowledged(event.target.checked)} /><span>{t.acknowledge}</span></label></div></div>}

    <div className="live-content">
      <div className="live-main-column">
        <div className="live-intro"><span className="live-kicker"><span className="live-kicker-dot" /> {t.connection}</span><h1 id="live-title">{t.live}</h1><p>{t.subtitle}</p></div>
        <div className="live-record-card" style={{ padding: 20, marginBottom: 18 }}>
          <h2>1. Identify beneficiary (real database)</h2>
          <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
            <input aria-label="Beneficiary ID" placeholder="Enter beneficiary ID (e.g. ASHA103)" value={enteredId} onChange={e => { setEnteredId(e.target.value); setMatched(null); setSaveMessage('') }} style={{ flex: 1, padding: 10, color: '#132c32', background: '#fff' }} />
            <button disabled={working || !enteredId.trim()} onClick={() => void findId()}>Find ID</button>
          </div>
          {matched && <p role="status" style={{ marginTop: 10 }}>Confirmed ID: <b>{matched.beneficiary_id}</b> — {matched.name}, {matched.category}, {matched.village}</p>}
          {registerMode && <div style={{ display: 'grid', gap: 8, marginTop: 10 }}>
            <p>ID not found. Register a fictional beneficiary after verifying identity:</p>
            <input aria-label="New beneficiary name" placeholder="Name" value={newName} onChange={e => setNewName(e.target.value)} />
            <select aria-label="Beneficiary category" value={newCategory} onChange={e => setNewCategory(e.target.value)}><option value="general">General</option><option value="pregnancy">Pregnancy</option><option value="newborn">Newborn</option><option value="child">Child</option><option value="postnatal">Postnatal</option></select>
            <input aria-label="Village" placeholder="Village" value={newVillage} onChange={e => setNewVillage(e.target.value)} />
            <button disabled={working || !newName.trim() || !newVillage.trim()} onClick={() => void registerId()}>Register beneficiary</button>
          </div>}
        </div>
        <div className="live-orb-area">
          <div className="live-orb-rings" aria-hidden="true"><span /><span /><span /><div className="live-orb"><AudioLines size={36} /></div></div>
          <p className="live-orb-caption" role="status" aria-live="polite">{liveStatus || (connectionError ? 'Connection failed' : t.ready)}</p>
          <button className="live-start" onClick={() => isListening ? stopVoice() : void startVoice()}><Mic size={19} />{isListening ? 'Stop voice visit' : t.start}</button>
          {voiceError && <p className="live-error" role="alert"><CircleHelp size={15} />{voiceError}</p>}
          {transcript && <div className="live-demo-transcript" aria-live="polite"><strong>Live transcript</strong><p>{transcript}</p></div>}
          <div style={{ display: 'grid', gap: 8, width: '100%', marginTop: 16 }}>
            <label htmlFor="visit-transcript">2. Review or type visit transcript (microphone optional)</label>
            <textarea id="visit-transcript" rows={4} placeholder="Child visit, weight 13 kilograms..." value={editableTranscript || transcript} onChange={e => setEditableTranscript(e.target.value)} style={{ width: '100%', padding: 12, color: '#132c32', background: '#fff' }} />
            <button type="button" disabled={isExtracting} onClick={() => void extractDetails()} style={{ display: 'inline-flex', justifyContent: 'center', alignItems: 'center', width: '100%', minHeight: 48, padding: '12px 18px', background: isExtracting ? '#64748b' : '#48d3c2', color: '#072b34', border: 'none', borderRadius: 12, fontWeight: 700, cursor: isExtracting ? 'wait' : 'pointer', opacity: isExtracting ? 0.8 : 1 }}>{isExtracting ? 'Extracting with Qwen...' : 'Extract visit details with Qwen'}</button>
            {extractionStatus && <p role="status" aria-live="polite" style={{ color: extractionStatus.toLowerCase().includes('failed') || extractionStatus.startsWith('Error') ? '#ffb4a9' : '#82eadc', fontWeight: 600 }}>{extractionStatus}</p>}
            {saveMessage && <p role="alert" style={{ color: saveMessage.startsWith('Saved successfully') ? '#82eadc' : '#ffb4a9', fontWeight: 700 }}>{saveMessage}</p>}
          </div>
          <p className="live-interrupt"><ShieldCheck size={15} />{t.interrupted}</p>
        </div>
        <div className="live-record-card">
          <div className="live-card-heading"><div><span className="live-card-eyebrow"><Sparkles size={13} />{t.reading}</span><h2>{t.reading}</h2></div><span className="live-capture-pill"><span />{draft ? "Draft — not saved" : t.unknown}</span></div>
          <div className="live-fields" aria-live="polite">{fields.map((field) => <div className="live-field" key={field.label}><span>{field.label}</span><b className={field.value ? '' : 'is-empty'}>{field.value || t.unknown}</b></div>)}</div>
          {draft && <div style={{ display: 'grid', gap: 8, marginTop: 16 }}>
            <label>Visit type<select value={draft.visit_type || ''} onChange={e => setDraft({ ...draft, visit_type: e.target.value })}><option value="">Select</option>{['pregnancy', 'newborn', 'child', 'postnatal', 'general'].map(x => <option key={x} value={x}>{x}</option>)}</select></label>
            <label>Weight (kg)<input type="number" min="0.1" max="300" step="0.1" value={draft.weight_kg ?? ''} onChange={e => setDraft({ ...draft, weight_kg: e.target.value ? Number(e.target.value) : null })} /></label>
            <label>Vaccinations due (comma separated)<input value={draft.vaccinations_due?.join(', ') || ''} onChange={e => setDraft({ ...draft, vaccinations_due: e.target.value ? e.target.value.split(',').map(v => v.trim()).filter(Boolean) : null })} /></label>
            <label>Next visit date<input type="date" value={draft.next_visit_date || ''} onChange={e => setDraft({ ...draft, next_visit_date: e.target.value || null })} /></label>
            {!matched && <p role="status" style={{ color: '#ffcd80' }}>Extraction preview only. Enter a valid beneficiary ID and click Find ID before saving.</p>}
            {dangerWarnings.map(w => <p key={w} role="alert" style={{ color: '#e8ae55' }}>{w}</p>)}
            {dangerWarnings.length > 0 && <label><input type="checkbox" checked={acknowledgeDanger} onChange={e => setAcknowledgeDanger(e.target.checked)} /> I acknowledge the urgent referral warning</label>}
            <button className="live-review" disabled={working} onClick={() => void saveDetails()}>{working ? 'Saving visit...' : 'Confirm & save this visit'}</button>
            {saveMessage && <p role="alert" style={{ color: saveMessage.startsWith('Saved successfully') ? '#82eadc' : '#ffb4a9', fontWeight: 700 }}>{saveMessage}</p>}
          </div>}
          <p className="live-readonly-note">Only the confirmed database beneficiary is used. No automatic save.</p>
        </div>
      </div>

    </div>
  </section>
}
