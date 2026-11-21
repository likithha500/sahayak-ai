
export type VoiceStatus =
  | "disconnected"
  | "connecting"
  | "listening"
  | "thinking"
  | "speaking"
  | "error"

export type VoiceEvent = {
  type: string
  text?: string
  message?: string
  audio?: string
  mime_type?: string
  visit?: Record<string, unknown>
  beneficiary?: Record<string, unknown>
  alert_id?: number
  [key: string]: unknown
}

type VoiceOptions = {
  onStatus: (status: VoiceStatus) => void
  onEvent: (event: VoiceEvent) => void
  language?: "kn" | "hi" | "en"
  beneficiaryId?: string
}

export class LiveVoiceController {
  private socket: WebSocket | null = null
  private stream: MediaStream | null = null
  private recorder: MediaRecorder | null = null
  private context: AudioContext | null = null
  private analyser: AnalyserNode | null = null
  private timer: number | null = null
  private connectionTimer: number | null = null
  private playback: HTMLAudioElement | null = null
  private audioUrl: string | null = null

  private chunks: Blob[] = []
  private active = false
  private recordingStarted = 0
  private lastSpeech = 0
  private heardSpeech = false
  private suppressRecording = false
  private sessionReady = false
  private connectionToken = 0

  private options: VoiceOptions

  constructor(options: VoiceOptions) {
    this.options = options
  }

  private status(status: VoiceStatus) {
    this.options.onStatus(status)
  }

  private fail(message: string) {
    this.disconnect()
    this.status("error")

    this.options.onEvent({
      type: "session_error",
      message,
    })
  }

  async connect(): Promise<void> {
    if (this.active) return

    this.active = true
    this.sessionReady = false
    this.status("connecting")

    try {
      this.stream =
        await navigator.mediaDevices.getUserMedia({
          audio: {
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
          },
        })

      if (!this.active) {
        this.stream.getTracks().forEach(t => t.stop())
        this.stream = null
        return
      }

      this.context = new AudioContext()
      await this.context.resume()

      if (!this.active || !this.context) return

      const source =
        this.context.createMediaStreamSource(this.stream)

      this.analyser = this.context.createAnalyser()
      this.analyser.fftSize = 2048

      source.connect(this.analyser)

      const token = ++this.connectionToken
      const socket = new WebSocket(
        process.env.NEXT_PUBLIC_SAHAYAK_WS_URL ||
        "ws://127.0.0.1:8001/ws/voice"
      )
      this.socket = socket

      this.connectionTimer = window.setTimeout(() => {
        if (this.active && token === this.connectionToken && !this.sessionReady) {
          this.fail("Timed out while initializing the voice session")
        }
      }, 20000)

      socket.onopen = () => {
        if (!this.active || token !== this.connectionToken) return
        try {
          socket.send(JSON.stringify({
            type: "start_session",
            language: this.options.language || "en",
            beneficiary_id: this.options.beneficiaryId,
          }))
        } catch {
          this.fail("Unable to initialize the voice session")
        }
      }

      socket.onmessage = event => {
        if (!this.active || token !== this.connectionToken) return
        try {
          const data = JSON.parse(event.data) as VoiceEvent
          this.handleEvent(data)
        } catch {
          this.fail("Invalid server response")
        }
      }

      socket.onerror = () => {
        if (this.active && token === this.connectionToken) {
          this.fail("Cannot connect to SAHAYAK backend")
        }
      }

      socket.onclose = event => {
        if (this.active && token === this.connectionToken) {
          const reason = event.reason
            .replace(/[\u0000-\u001f\u007f]/g, "")
            .slice(0, 120)
          const closeMessage = reason
            ? `Backend connection closed (code ${event.code}): ${reason}`
            : `Backend connection closed (code ${event.code})`
          this.fail(closeMessage)
        }
      }

    } catch (error) {
      this.fail(
        error instanceof Error
          ? error.message
          : "Unable to access microphone"
      )
    }
  }

  private handleEvent(event: VoiceEvent) {
    if (!this.active) return

    this.options.onEvent(event)

    switch (event.type) {
      case "session_connected":
        break

      case "session_started":
        this.sessionReady = true
        if (this.connectionTimer !== null) {
          window.clearTimeout(this.connectionTimer)
          this.connectionTimer = null
        }
        this.status("thinking")
        break

      case "agent_speaking_started":
        this.suppressRecording = true
        this.stopRecording()
        this.status("thinking")
        break

      case "agent_audio":
        if (event.audio) {
          void this.playAudio(
            event.audio,
            event.mime_type || "audio/wav"
          )
        } else {
          this.fail("Server returned empty audio")
        }
        break

      case "session_error":
        if (event.recoverable === true && this.sessionReady) {
          this.suppressRecording = false
          this.startListening()
        } else {
          this.disconnect()
          this.status("error")
        }
        break
    }
  }

