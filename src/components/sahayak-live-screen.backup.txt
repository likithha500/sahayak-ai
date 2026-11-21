'use client'

import { useMemo, useState } from 'react'
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
  const { lang, setLang, onBack, onReview, scenario, scenarios, loadScenario, selectedId, beneficiaryName, visitType, weight, vaccines, nextDate, danger, dangerAlert, dangerAcknowledged, setDangerAcknowledged } = props
  const t = ui[lang]
  const [connectionError, setConnectionError] = useState(false)
  const [demoScenario, setDemoScenario] = useState<Scenario | null>(null)
  const demoFields = demoScenario === scenario
  const fields = useMemo(() => [
    { label: t.id, value: demoFields ? selectedId : '' },
    { label: t.name, value: demoFields ? beneficiaryName : '' },
    { label: t.type, value: demoFields ? visitType : '' },
    { label: t.weight, value: demoFields && weight ? `${weight} kg` : '' },
    { label: t.vaccine, value: demoFields ? vaccines : '' },
    { label: t.date, value: demoFields ? nextDate : '' },
  ], [t, demoFields, selectedId, beneficiaryName, visitType, weight, vaccines, nextDate])

  return <section className="live-screen" aria-labelledby="live-title">
    <header className="live-header">
      <button className="live-back" onClick={onBack}><ArrowLeft size={17}/><span>{t.back}</span></button>
      <a className="live-brand" href="#live" onClick={(event) => event.preventDefault()}><span className="live-brand-mark"><Activity size={18}/></span><span><b>SAHAYAK</b><small>COMMUNITY HEALTH</small></span></a>
      <label className="live-language"><span className="sr-only">{t.language}</span><select aria-label={t.language} value={lang} onChange={(event) => setLang(event.target.value as Language)}><option value="kn">ಕನ್ನಡ</option><option value="hi">हिन्दी</option><option value="en">English</option></select><ChevronDown size={14}/></label>
    </header>

    {danger && <div className="live-danger" role="alert"><div className="live-danger-icon"><AlertTriangle size={21}/></div><div className="live-danger-copy"><strong>{t.referral}</strong><p>{dangerAlert || t.noAdvice}</p><small>{t.noAdvice}</small><label className="live-ack"><input type="checkbox" checked={dangerAcknowledged} onChange={(event) => setDangerAcknowledged(event.target.checked)}/><span>{t.acknowledge}</span></label></div></div>}

    <div className="live-content">
      <div className="live-main-column">
        <div className="live-intro"><span className="live-kicker"><span className="live-kicker-dot"/> {t.connection}</span><h1 id="live-title">{t.live}</h1><p>{t.subtitle}</p></div>
        <div className="live-orb-area">
          <div className="live-orb-rings" aria-hidden="true"><span/><span/><span/><div className="live-orb"><AudioLines size={36}/></div></div>
          <p className="live-orb-caption" role="status" aria-live="polite">{connectionError ? t.unavailable : t.ready}</p>
          <button className="live-start" onClick={() => setConnectionError(true)}><Mic size={19}/>{t.start}</button>
          {connectionError && <p className="live-error" role="alert"><CircleHelp size={15}/>{t.unavailable}</p>}
          <p className="live-interrupt"><ShieldCheck size={15}/>{t.interrupted}</p>
        </div>
        <div className="live-record-card">
          <div className="live-card-heading"><div><span className="live-card-eyebrow"><Sparkles size={13}/>{t.reading}</span><h2>{t.reading}</h2></div><span className="live-capture-pill"><span/>{t.unknown}</span></div>
          <div className="live-fields" aria-live="polite">{fields.map((field) => <div className="live-field" key={field.label}><span>{field.label}</span><b className={field.value ? '' : 'is-empty'}>{field.value || t.unknown}</b></div>)}</div>
          <p className="live-readonly-note">{t.editNote}</p>
          <button className="live-review" onClick={onReview}>{t.review}<ArrowLeft size={15}/></button>
        </div>
      </div>
      <aside className="live-side-column">
        <div className="live-connect-card"><span className="live-connect-icon"><Mic size={17}/></span><div><b>{t.ready}</b><small>{t.connected}</small></div><span className="live-connection-dot"/></div>
        <section className="live-demo-card"><div className="live-demo-heading"><span>{t.demo}</span><span className="live-demo-dot"/></div><p>{t.demoNote}</p><h2>{t.choose}</h2>
          <div className="live-scenarios">{scenarios.map((item) => <button key={item.id} className={`live-scenario ${demoScenario?.id === item.id ? 'active' : ''}`} onClick={() => { loadScenario(item); setDemoScenario(item); setConnectionError(false) }}><span className="live-scenario-mark">{item.danger ? <AlertTriangle size={15}/> : <Mic size={15}/>}</span><span><b>{item.title}</b><small>{item.description}</small></span><span className="live-check">{demoScenario?.id === item.id && <Check size={13}/>}</span></button>)}</div>
          {demoFields && <div className="live-demo-transcript"><span><AudioLines size={13}/>{t.demoTranscript}</span><p>{scenario.transcript}</p></div>}
        </section>
        {danger && <div className="live-safety-note"><ShieldCheck size={16}/><p>{t.noAdvice}</p></div>}
      </aside>
    </div>
  </section>
}
