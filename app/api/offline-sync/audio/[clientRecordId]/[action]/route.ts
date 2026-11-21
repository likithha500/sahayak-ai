import { NextRequest, NextResponse } from "next/server"

export const runtime = "nodejs"

type RouteContext = {
  params: Promise<{ clientRecordId: string; action: string }>
}

const allowedActions = new Set([
  "confirm",
  "confirm-visit",
  "extract",
])

export async function POST(request: NextRequest, context: RouteContext) {
  const { clientRecordId, action } = await context.params
  if (!allowedActions.has(action)) {
    return NextResponse.json(
      { error: "Audio action is not available" },
      { status: 404 }
    )
  }

  const backendUrl = process.env.SAHAYAK_BACKEND_URL
  const syncKey = process.env.SAHAYAK_SYNC_API_KEY
  if (!backendUrl || !syncKey) {
    return NextResponse.json(
      { error: "Server synchronization is not configured" },
      { status: 503 }
    )
  }

  try {
    const body = await request.text()
    const response = await fetch(
      `${backendUrl.replace(/\/+$/, "")}/api/offline-sync/audio/${encodeURIComponent(clientRecordId)}/${action}`,
      {
        method: "POST",
        headers: {
          "X-Sync-API-Key": syncKey,
          ...(body ? { "Content-Type": "application/json" } : {}),
        },
        body: body || undefined,
        cache: "no-store",
        signal: AbortSignal.timeout(30000),
      }
    )
    return NextResponse.json(await response.json(), {
      status: response.status,
    })
  } catch {
    return NextResponse.json(
      { error: "Backend unavailable; the reviewed draft is preserved." },
      { status: 503 }
    )
  }
}