  private startListening() {
    if (
      !this.active ||
      !this.sessionReady ||
      !this.stream ||
      !this.analyser ||
      this.socket?.readyState !== WebSocket.OPEN
    ) return

    if (this.recorder?.state === "recording") return

    this.chunks = []
    this.heardSpeech = false
    this.recordingStarted = performance.now()
    this.lastSpeech = this.recordingStarted

    this.stream.getAudioTracks().forEach(track => {
      track.enabled = true
    })

    try {
      const mimeType =
        MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
          ? "audio/webm;codecs=opus"
          : MediaRecorder.isTypeSupported("audio/webm")
            ? "audio/webm"
            : ""

      const recorder = new MediaRecorder(
        this.stream,
        mimeType ? { mimeType } : undefined
      )

      this.recorder = recorder

      recorder.ondataavailable = event => {
        if (event.data.size > 0) {
          this.chunks.push(event.data)
        }
      }

      recorder.onstop = () => {
        if (!this.active) return

        if (this.suppressRecording) {
          this.chunks = []
          return
        }

        const blob = new Blob(this.chunks, {
          type: recorder.mimeType,
        })

        if (
          this.heardSpeech &&
          blob.size > 0 &&
          this.socket?.readyState === WebSocket.OPEN
        ) {
          this.status("thinking")
          this.socket.send(blob)
        } else {
          this.startListening()
        }
      }

      recorder.onerror = () => {
        this.fail("Microphone recording failed")
      }

      recorder.start(250)
      this.status("listening")
      this.detectSilence()

    } catch {
      this.fail("Unable to start audio recording")
    }
  }

  private detectSilence() {
    if (!this.analyser) return

    const samples = new Float32Array(
      this.analyser.fftSize
    )

    const check = () => {
      if (
        !this.active ||
        !this.analyser ||
        this.recorder?.state !== "recording"
      ) return

      this.analyser.getFloatTimeDomainData(samples)

      let sum = 0

      for (const sample of samples) {
        sum += sample * sample
      }

      const volume = Math.sqrt(sum / samples.length)
      const now = performance.now()

      if (volume > 0.018) {
        this.heardSpeech = true
        this.lastSpeech = now
      }

      const silence = now - this.lastSpeech
      const duration = now - this.recordingStarted

      if (
        (this.heardSpeech &&
          silence > 1500 &&
          duration > 1000) ||
        duration >= 25000
      ) {
        this.stopRecording()
        return
      }

      this.timer = window.setTimeout(check, 100)
    }

    check()
  }

  private stopRecording() {
    if (this.timer !== null) {
      window.clearTimeout(this.timer)
      this.timer = null
    }

    if (this.recorder?.state === "recording") {
      this.recorder.stop()
    }

    this.stream?.getAudioTracks().forEach(track => {
      track.enabled = false
    })
  }

  private async playAudio(
    encoded: string,
    mimeType: string
  ) {
    if (!this.active) return

    try {
      this.releasePlayback()

      const decoded = atob(encoded)
      const bytes = new Uint8Array(decoded.length)

      for (let i = 0; i < decoded.length; i++) {
        bytes[i] = decoded.charCodeAt(i)
      }

      const blob = new Blob([bytes], {
        type: mimeType,
      })

      this.audioUrl = URL.createObjectURL(blob)

      const audio = new Audio(this.audioUrl)
      this.playback = audio

      audio.onended = () => {
        this.releasePlayback()

        if (this.active) {
          this.suppressRecording = false
          this.startListening()
        }
      }

      audio.onerror = () => {
        this.recoverPlayback("Unable to play Gnani audio")
      }

      this.status("speaking")
      await audio.play()

    } catch {
      this.recoverPlayback("Voice playback failed or was blocked")
    }
  }

  private recoverPlayback(message: string) {
    this.releasePlayback()
    this.suppressRecording = false
    this.options.onEvent({
      type: "session_error",
      message: `${message}. You can continue by speaking.`,
      recoverable: true,
    })
    if (this.active && this.sessionReady) {
      this.startListening()
    }
  }

  private releasePlayback() {
    if (this.playback) {
      this.playback.onended = null
      this.playback.onerror = null
      this.playback.pause()
      this.playback = null
    }

    if (this.audioUrl) {
      URL.revokeObjectURL(this.audioUrl)
      this.audioUrl = null
    }
  }

  acknowledgeAlert(alertId: number) {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify({
        type: "acknowledge_alert",
        alert_id: alertId,
      }))
    }
  }

  disconnect() {
    this.active = false
    this.sessionReady = false
    this.connectionToken += 1

    if (this.connectionTimer !== null) {
      window.clearTimeout(this.connectionTimer)
      this.connectionTimer = null
    }

    this.stopRecording()
    this.releasePlayback()

    this.stream?.getTracks().forEach(track => {
      track.stop()
    })

    this.stream = null
    this.recorder = null
    this.analyser = null
    this.chunks = []

    if (this.context) {
      void this.context.close().catch(() => {})
      this.context = null
    }

    if (this.socket) {
      this.socket.close()
      this.socket = null
    }

    this.status("disconnected")
  }
}
