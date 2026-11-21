
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
import { notifyDataUpdated } from "@/src/services/api.service"

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

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const selectedId = params.get("beneficiaryId")

    if (selectedId) {
      setBeneficiaryId(selectedId)
    }
  }, [])
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


type TranscriptJob = {
  client_record_id: string
  beneficiary_id: string
  status: string
  transcript: string | null
  transcript_language: string | null
  stt_model: string | null
  reviewed_transcript: string | null
  reviewed_at: string | null
  confirmed_visit_id: number | null
  visit_saved: boolean
}

type OfflineVisitDraft = {
  beneficiary_id: string | null
  beneficiary_name: string | null
  visit_type: "pregnancy" | "newborn" | "child" | "postnatal" | "general" | null
  weight_kg: number | null
  vaccinations_due: string[] | null
  next_visit_date: string | null
}

function SavedAudioCard({
  visit,
}: {
  visit: OfflineAudioVisit
}) {
  const [audioUrl, setAudioUrl] = useState<string | null>(null)
  const [job, setJob] = useState<TranscriptJob | null>(null)
  const [reviewedText, setReviewedText] = useState("")
  const [visitDraft, setVisitDraft] = useState<OfflineVisitDraft | null>(null)
  const [explicitlyConfirmed, setExplicitlyConfirmed] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")

  const recordId = visit.clientRecordId
  const baseUrl = `/api/offline-sync/audio/${encodeURIComponent(recordId)}`

  useEffect(() => {
    const objectUrl = URL.createObjectURL(visit.audio)
    setAudioUrl(objectUrl)

    return () => {
      URL.revokeObjectURL(objectUrl)
    }
  }, [visit.audio])

  const loadStatus = useCallback(async () => {
    setBusy(true)
    setError("")

    try {
      const response = await fetch(`${baseUrl}/processing`, {
        cache: "no-store",
      })
      const result = await response.json()

      if (!response.ok) {
        throw new Error(
          result.detail || result.error || "Unable to load transcript"
        )
      }

      setJob(result)
      setReviewedText(
        result.reviewed_transcript ?? result.transcript ?? ""
      )
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Request failed"
      )
    } finally {
      setBusy(false)
    }
  }, [baseUrl])

  useEffect(() => {
    if (visit.status === "uploaded") {
      void loadStatus()
    }
  }, [loadStatus, visit.status])

  async function transcribe() {
    setBusy(true)
    setError("")

    try {
      const response = await fetch(`${baseUrl}/process`, {
        method: "POST",
      })
      const result = await response.json()

      if (!response.ok) {
        throw new Error(
          result.detail || result.error || "Transcription failed"
        )
      }

      setJob(result)
      setReviewedText(
        result.reviewed_transcript ?? result.transcript ?? ""
      )
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Request failed"
      )
    } finally {
      setBusy(false)
    }
  }

  async function confirm() {
    const text = reviewedText.trim()

    if (!text) {
      setError("Please review the transcript before confirming.")
      return
    }

    setBusy(true)
    setError("")

    try {
      const response = await fetch(`${baseUrl}/confirm`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          reviewed_transcript: text,
        }),
      })

      const result = await response.json()

      if (!response.ok) {
        throw new Error(
          result.detail || result.error || "Confirmation failed"
        )
      }

      setJob(result)
      setReviewedText(result.reviewed_transcript ?? text)
      setVisitDraft(null)
      setExplicitlyConfirmed(false)
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Request failed"
      )
    } finally {
      setBusy(false)
    }
  }

  async function extractVisitDraft() {
    setBusy(true)
    setError("")
    try {
      const response = await fetch(`${baseUrl}/extract`, {
        method: "POST",
      })
      const result = await response.json()
      if (!response.ok) {
        throw new Error(
          result.detail || result.error || "Visit extraction failed"
        )
      }
      setVisitDraft(result.visit as OfflineVisitDraft)
      setExplicitlyConfirmed(false)
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Visit extraction failed"
      )
    } finally {
      setBusy(false)
    }
  }

  async function saveConfirmedVisit() {
    if (!visitDraft || !explicitlyConfirmed || !visitDraft.visit_type) {
      setError("Select the visit type and explicitly confirm the reviewed draft.")
      return
    }
    setBusy(true)
    setError("")
    try {
      const response = await fetch(`${baseUrl}/confirm-visit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          confirmed: true,
          visit: visitDraft,
        }),
      })
      const result = await response.json()
      if (!response.ok) {
        throw new Error(
          result.detail || result.error || "Visit could not be saved"
        )
      }
      setJob(result)
      notifyDataUpdated()
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Visit was not saved; the reviewed draft is preserved."
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <article className="rounded-xl border p-5">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <strong className="text-lg">{visit.beneficiaryId}</strong>

        <span className="rounded-full bg-blue-100 px-3 py-1 text-sm text-blue-800">
          {job?.status ??
            (visit.status === "uploaded"
              ? "Uploaded"
              : "Pending Sync")}
        </span>
      </div>

      <p className="mb-2 text-sm text-gray-600">
        Duration: {formatDuration(visit.durationSeconds)}
      </p>

      {audioUrl && (
        <audio controls src={audioUrl} className="mb-3 w-full" />
      )}

      <p className="break-all text-xs text-gray-500">
        Local Record ID: {recordId}
      </p>

      {visit.serverSyncId !== undefined && (
        <p className="mt-1 text-xs text-gray-500">
          Server Sync ID: {visit.serverSyncId}
        </p>
      )}

      <p className="mt-1 text-xs text-gray-500">
        Recorded: {new Date(visit.recordedAt).toLocaleString()}
      </p>

      {visit.status === "uploaded" && (
        <div className="mt-5 space-y-4 border-t pt-4">
          <h3 className="font-semibold">Gnani Transcript Review</h3>

          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => void loadStatus()}
              disabled={busy}
              className="rounded-lg border px-4 py-2 disabled:opacity-50"
            >
              Refresh Status
            </button>

            {(!job ||
              job.status === "uploaded" ||
              job.status === "failed") && (
              <button
                type="button"
                onClick={() => void transcribe()}
                disabled={busy}
                className="rounded-lg bg-indigo-700 px-4 py-2 text-white disabled:opacity-50"
              >
                {busy ? "Working..." : "Transcribe with Gnani"}
              </button>
            )}
          </div>

          {job?.transcript && (
            <div>
              <p className="mb-2 text-sm font-medium">
                Original Gnani Transcript
              </p>
              <p className="whitespace-pre-wrap rounded-lg bg-gray-100 p-3 text-sm text-gray-900">
                {job.transcript}
              </p>
              <p className="mt-2 text-xs text-gray-500">
                Language: {job.transcript_language ?? "Unknown"}
                {" · "}
                Model: {job.stt_model ?? "Unknown"}
              </p>
            </div>
          )}

          {job?.status === "awaiting_review" && (
            <div className="space-y-3">
              <label
                htmlFor={`review-${recordId}`}
                className="block font-medium"
              >
                Review and Correct Transcript
              </label>

              <textarea
                id={`review-${recordId}`}
                value={reviewedText}
                onChange={(event) =>
                  setReviewedText(event.target.value)
                }
                rows={5}
                maxLength={10000}
                className="w-full rounded-lg border p-3"
              />

              <button
                type="button"
                onClick={() => void confirm()}
                disabled={busy || !reviewedText.trim()}
                className="rounded-lg bg-green-700 px-5 py-3 font-medium text-white disabled:opacity-50"
              >
                Confirm Reviewed Transcript
              </button>
            </div>
          )}

          {job?.status === "confirmed" && (
            <div className="space-y-4 rounded-lg border p-4">
              <p className="font-semibold text-green-700">
                Transcript reviewed. The visit has not been saved yet.
              </p>

              <p className="mt-2 whitespace-pre-wrap text-sm">
                {job.reviewed_transcript}
              </p>

              {job.reviewed_at && (
                <p className="mt-2 text-xs text-gray-500">
                  Reviewed: {job.reviewed_at} UTC
                </p>
              )}

              <button
                type="button"
                onClick={() => void extractVisitDraft()}
                disabled={busy}
                className="rounded-lg bg-indigo-700 px-4 py-2 text-white disabled:opacity-50"
              >
                {busy ? "Extracting..." : "Extract structured visit draft"}
              </button>

              {visitDraft && (
                <div className="space-y-4 rounded-lg border bg-gray-50 p-4">
                  <h4 className="font-semibold">Review structured visit</h4>
                  <p className="text-sm text-gray-700">
                    Registered beneficiary: {visitDraft.beneficiary_name || job.beneficiary_id}
                    {" · "}{job.beneficiary_id}
                  </p>

                  <label className="block text-sm font-medium">
                    Visit type
                    <select
                      value={visitDraft.visit_type || ""}
                      onChange={(event) =>
                        setVisitDraft((current) =>
                          current
                            ? {
                                ...current,
                                visit_type: event.target.value
                                  ? event.target.value as OfflineVisitDraft["visit_type"]
                                  : null,
                              }
                            : current
                        )
                      }
                      className="mt-1 block w-full rounded-lg border bg-white p-3"
                    >
                      <option value="">Select visit type</option>
                      <option value="pregnancy">Pregnancy</option>
                      <option value="newborn">Newborn</option>
                      <option value="child">Child</option>
                      <option value="postnatal">Postnatal</option>
                      <option value="general">General</option>
                    </select>
                  </label>

                  <label className="block text-sm font-medium">
                    Weight (kg)
                    <input
                      type="number"
                      min="0"
                      max="300"
                      step="0.1"
                      value={visitDraft.weight_kg ?? ""}
                      onChange={(event) =>
                        setVisitDraft((current) =>
                          current
                            ? {
                                ...current,
                                weight_kg: event.target.value
                                  ? Number(event.target.value)
                                  : null,
                              }
                            : current
                        )
                      }
                      className="mt-1 block w-full rounded-lg border bg-white p-3"
                    />
                  </label>

                  <label className="block text-sm font-medium">
                    Vaccinations due (optional; comma-separated)
                    <input
                      value={visitDraft.vaccinations_due?.join(", ") || ""}
                      onChange={(event) =>
                        setVisitDraft((current) =>
                          current
                            ? {
                                ...current,
                                vaccinations_due: event.target.value.trim()
                                  ? event.target.value
                                      .split(",")
                                      .map((item) => item.trim())
                                      .filter(Boolean)
                                  : null,
                              }
                            : current
                        )
                      }
                      className="mt-1 block w-full rounded-lg border bg-white p-3"
                    />
                  </label>

                  <label className="block text-sm font-medium">
                    Next visit date (optional)
                    <input
                      type="date"
                      value={visitDraft.next_visit_date || ""}
                      onChange={(event) =>
                        setVisitDraft((current) =>
                          current
                            ? {
                                ...current,
                                next_visit_date: event.target.value || null,
                              }
                            : current
                        )
                      }
                      className="mt-1 block w-full rounded-lg border bg-white p-3"
                    />
                  </label>

                  <label className="flex items-start gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={explicitlyConfirmed}
                      onChange={(event) =>
                        setExplicitlyConfirmed(event.target.checked)
                      }
                    />
                    <span>I reviewed and explicitly confirm this visit draft for saving.</span>
                  </label>
                  <button
                    type="button"
                    onClick={() => void saveConfirmedVisit()}
                    disabled={busy || !explicitlyConfirmed || !visitDraft.visit_type}
                    className="rounded-lg bg-green-700 px-5 py-3 font-medium text-white disabled:opacity-50"
                  >
                    {busy ? "Saving..." : "Confirm and save visit"}
                  </button>
                </div>
              )}
            </div>
          )}

          {job?.status === "visit_saved" && (
            <div className="rounded-lg border border-green-300 bg-green-50 p-4">
              <p className="font-semibold text-green-700">
                Visit saved successfully · Visit ID {job.confirmed_visit_id}
              </p>
            </div>
          )}

          {job?.status === "processing" && (
            <p className="text-sm">
              Transcription is processing. Refresh the status shortly.
            </p>
          )}

          {job?.status === "failed" && (
            <p className="text-sm text-red-700">
              Transcription failed. You can retry.
            </p>
          )}

          {error && (
            <p role="alert" className="text-sm text-red-700">
              {error}
            </p>
          )}
        </div>
      )}
    </article>
  )
}
