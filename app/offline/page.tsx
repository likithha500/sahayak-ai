
"use client"

import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react"

import {
  getAudioVisits,
  saveAudioVisit,
  uploadPendingAudio,
  type OfflineAudioVisit,
} from "@/src/services/offline-queue"

import OfflineServiceWorker from "@/src/components/offline-service-worker"

type RecordingPreview = {
  blob: Blob
  mimeType: string
  durationSeconds: number
}

function chooseMimeType(): string | undefined {
  if (typeof MediaRecorder === "undefined") {
    return undefined
  }

  const supportedTypes = [
    "audio/webm;codecs=opus",
    "audio/mp4",
    "audio/webm",
    "audio/ogg;codecs=opus",
  ]

  return supportedTypes.find((type) =>
    MediaRecorder.isTypeSupported(type)
  )
}

function formatDuration(seconds: number): string {
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = seconds % 60

  return `${String(minutes).padStart(2, "0")}:${String(
    remainingSeconds
  ).padStart(2, "0")}`
}

export default function OfflineAudioPage() {
  const [beneficiaryId, setBeneficiaryId] = useState("")
  const [visits, setVisits] = useState<OfflineAudioVisit[]>([])
  const [recording, setRecording] = useState(false)
  const [preview, setPreview] =
    useState<RecordingPreview | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(
    null
  )

  const [message, setMessage] = useState("")
  const [elapsed, setElapsed] = useState(0)
  const [syncing, setSyncing] = useState(false)
  const [online, setOnline] = useState(true)
  const [loading, setLoading] = useState(true)

  const recorderRef = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const startedAtRef = useRef(0)

  const intervalRef =
    useRef<ReturnType<typeof setInterval> | null>(null)

  const previewUrlRef = useRef<string | null>(null)
  const syncInProgressRef = useRef(false)
  const mountedRef = useRef(true)

  // ----------------------------------------------
  // LOAD SAVED RECORDINGS
  // ----------------------------------------------

  const refresh = useCallback(async () => {
    try {
      const saved = await getAudioVisits()

      saved.sort((a, b) =>
        b.recordedAt.localeCompare(a.recordedAt)
      )

      if (mountedRef.current) {
        setVisits(saved)
      }
    } catch (error) {
      console.error("Failed to load offline audio:", error)

      if (mountedRef.current) {
        setMessage("Unable to load locally saved audio.")
      }
    } finally {
      if (mountedRef.current) {
        setLoading(false)
      }
    }
  }, [])

  useEffect(() => {
    mountedRef.current = true
    void refresh()

    return () => {
      mountedRef.current = false
    }
  }, [refresh])

  // ----------------------------------------------
  // BROWSER CONNECTION STATUS
  // ----------------------------------------------

  useEffect(() => {
    setOnline(navigator.onLine)

    const handleOnline = () => setOnline(true)
    const handleOffline = () => setOnline(false)

    window.addEventListener("online", handleOnline)
    window.addEventListener("offline", handleOffline)

    return () => {
      window.removeEventListener("online", handleOnline)
      window.removeEventListener("offline", handleOffline)
    }
  }, [])

  // ----------------------------------------------
  // CLEAN UP MICROPHONE AND OBJECT URLS
  // ----------------------------------------------

  useEffect(() => {
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
      }

      if (recorderRef.current?.state === "recording") {
        recorderRef.current.stop()
      }

      streamRef.current
        ?.getTracks()
        .forEach((track) => track.stop())

      if (previewUrlRef.current) {
        URL.revokeObjectURL(previewUrlRef.current)
      }
    }
  }, [])

  function updatePreviewUrl(blob: Blob) {
    if (previewUrlRef.current) {
      URL.revokeObjectURL(previewUrlRef.current)
    }

    const url = URL.createObjectURL(blob)

    previewUrlRef.current = url
    setPreviewUrl(url)
  }

  // ----------------------------------------------
  // START AUDIO RECORDING
  // ----------------------------------------------

  async function startRecording() {
    if (
      typeof MediaRecorder === "undefined" ||
      !navigator.mediaDevices?.getUserMedia
    ) {
      setMessage(
        "Audio recording is not supported in this browser."
      )
      return
    }

    if (recording) return

    try {
      setMessage("")
      setPreview(null)

      if (previewUrlRef.current) {
        URL.revokeObjectURL(previewUrlRef.current)
        previewUrlRef.current = null
        setPreviewUrl(null)
      }

      const stream =
        await navigator.mediaDevices.getUserMedia({
          audio: true,
        })

      streamRef.current = stream
      chunksRef.current = []

      const mimeType = chooseMimeType()

      const recorder = new MediaRecorder(
        stream,
        mimeType ? { mimeType } : undefined
      )

      recorderRef.current = recorder

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data)
        }
      }

      recorder.onstop = () => {
        const actualType =
          recorder.mimeType ||
          chunksRef.current[0]?.type ||
          "application/octet-stream"

        const blob = new Blob(chunksRef.current, {
          type: actualType,
        })

        const durationSeconds = Math.max(
          1,
          Math.round(
            (Date.now() - startedAtRef.current) / 1000
          )
        )

        stream
          .getTracks()
          .forEach((track) => track.stop())

        streamRef.current = null
        recorderRef.current = null

        if (blob.size === 0) {
          setMessage(
            "The recording was empty. Please try again."
          )
          return
        }

        setPreview({
          blob,
          mimeType: actualType,
          durationSeconds,
        })

        updatePreviewUrl(blob)

        setMessage(
          "Recording complete. Review and save it offline."
        )
      }

      recorder.onerror = () => {
        stream
          .getTracks()
          .forEach((track) => track.stop())

        streamRef.current = null
        recorderRef.current = null

        if (intervalRef.current) {
          clearInterval(intervalRef.current)
          intervalRef.current = null
        }

        setRecording(false)
        setMessage("Recording failed. Please try again.")
      }

      startedAtRef.current = Date.now()
      setElapsed(0)

      recorder.start(1000)
      setRecording(true)

      intervalRef.current = setInterval(() => {
        setElapsed(
          Math.floor(
            (Date.now() - startedAtRef.current) / 1000
          )
        )
      }, 500)
    } catch (error) {
      console.error("Microphone error:", error)

      streamRef.current
        ?.getTracks()
        .forEach((track) => track.stop())

      streamRef.current = null

      setMessage(
        "Unable to access microphone. Check browser permissions."
      )
    }
  }

  // ----------------------------------------------
  // STOP AUDIO RECORDING
  // ----------------------------------------------

  function stopRecording() {
    const recorder = recorderRef.current

    if (recorder?.state === "recording") {
      recorder.stop()
    }

    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }

    setRecording(false)
  }

  // ----------------------------------------------
  // SAVE AUDIO INTO INDEXEDDB
  // ----------------------------------------------

  async function saveRecording() {
    if (!preview) {
      setMessage("Please record audio first.")
      return
    }

    if (!beneficiaryId.trim()) {
      setMessage("Please enter a beneficiary ID.")
      return
    }

    const visit: OfflineAudioVisit = {
      clientRecordId: crypto.randomUUID(),
      beneficiaryId: beneficiaryId.trim(),
      recordedAt: new Date().toISOString(),
      audio: preview.blob,
      mimeType: preview.mimeType,
      durationSeconds: preview.durationSeconds,
      status: "pending",
    }

    try {
      await saveAudioVisit(visit)

      setPreview(null)
      setBeneficiaryId("")

      if (previewUrlRef.current) {
        URL.revokeObjectURL(previewUrlRef.current)
        previewUrlRef.current = null
        setPreviewUrl(null)
      }

      setMessage(
        `Audio saved on this device. Record ID: ${visit.clientRecordId}`
      )

      await refresh()
    } catch (error) {
      console.error("IndexedDB save error:", error)

      setMessage(
        "Unable to save audio locally. Do not close the page; please try again."
      )
    }
  }

  // ----------------------------------------------
  // SYNCHRONIZE PENDING AUDIO
  // ----------------------------------------------

  const syncAudio = useCallback(async () => {
    if (syncInProgressRef.current) return

    syncInProgressRef.current = true
    setSyncing(true)
    setMessage("Checking and uploading pending audio...")

    try {
      const result = await uploadPendingAudio()

      await refresh()

      if (mountedRef.current) {
        if (result.uploaded === 0 && result.failed === 0) {
          setMessage("No pending recordings to synchronize.")
        } else if (result.failed > 0) {
          setMessage(
            `Uploaded ${result.uploaded} recording(s). ${result.failed} remain pending. Please retry when the backend is available.`
          )
        } else {
          setMessage(
            `Successfully uploaded ${result.uploaded} recording(s). Awaiting transcription and review.`
          )
        }
      }
    } catch (error) {
      console.error("Audio sync error:", error)

      if (mountedRef.current) {
        setMessage(
          "Synchronization failed. Audio remains saved on this device."
        )
      }
    } finally {
      syncInProgressRef.current = false

      if (mountedRef.current) {
        setSyncing(false)
      }
    }
  }, [refresh])

  // ----------------------------------------------
  // AUTOMATIC RETRY WHEN CONNECTION RETURNS
  // ----------------------------------------------

  useEffect(() => {
    const handleReconnect = () => {
      setOnline(true)
      void syncAudio()
    }

    window.addEventListener("online", handleReconnect)

    return () => {
      window.removeEventListener(
        "online",
        handleReconnect
      )
    }
  }, [syncAudio])

  // ----------------------------------------------
  // RETRY WHEN APP IS REOPENED
  // ----------------------------------------------

  useEffect(() => {
    if (navigator.onLine) {
      void syncAudio()
    }
  }, [syncAudio])

  const pendingCount = visits.filter(
    (visit) => visit.status === "pending"
  ).length

  const uploadedCount = visits.filter(
    (visit) => visit.status === "uploaded"
  ).length

  return (
    <main className="mx-auto max-w-3xl p-6">
      <OfflineServiceWorker />

      {/* HEADER */}

      <div className="mb-6">
        <h1 className="mb-2 text-3xl font-bold">
          SAHAYAK AI — Offline Audio Visits
        </h1>

        <p className="text-sm text-gray-600">
          Record household visits without internet.
          Audio is stored locally and synchronized when
          the backend becomes available.
        </p>
      </div>

      {/* CONNECTION STATUS */}

      <div className="mb-6 flex flex-wrap items-center gap-3">
        <span
          className={`rounded-full px-4 py-2 text-sm font-medium ${
            online
              ? "bg-green-100 text-green-800"
              : "bg-red-100 text-red-800"
          }`}
        >
          {online
            ? "Browser reports online"
            : "Offline mode"}
        </span>

        <span className="rounded-full bg-amber-100 px-4 py-2 text-sm font-medium text-amber-800">
          Pending: {pendingCount}
        </span>

        <span className="rounded-full bg-blue-100 px-4 py-2 text-sm font-medium text-blue-800">
          Uploaded: {uploadedCount}
        </span>
      </div>

      {/* AUDIO RECORDING FORM */}

      <section className="mb-8 space-y-5 rounded-xl border p-5">
        <h2 className="text-xl font-semibold">
          Record Household Visit
        </h2>

        <div>
          <label
            htmlFor="beneficiary"
            className="mb-2 block font-medium"
          >
            Beneficiary ID
          </label>

          <input
            id="beneficiary"
            value={beneficiaryId}
            onChange={(event) =>
              setBeneficiaryId(event.target.value)
            }
            placeholder="Example: ASHA102"
            maxLength={80}
            disabled={recording}
            className="w-full rounded-lg border p-3"
          />
        </div>

        <div className="flex flex-wrap items-center gap-4">
          {!recording ? (
            <button
              type="button"
              onClick={startRecording}
              className="rounded-lg bg-blue-700 px-5 py-3 font-medium text-white"
            >
              🎤 Start Recording
            </button>
          ) : (
            <button
              type="button"
              onClick={stopRecording}
              className="rounded-lg bg-red-700 px-5 py-3 font-medium text-white"
            >
              ⏹ Stop Recording
            </button>
          )}

          {recording && (
            <span
              role="status"
              className="font-medium text-red-700"
            >
              ● Recording {formatDuration(elapsed)}
            </span>
          )}
        </div>

        {/* RECORDING PREVIEW */}

        {preview && previewUrl && (
          <div className="space-y-4 rounded-lg border p-4">
            <p className="font-medium">
              Recording Preview
            </p>

            <p className="text-sm text-gray-600">
              Duration:{" "}
              {formatDuration(preview.durationSeconds)}
            </p>

            <audio
              controls
              src={previewUrl}
              className="w-full"
            />

            <button
              type="button"
              onClick={saveRecording}
              className="rounded-lg bg-green-700 px-5 py-3 font-medium text-white"
            >
              Save Audio Offline
            </button>
          </div>
        )}
      </section>

      {/* SYNC BUTTON */}

      <section className="mb-8 rounded-xl border p-5">
        <h2 className="mb-2 text-xl font-semibold">
          Synchronization
        </h2>

        <p className="mb-4 text-sm text-gray-600">
          Pending audio is uploaded to FastAPI when
          connectivity is available. Uploading does
          not confirm or finalize a visit.
        </p>

        <button
          type="button"
          onClick={() => void syncAudio()}
          disabled={syncing || pendingCount === 0}
          className="rounded-lg bg-indigo-700 px-5 py-3 font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
        >
          {syncing
            ? "Synchronizing..."
            : "Sync Pending Audio"}
        </button>
      </section>

      {/* STATUS MESSAGE */}

      {message && (
        <div
          role="status"
          className="mb-6 rounded-lg border p-4 text-sm"
        >
          {message}
        </div>
      )}

      {/* SAVED AUDIO QUEUE */}

      <section>
        <h2 className="mb-4 text-2xl font-semibold">
          Audio Visit Queue ({visits.length})
        </h2>

        {loading ? (
          <p>Loading recordings...</p>
        ) : visits.length === 0 ? (
          <p className="text-gray-600">
            No audio recordings saved yet.
          </p>
        ) : (
          <div className="space-y-4">
            {visits.map((visit) => (
              <SavedAudioCard
                key={visit.clientRecordId}
                visit={visit}
              />
            ))}
          </div>
        )}
      </section>

      <p className="mt-8 text-xs text-gray-500">
        Development prototype. Use synthetic test
        recordings only. Audio is not yet encrypted
        in browser storage.
      </p>
    </main>
  )
}

