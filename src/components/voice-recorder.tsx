'use client'

import { useEffect, useRef, useState } from 'react'
import { ArrowRight, Mic, Pause, Play, Square } from 'lucide-react'

type RecorderState = 'idle' | 'recording' | 'paused' | 'stopped' | 'error'

type Props = {
  lang: 'kn' | 'hi' | 'en'
  onStateChange: (recording: boolean) => void
  onDurationChange: (seconds: number) => void
  onContinue: () => void
  continueLabel: string
}

const labels = {
  en: { request: 'Allow microphone access to record', start: 'Start recording', pause: 'Pause recording', resume: 'Resume recording', stop: 'Stop recording', ready: 'Ready to record', recording: 'Recording audio on this device', paused: 'Recording paused', stopped: 'Recording complete', permission: 'Microphone permission was denied. Allow access in your browser settings and try again.', unsupported: 'Audio recording is not supported in this browser.', failed: 'Unable to record audio. Check your microphone and try again.', playback: 'Recorded audio playback', playAudio: 'Play recorded audio', pauseAudio: 'Pause playback', local: 'Audio remains on this device. No speech recognition or transcription is active.', permissionDenied: 'Microphone access was denied.' },
  hi: { request: 'रिकॉर्ड करने के लिए माइक्रोफ़ोन की अनुमति दें', start: 'रिकॉर्डिंग शुरू करें', pause: 'रिकॉर्डिंग रोकें', resume: 'रिकॉर्डिंग फिर शुरू करें', stop: 'रिकॉर्डिंग समाप्त करें', ready: 'रिकॉर्ड करने के लिए तैयार', recording: 'इस डिवाइस पर ऑडियो रिकॉर्ड हो रहा है', paused: 'रिकॉर्डिंग रुकी हुई है', stopped: 'रिकॉर्डिंग पूरी हुई', permission: 'माइक्रोफ़ोन की अनुमति नहीं मिली। ब्राउज़र सेटिंग में अनुमति दें और फिर कोशिश करें।', unsupported: 'इस ब्राउज़र में ऑडियो रिकॉर्डिंग उपलब्ध नहीं है।', failed: 'ऑडियो रिकॉर्ड नहीं हो सका। माइक्रोफ़ोन जांचें और फिर कोशिश करें।', playback: 'रिकॉर्ड किए गए ऑडियो का प्लेबैक', playAudio: 'रिकॉर्ड किया ऑडियो चलाएँ', pauseAudio: 'प्लेबैक रोकें', local: 'ऑडियो इसी डिवाइस पर रहता है। वाक् पहचान या ट्रांसक्रिप्शन सक्रिय नहीं है।', permissionDenied: 'माइक्रोफ़ोन की अनुमति नहीं मिली।' },
  kn: { request: 'ರೆಕಾರ್ಡ್ ಮಾಡಲು ಮೈಕ್ರೊಫೋನ್ ಅನುಮತಿಸಿ', start: 'ರೆಕಾರ್ಡಿಂಗ್ ಪ್ರಾರಂಭಿಸಿ', pause: 'ರೆಕಾರ್ಡಿಂಗ್ ವಿರಾಮಗೊಳಿಸಿ', resume: 'ರೆಕಾರ್ಡಿಂಗ್ ಮುಂದುವರಿಸಿ', stop: 'ರೆಕಾರ್ಡಿಂಗ್ ನಿಲ್ಲಿಸಿ', ready: 'ರೆಕಾರ್ಡ್ ಮಾಡಲು ಸಿದ್ಧ', recording: 'ಈ ಸಾಧನದಲ್ಲಿ ಆಡಿಯೊ ರೆಕಾರ್ಡ್ ಆಗುತ್ತಿದೆ', paused: 'ರೆಕಾರ್ಡಿಂಗ್ ವಿರಾಮದಲ್ಲಿದೆ', stopped: 'ರೆಕಾರ್ಡಿಂಗ್ ಪೂರ್ಣಗೊಂಡಿದೆ', permission: 'ಮೈಕ್ರೊಫೋನ್ ಅನುಮತಿ ನಿರಾಕರಿಸಲಾಗಿದೆ. ಬ್ರೌಸರ್ ಸೆಟ್ಟಿಂಗ್‌ಗಳಲ್ಲಿ ಅನುಮತಿಸಿ ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.', unsupported: 'ಈ ಬ್ರೌಸರ್‌ನಲ್ಲಿ ಆಡಿಯೊ ರೆಕಾರ್ಡಿಂಗ್ ಲಭ್ಯವಿಲ್ಲ.', failed: 'ಆಡಿಯೊ ರೆಕಾರ್ಡ್ ಆಗಲಿಲ್ಲ. ಮೈಕ್ರೊಫೋನ್ ಪರಿಶೀಲಿಸಿ ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.', playback: 'ರೆಕಾರ್ಡ್ ಮಾಡಿದ ಆಡಿಯೊ ಪ್ಲೇಬ್ಯಾಕ್', playAudio: 'ರೆಕಾರ್ಡ್ ಮಾಡಿದ ಆಡಿಯೊ ಪ್ಲೇ ಮಾಡಿ', pauseAudio: 'ಪ್ಲೇಬ್ಯಾಕ್ ವಿರಾಮಗೊಳಿಸಿ', local: 'ಆಡಿಯೊ ಈ ಸಾಧನದಲ್ಲೇ ಇರುತ್ತದೆ. ಮಾತಿನ ಗುರುತಿಸುವಿಕೆ ಅಥವಾ ಪ್ರತಿಲಿಪಿ ಸಕ್ರಿಯವಾಗಿಲ್ಲ.', permissionDenied: 'ಮೈಕ್ರೊಫೋನ್ ಅನುಮತಿ ನಿರಾಕರಿಸಲಾಗಿದೆ.' },
} as const

