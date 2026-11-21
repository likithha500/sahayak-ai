
export type OfflineAudioVisit = {
  clientRecordId: string
  beneficiaryId: string
  recordedAt: string
  audio: Blob
  mimeType: string
  durationSeconds: number
  status: "pending" | "uploaded"
  serverSyncId?: number
}

const DB_NAME = "sahayak-offline"
const STORE_NAME = "audio-visits"
const DB_VERSION = 2

function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION)

    request.onupgradeneeded = () => {
      const db = request.result

      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, {
          keyPath: "clientRecordId",
        })
      }
    }

    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
    request.onblocked = () =>
      reject(new Error("Close other tabs using the offline database"))
  })
}

export async function saveAudioVisit(
  visit: OfflineAudioVisit
): Promise<void> {
  const db = await openDatabase()

  try {
    await new Promise<void>((resolve, reject) => {
      const transaction = db.transaction(STORE_NAME, "readwrite")
      transaction.objectStore(STORE_NAME).put(visit)

      transaction.oncomplete = () => resolve()
      transaction.onerror = () => reject(transaction.error)
      transaction.onabort = () => reject(transaction.error)
    })
  } finally {
    db.close()
  }
}

export async function getAudioVisits(): Promise<OfflineAudioVisit[]> {
  const db = await openDatabase()

  try {
    return await new Promise((resolve, reject) => {
      const transaction = db.transaction(STORE_NAME, "readonly")
      const request = transaction.objectStore(STORE_NAME).getAll()

      request.onsuccess = () =>
        resolve(request.result as OfflineAudioVisit[])
      request.onerror = () => reject(request.error)
    })
  } finally {
    db.close()
  }
}

export async function uploadPendingAudio(): Promise<{
  uploaded: number
  failed: number
}> {
  const visits = await getAudioVisits()

  let uploaded = 0
  let failed = 0

  for (const visit of visits) {
    if (visit.status !== "pending") continue

    const form = new FormData()

    form.append("client_record_id", visit.clientRecordId)
    form.append("beneficiary_id", visit.beneficiaryId)
    form.append("recorded_at", visit.recordedAt)

    const extension = visit.mimeType.includes("mp4")
      ? "m4a"
      : visit.mimeType.includes("ogg")
        ? "ogg"
        : "webm"

    form.append(
      "audio",
      visit.audio,
      `recording.${extension}`
    )

    try {
      const response = await fetch(
        "/api/offline-sync/audio",
        {
          method: "POST",
          body: form,
        }
      )

      if (!response.ok) {
        failed++
        continue
      }

      const result = await response.json()

      if (
        result.client_record_id !== visit.clientRecordId ||
        typeof result.server_sync_id !== "number"
      ) {
        failed++
        continue
      }

      await saveAudioVisit({
        ...visit,
        status: "uploaded",
        serverSyncId: result.server_sync_id,
      })

      uploaded++
    } catch {
      failed++
    }
  }

  return { uploaded, failed }
}