// ==================================================
// SAVED AUDIO CARD
// ==================================================

function SavedAudioCard({
  visit,
}: {
  visit: OfflineAudioVisit
}) {
  const [audioUrl, setAudioUrl] =
    useState<string | null>(null)

  useEffect(() => {
    const objectUrl = URL.createObjectURL(visit.audio)

    setAudioUrl(objectUrl)

    return () => {
      URL.revokeObjectURL(objectUrl)
    }
  }, [visit.audio])

  return (
    <article className="rounded-xl border p-5">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <strong className="text-lg">
          {visit.beneficiaryId}
        </strong>

        {visit.status === "uploaded" ? (
          <span className="rounded-full bg-green-100 px-3 py-1 text-sm font-medium text-green-800">
            Uploaded — Awaiting Processing
          </span>
        ) : (
          <span className="rounded-full bg-amber-100 px-3 py-1 text-sm font-medium text-amber-800">
            Pending Sync
          </span>
        )}
      </div>

      <p className="mb-2 text-sm text-gray-600">
        Duration:{" "}
        {formatDuration(visit.durationSeconds)}
      </p>

      {audioUrl && (
        <audio
          controls
          src={audioUrl}
          className="mb-3 w-full"
        />
      )}

      <p className="break-all text-xs text-gray-500">
        Local Record ID: {visit.clientRecordId}
      </p>

      {visit.serverSyncId !== undefined && (
        <p className="mt-1 text-xs text-gray-500">
          Server Sync ID: {visit.serverSyncId}
        </p>
      )}

      <p className="mt-1 text-xs text-gray-500">
        Recorded:{" "}
        {new Date(visit.recordedAt).toLocaleString()}
      </p>
    </article>
  )
}

