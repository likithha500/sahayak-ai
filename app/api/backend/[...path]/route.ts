import { NextRequest, NextResponse } from "next/server"

export const runtime = "nodejs"
export const dynamic = "force-dynamic"

const allowedRoots = new Set([
  "api/alerts",
  "api/beneficiaries",
  "api/dashboard",
  "api/follow-ups",
  "api/statistics",
  "api/visits",
  "health",
])

type RouteContext = {
  params: Promise<{ path: string[] }>
}

async function proxy(
  request: NextRequest,
  context: RouteContext,
  method: "GET" | "POST" | "PATCH"
) {
  const backendUrl = process.env.SAHAYAK_BACKEND_URL
  if (!backendUrl) {
    return NextResponse.json(
      { detail: "Backend URL is not configured" },
      { status: 503 }
    )
  }

  const { path } = await context.params
  const root = path.slice(0, 2).join("/")
  if (
    path.some((segment) => !segment || segment === "." || segment === "..") ||
    (!allowedRoots.has(root) && path[0] !== "health")
  ) {
    return NextResponse.json(
      { detail: "Backend route is not available through this proxy" },
      { status: 404 }
    )
  }

  const target = new URL(
    path.map((segment) => encodeURIComponent(segment)).join("/"),
    `${backendUrl.replace(/\/+$/, "")}/`
  )
  request.nextUrl.searchParams.forEach((value, key) => {
    target.searchParams.append(key, value)
  })

  try {
    const body =
      method === "GET" ? undefined : await request.text()
    const response = await fetch(target, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body,
      cache: "no-store",
      signal: AbortSignal.timeout(15000),
    })
    const contentType = response.headers.get("content-type")
    const responseBody = await response.text()
    return new NextResponse(responseBody, {
      status: response.status,
      headers: {
        "Cache-Control": "no-store",
        ...(contentType ? { "Content-Type": contentType } : {}),
      },
    })
  } catch {
    return NextResponse.json(
      { detail: "SAHAYAK backend is unavailable" },
      { status: 503 }
    )
  }
}

export function GET(request: NextRequest, context: RouteContext) {
  return proxy(request, context, "GET")
}

export function POST(request: NextRequest, context: RouteContext) {
  return proxy(request, context, "POST")
}

export function PATCH(request: NextRequest, context: RouteContext) {
  return proxy(request, context, "PATCH")
}
