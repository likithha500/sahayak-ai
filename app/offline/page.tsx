
"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import {
  getAudioVisits,
  saveAudioVisit,
  type OfflineAudioVisit,
} from "@/src/services/offline-queue"

type RecordingPreview = {
  blob: Blob
  mimeType: string
  durationSeconds: number
}

function chooseMimeType(): string | undefined {
  const types = [
    "audio/webm;codecs=opus",
    "audio/mp4",
    "audio/webm",
  ]

  return types.find((type) => MediaRecorder.isTypeSupported(type))
}

export default function OfflineAudioPage() {
  const [beneficiaryId, setBeneficiaryId] = useState("")
  const [visits, setVisits] = useState<OfflineAudioVisit[]>([])
  const [recording, setRecording] = useState(false)
  const [preview, setPreview] = useState<RecordingPreview | null>(null)
  const [message, setMessage] = useState("")
  const [elapsed, setElapsed] = useState(0)

  const recorderRef = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const startedAtRef = useRef(0)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const previewUrlRef = useRef<string | null>(null)

  const [previewUrl, setPreviewUrl] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      const saved = await getAudioVisits()
      saved.sort((a, b) =>
        b.recordedAt.localeCompare(a.recordedAt)
      )
      setVisits(saved)
    } catch {
      setMessage("Could not read saved audio recordings.")
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  useEffect(() => {
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
      if (recorderRef.current?.state === "recording") {
        recorderRef.current.stop()
      }
      streamRef.current?.getTracks().forEach((track) => track.stop())
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

  async function startRecording() {
    if (!navigator.mediaDevices?.getUserMedia) {
      setMessage("Microphone recording is not supported in this browser.")
      return
    }

    try {
      setMessage("")
      setPreview(null)

      if (previewUrlRef.current) {
        URL.revokeObjectURL(previewUrlRef.current)
        previewUrlRef.current = null
        setPreviewUrl(null)
      }

      const stream = await navigator.mediaDevices.getUserMedia({
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
          Math.round((Date.now() - startedAtRef.current) / 1000)
        )

        stream.getTracks().forEach((track) => track.stop())
        streamRef.current = null

        if (blob.size === 0) {
          setMessage("Recording was empty. Please try again.")
          return
        }

        setPreview({
          blob,
          mimeType: actualType,
          durationSeconds,
        })

        updatePreviewUrl(blob)
        setMessage("Recording complete. Save it to the offline queue.")
      }

      recorder.onerror = () => {
        setMessage("Recording failed. Please try again.")
        stream.getTracks().forEach((track) => track.stop())
        setRecording(false)
        if (intervalRef.current) clearInterval(intervalRef.current)
      }

      startedAtRef.current = Date.now()
      setElapsed(0)

      recorder.start(1000)
      setRecording(true)

      intervalRef.current = setInterval(() => {
        setElapsed(
          Math.floor((Date.now() - startedAtRef.current) / 1000)
        )
      }, 500)
    } catch {
      setMessage(
        "Could not access the microphone. Check browser permissions."
      )
    }
  }

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

  async function saveRecording() {
    if (!preview) {
      setMessage("Record audio before saving.")
      return
    }

    if (!beneficiaryId.trim()) {
      setMessage("Enter a beneficiary ID.")
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
      setMessage(
        `Audio saved locally. Record ID: ${visit.clientRecordId}`
      )

      if (previewUrlRef.current) {
        URL.revokeObjectURL(previewUrlRef.current)
        previewUrlRef.current = null
        setPreviewUrl(null)
      }

      await refresh()
    } catch {
      setMessage(
        "Unable to save audio. Keep this page open and try again."
      )
    }
  }

  return (
    <main className="mx-auto max-w-2xl p-6">
      <h1 className="mb-2 text-3xl font-bold">
        SAHAYAK AI — Offline Audio Visits
      </h1>

      <p className="mb-6 text-sm text-gray-600">
        Record household visits and save audio locally without internet.
        Use synthetic test recordings only.
      </p>

      <section className="mb-8 space-y-4 rounded-xl border p-5">
        <label className="block font-medium" htmlFor="beneficiary">
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
          className="w-full rounded border p-3"
        />

        <div className="flex flex-wrap items-center gap-3">
          {!recording ? (
            <button
              type="button"
              onClick={startRecording}
              className="rounded-lg bg-blue-700 px-5 py-3 text-white"
            >
              Start Recording
            </button>
          ) : (
            <button
              type="button"
              onClick={stopRecording}
              className="rounded-lg bg-red-700 px-5 py-3 text-white"
            >
              Stop Recording
            </button>
          )}

          {recording && (
            <span role="status" className="font-medium text-red-700">
              Recording: {elapsed}s
            </span>
          )}
        </div>

        {preview && previewUrl && (
          <div className="space-y-3 rounded-lg border p-3">
            <p className="font-medium">
              Recorded audio ({preview.durationSeconds}s)
            </p>

            <audio controls src={previewUrl} className="w-full" />

            <button
              type="button"
              onClick={saveRecording}
              className="rounded-lg bg-green-700 px-5 py-3 text-white"
            >
              Save Audio Offline
            </button>
          </div>
        )}
      </section>

      {message && (
        <p role="status" className="mb-5 rounded border p-3">
          {message}
        </p>
      )}

      <h2 className="mb-4 text-xl font-semibold">
        Pending Audio Queue ({visits.length})
      </h2>

      {visits.length === 0 ? (
        <p>No audio recordings saved yet.</p>
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
    </main>
  )
}

function SavedAudioCard({
  visit,
}: {
  visit: OfflineAudioVisit
}) {
  const [url, setUrl] = useState<string | null>(null)

  useEffect(() => {
    const objectUrl = URL.createObjectURL(visit.audio)
    setUrl(objectUrl)

    return () => URL.revokeObjectURL(objectUrl)
  }, [visit.audio])

  return (
    <article className="rounded-xl border p-4">
      <div className="flex items-center justify-between gap-3">
        <strong>{visit.beneficiaryId}</strong>

        <span className="rounded bg-amber-100 px-2 py-1 text-sm text-amber-900">
          {visit.status === "pending"
            ? "Pending sync"
            : "Uploaded"}
        </span>
      </div>

      <p className="mt-2 text-sm">
        Duration: {visit.durationSeconds}s
      </p>

      {url && (
        <audio controls src={url} className="mt-3 w-full" />
      )}

      <p className="mt-3 break-all text-xs text-gray-500">
        Record ID: {visit.clientRecordId}
      </p>

      <p className="mt-1 text-xs text-gray-500">
        {new Date(visit.recordedAt).toLocaleString()}
      </p>
    </article>
  )
}