function pcmFrame(samples: number[]): ArrayBuffer {
  const buffer = new ArrayBuffer(1024)
  const view = new DataView(buffer)
  samples.forEach((sample, i) => {
    const clipped = Math.max(-1, Math.min(1, sample))
    view.setInt16(i * 2, clipped < 0 ? clipped * 32768 : clipped * 32767, true)
  })
  return buffer
}

export function VoiceRecorder({ lang, onStateChange, onDurationChange, onContinue, continueLabel }: Props) {
  const text = labels[lang]
  const [state, setState] = useState<RecorderState>('idle')
  const [error, setError] = useState('')
  const [audioUrl, setAudioUrl] = useState('')
  const [playing, setPlaying] = useState(false)
  const [transcript, setTranscript] = useState('')
  const [sttStatus, setSttStatus] = useState('Not connected')
  const [levels, setLevels] = useState<number[]>(Array(37).fill(8))
  const recorderRef = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const chunksRef = useRef<BlobPart[]>([])
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const audioUrlRef = useRef('')
  const startedAtRef = useRef(0)
  const elapsedRef = useRef(0)
  const animationRef = useRef<number | null>(null)
  const audioContextRef = useRef<AudioContext | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const mountedRef = useRef(true)
  const failedRef = useRef(false)
  const socketRef = useRef<WebSocket | null>(null)
  const processorRef = useRef<ScriptProcessorNode | null>(null)
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null)
  const muteRef = useRef<GainNode | null>(null)
  const pcmPendingRef = useRef<number[]>([])
  const pcmQueueRef = useRef<ArrayBuffer[]>([])
  const sendTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const isPausedRef = useRef(false)
  const transcriptRef = useRef('')

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      if (animationRef.current !== null) cancelAnimationFrame(animationRef.current)
      if (recorderRef.current?.state !== 'inactive') recorderRef.current?.stop()
      streamRef.current?.getTracks().forEach((track) => track.stop())
      if (sendTimerRef.current) clearInterval(sendTimerRef.current)
      socketRef.current?.close()
      processorRef.current?.disconnect()
      sourceRef.current?.disconnect()
      muteRef.current?.disconnect()
      void audioContextRef.current?.close()
      if (audioUrlRef.current) URL.revokeObjectURL(audioUrlRef.current)
    }
  }, [])

  useEffect(() => {
    if (state !== 'recording') return
    const timer = window.setInterval(() => {
      const seconds = elapsedRef.current + Math.floor((Date.now() - startedAtRef.current) / 1000)
      onDurationChange(seconds)
    }, 250)
    const draw = () => {
      const analyser = analyserRef.current
      if (analyser) {
        const values = new Uint8Array(analyser.frequencyBinCount)
        analyser.getByteFrequencyData(values)
        setLevels(Array.from({ length: 37 }, (_, index) => 8 + (values[Math.floor(index * values.length / 37)] / 255) * 48))
      }
      animationRef.current = requestAnimationFrame(draw)
    }
    animationRef.current = requestAnimationFrame(draw)
    return () => {
      window.clearInterval(timer)
      if (animationRef.current !== null) cancelAnimationFrame(animationRef.current)
      animationRef.current = null
    }
  }, [state, onDurationChange])

  const stopLiveStream = () => {
    if (sendTimerRef.current) clearInterval(sendTimerRef.current)
    sendTimerRef.current = null
    processorRef.current?.disconnect()
    sourceRef.current?.disconnect()
    muteRef.current?.disconnect()
    processorRef.current = null
    sourceRef.current = null
    muteRef.current = null
    const socket = socketRef.current
    if (socket?.readyState === WebSocket.OPEN) {
      const pending = pcmPendingRef.current
      if (pending.length) {
        while (pending.length < 512) pending.push(0)
        pcmQueueRef.current.push(pcmFrame(pending.splice(0, 512)))
      }
      const flush = setInterval(() => {
        if (socket.readyState !== WebSocket.OPEN) { clearInterval(flush); return }
        const frame = pcmQueueRef.current.shift()
        if (frame) socket.send(frame)
        else {
          clearInterval(flush)
          socket.send(JSON.stringify({ type: 'stop_stt' }))
          setTimeout(() => { if (socket.readyState === WebSocket.OPEN) socket.close() }, 3500)
        }
      }, 32)
    } else socket?.close()
    pcmPendingRef.current = []
  }

  const stop = () => {
    stopLiveStream()
    const recorder = recorderRef.current
    if (recorder?.state === 'recording') {
      elapsedRef.current += Math.floor((Date.now() - startedAtRef.current) / 1000)
      onDurationChange(elapsedRef.current)
    }
    if (recorder && recorder.state !== 'inactive') recorder.stop()
    streamRef.current?.getTracks().forEach((track) => track.stop())
    streamRef.current = null
    void audioContextRef.current?.close()
    audioContextRef.current = null
    analyserRef.current = null
    onStateChange(false)
  }

  const start = async () => {
    setError('')
    setTranscript('')
    transcriptRef.current = ''
    setSttStatus('Connecting to Prisma...')
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      setError(text.unsupported)
      setState('error')
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      if (!mountedRef.current) {
        stream.getTracks().forEach((track) => track.stop())
        return
      }
      isPausedRef.current = false
      pcmPendingRef.current = []
      pcmQueueRef.current = []
      failedRef.current = false
      const preferredType = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4'].find((type) => MediaRecorder.isTypeSupported(type))
      const recorder = new MediaRecorder(stream, preferredType ? { mimeType: preferredType } : undefined)
      streamRef.current = stream
      recorderRef.current = recorder
      chunksRef.current = []
      elapsedRef.current = 0
      onDurationChange(0)
      if (audioUrlRef.current) URL.revokeObjectURL(audioUrlRef.current)
      audioUrlRef.current = ''
      setAudioUrl('')
      recorder.ondataavailable = (event) => { if (event.data.size) chunksRef.current.push(event.data) }
      recorder.onerror = () => {
        failedRef.current = true
        setError(text.failed)
        stop()
        setState('error')
      }
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' })
        if (blob.size && mountedRef.current) {
          const url = URL.createObjectURL(blob)
          audioUrlRef.current = url
          setAudioUrl(url)
        }
        if (mountedRef.current) setState(failedRef.current ? 'error' : 'stopped')
        stream.getTracks().forEach((track) => track.stop())
      }
      try {
        const context = new AudioContext()
        const source = context.createMediaStreamSource(stream)
        const analyser = context.createAnalyser()
        analyser.fftSize = 128
        source.connect(analyser)
        audioContextRef.current = context
        analyserRef.current = analyser
      } catch {
        analyserRef.current = null
      }
      // Establish a persistent backend WebSocket before streaming PCM.
      const wsUrl = (process.env.NEXT_PUBLIC_WS_URL || 'ws://127.0.0.1:8000/ws/voice')
      const socket = new WebSocket(wsUrl)
      socketRef.current = socket
      await new Promise<void>((resolve, reject) => {
        const timeout = setTimeout(() => reject(new Error('WebSocket connection timed out')), 12000)
        socket.onopen = () => socket.send(JSON.stringify({ type: 'start_stt' }))
        socket.onerror = () => { clearTimeout(timeout); reject(new Error('WebSocket connection failed')) }
        socket.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data)
            if (data.type === 'stt_connected') { clearTimeout(timeout); setSttStatus('Live transcription connected'); resolve() }
            if (data.type === 'stt_transcript' && typeof data.text === 'string') {
              transcriptRef.current = `${transcriptRef.current} ${data.text}`.trim()
              setTranscript(transcriptRef.current)
              // Route recognized speech through existing safety and visit logic.
              socket.send(JSON.stringify({ type: 'transcript_final', text: data.text }))
            }
            if (data.type === 'session_error') { setSttStatus(data.message || 'Speech recognition error') }
          } catch { /* Ignore malformed server events. */ }
        }
      })

      const context = audioContextRef.current || new AudioContext()
      if (!audioContextRef.current) audioContextRef.current = context
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
      let fractionalPosition = 0
      let previousSample = 0
      processor.onaudioprocess = (event) => {
        if (isPausedRef.current) return
        const input = event.inputBuffer.getChannelData(0)
        const step = context.sampleRate / 16000
        // Interpolate across callback boundaries, producing 16 kHz mono samples.
        for (let position = fractionalPosition; position < input.length; position += step) {
          const index = Math.floor(position)
          const fraction = position - index
          const left = index >= 0 ? input[index] : previousSample
          const right = input[Math.min(index + 1, input.length - 1)]
          pcmPendingRef.current.push(left + (right - left) * fraction)
          if (pcmPendingRef.current.length >= 512) {
            pcmQueueRef.current.push(pcmFrame(pcmPendingRef.current.splice(0, 512)))
          }
          fractionalPosition = position + step - input.length
        }
        previousSample = input[input.length - 1]
      }
      sendTimerRef.current = setInterval(() => {
        if (socket.readyState === WebSocket.OPEN && pcmQueueRef.current.length) {
          socket.send(pcmQueueRef.current.shift()!)
        }
      }, 32)

      recorder.start(250)
      startedAtRef.current = Date.now()
      setState('recording')
      onStateChange(true)
    } catch (cause) {
      const denied = cause instanceof DOMException && (cause.name === 'NotAllowedError' || cause.name === 'SecurityError')
      stopLiveStream()
      streamRef.current?.getTracks().forEach((track) => track.stop())
      void audioContextRef.current?.close()
      audioContextRef.current = null
      setError(denied ? text.permission : text.failed)
      setState('error')
      onStateChange(false)
    }
  }

  const togglePause = () => {
    const recorder = recorderRef.current
    if (!recorder || (recorder.state !== 'recording' && recorder.state !== 'paused')) return
    if (recorder.state === 'recording') {
      elapsedRef.current += Math.floor((Date.now() - startedAtRef.current) / 1000)
      isPausedRef.current = true
      recorder.pause()
      setState('paused')
    } else {
      startedAtRef.current = Date.now()
      isPausedRef.current = false
      recorder.resume()
      setState('recording')
    }
  }

  const status = state === 'recording' ? text.recording : state === 'paused' ? text.paused : state === 'stopped' ? text.stopped : text.ready
  const canPause = recorderRef.current && typeof recorderRef.current.pause === 'function'
  const elapsed = elapsedRef.current + (state === 'recording' ? (Date.now() - startedAtRef.current) / 1000 : 0)
  const timerLabel = `${String(Math.floor(elapsed / 60)).padStart(2, '0')}:${String(Math.floor(elapsed % 60)).padStart(2, '0')}`

  return <>
    <div className={`mic-stage ${state === 'recording' ? 'is-recording' : ''}`}>
      <div className="waveform" aria-hidden="true">{levels.map((level, index) => <i key={index} style={{ '--bar': `${level}px` } as React.CSSProperties} />)}</div>
      <div className="recorder-actions">
        {state === 'idle' || state === 'error' || state === 'stopped' ? <button className="mic-button" aria-label={text.start} title={text.start} onClick={() => void start()}><Mic size={28} /></button> : <>
          {canPause && <button className="recorder-control" aria-label={state === 'paused' ? text.resume : text.pause} title={state === 'paused' ? text.resume : text.pause} onClick={togglePause}>{state === 'paused' ? <Play size={18} /> : <Pause size={18} />}</button>}
          <button className="mic-button stop-recording" aria-label={text.stop} title={text.stop} onClick={stop}><Square size={25} fill="currentColor" /></button>
        </>}
      </div>
      <div className="mic-status" role="status" aria-live="polite">{state === 'idle' ? text.request : status}</div>
      <div className="record-time"><span className={state === 'recording' ? 'live-dot' : ''} />{timerLabel} <span>·</span> {status}</div>
    </div>
    {error && <p className="recorder-error" role="alert">{error}</p>}
    <div className="recorder-note"><Mic size={15} /><span>{sttStatus}</span></div>
    <div className="recorded-audio" aria-live="polite"><div><b>Live transcript</b><p>{transcript || 'Speak into your microphone to see recognized speech here.'}</p></div></div>
    {audioUrl && <div className="recorded-audio"><div><b>{text.playback}</b><small>{text.stopped}</small></div><button className="recorder-control" aria-label={playing ? text.pauseAudio : text.playAudio} onClick={() => { const audio = audioRef.current; if (!audio) return; if (playing) audio.pause(); else void audio.play() }}><span className="sr-only">{playing ? text.pauseAudio : text.playAudio}</span>{playing ? <Pause size={17} /> : <Play size={17} />}</button><audio ref={audioRef} src={audioUrl} controls preload="metadata" onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onEnded={() => setPlaying(false)} aria-label={text.playback} /></div>}
    <div className="voice-footer"><button className="button-primary" onClick={() => { if (recorderRef.current?.state !== 'inactive' && recorderRef.current) stop(); onContinue() }}>{continueLabel}<ArrowRight size={17} /></button></div>
  </>
}
