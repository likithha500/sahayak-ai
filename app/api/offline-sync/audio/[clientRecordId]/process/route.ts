
import { NextRequest, NextResponse } from "next/server"

export const runtime = "nodejs"

type RouteContext = {
  params: Promise<{
    clientRecordId: string
  }>
}

export async function POST(
  _request: NextRequest,
  context: RouteContext
) {
  const backendUrl = process.env.SAHAYAK_BACKEND_URL
  const syncKey = process.env.SAHAYAK_SYNC_API_KEY

  if (!backendUrl || !syncKey) {
    return NextResponse.json(
      { error: "Server synchronization is not configured" },
      { status: 503 }
    )
  }

  const { clientRecordId } = await context.params

  const uuidPattern =
    /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

  if (!uuidPattern.test(clientRecordId)) {
    return NextResponse.json(
      { error: "Invalid audio record ID" },
      { status: 422 }
    )
  }

  try {
    const response = await fetch(
      `${backendUrl.replace(/\/$/, "")}/api/offline-sync/audio/${clientRecordId}/process`,
      {
        method: "POST",
        headers: {
          "X-Sync-API-Key": syncKey,
        },
        cache: "no-store",
        signal: AbortSignal.timeout(60000),
      }
    )

    const result = await response.json()

    return NextResponse.json(result, {
      status: response.status,
    })
  } catch {
    return NextResponse.json(
      { error: "Transcription backend unavailable" },
      { status: 503 }
    )
  }
}
