
import { NextRequest, NextResponse } from "next/server"

export const runtime = "nodejs"

const MAX_AUDIO_BYTES = 10 * 1024 * 1024

export async function POST(request: NextRequest) {
  const backendUrl = process.env.SAHAYAK_BACKEND_URL
  const syncKey = process.env.SAHAYAK_SYNC_API_KEY

  if (!backendUrl || !syncKey) {
    return NextResponse.json(
      { error: "Server synchronization is not configured" },
      { status: 503 }
    )
  }

  const contentLength = Number(
    request.headers.get("content-length") || 0
  )

  if (contentLength > MAX_AUDIO_BYTES + 10000) {
    return NextResponse.json(
      { error: "Upload too large" },
      { status: 413 }
    )
  }

  try {
    const form = await request.formData()
    const audio = form.get("audio")

    if (!(audio instanceof File)) {
      return NextResponse.json(
        { error: "Audio file is required" },
        { status: 422 }
      )
    }

    if (audio.size > MAX_AUDIO_BYTES || audio.size === 0) {
      return NextResponse.json(
        { error: "Audio must be between 1 byte and 10 MB" },
        { status: 413 }
      )
    }

    const response = await fetch(
      `${backendUrl}/api/offline-sync/audio`,
      {
        method: "POST",
        headers: {
          "X-Sync-API-Key": syncKey,
        },
        body: form,
        cache: "no-store",
        signal: AbortSignal.timeout(30000),
      }
    )

    const result = await response.json()

    return NextResponse.json(result, {
      status: response.status,
    })
  } catch {
    return NextResponse.json(
      { error: "Backend unavailable. Audio remains pending." },
      { status: 503 }
    )
  }
}
