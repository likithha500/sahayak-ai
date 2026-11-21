export type Beneficiary = {
  beneficiary_id: string
  name: string
  category: string
  village: string
  last_visit: string | null
  next_visit: string | null
}

export type Visit = {
  id: number
  beneficiary_id: string
  beneficiary_name: string
  beneficiary_category: string
  beneficiary_village: string
  visit_type: string | null
  weight_kg: number | null
  vaccinations_due: string[] | null
  next_visit_date: string | null
  created_at: string | null
  follow_up_id: number | null
  follow_up_date: string | null
  follow_up_status: string | null
  alerts: Alert[]
}

export type FollowUp = {
  id: number
  beneficiary_id: string
  beneficiary_name: string
  beneficiary_category: string
  visit_id: number
  scheduled_date: string
  reason: string
  status: "pending" | "overdue" | "completed"
  visit_type: string | null
}

export type Alert = {
  id: number
  beneficiary_id: string | null
  visit_id: number | null
  danger_type: string
  transcript: string
  severity: string
  matched_sign: string | null
  guideline_document: string | null
  guideline_page: number | null
  recommended_action: string | null
  acknowledged: number
  referral_status: string
  created_at: string
}

export type Dashboard = {
  stats: {
    beneficiaries: number
    visits_today: number
    scheduled_today: number
    upcoming_follow_ups: number
    overdue_follow_ups: number
    urgent_referrals: number
  }
  today_visits: Visit[]
  recent_visits: Visit[]
  upcoming_follow_ups: FollowUp[]
  urgent_alerts: Alert[]
}

export const DATA_UPDATED_EVENT = "sahayak:data-updated"

export function notifyDataUpdated() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(DATA_UPDATED_EVENT))
  }
}

export function subscribeToDataUpdates(callback: () => void) {
  if (typeof window === "undefined") {
    return () => undefined
  }
  window.addEventListener(DATA_UPDATED_EVENT, callback)
  return () => window.removeEventListener(DATA_UPDATED_EVENT, callback)
}

async function request<T>(
  path: string,
  init?: RequestInit
): Promise<T> {
  const response = await fetch(`/api/backend/${path}`, {
    ...init,
    cache: "no-store",
    headers: {
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  })

  if (!response.ok) {
    let detail = `Request failed (${response.status})`
    try {
      const body = await response.json() as { detail?: string }
      if (body.detail) detail = body.detail
    } catch {
      // Keep the HTTP status as the actionable error when there is no JSON body.
    }
    throw new Error(detail)
  }

  return response.json() as Promise<T>
}

export const apiService = {
  getDashboard: () => request<Dashboard>("api/dashboard"),
  getBeneficiaries: () =>
    request<Beneficiary[]>("api/beneficiaries"),
  getBeneficiary: (id: string) =>
    request<Beneficiary>(`api/beneficiaries/${encodeURIComponent(id)}`),
  getBeneficiaryVisits: (id: string) =>
    request<Visit[]>(
      `api/beneficiaries/${encodeURIComponent(id)}/visits`
    ),
  getVisits: () => request<Visit[]>("api/visits"),
  getVisit: (id: number) => request<Visit>(`api/visits/${id}`),
  getFollowUps: () => request<FollowUp[]>("api/follow-ups"),
  updateFollowUp: (
    id: number,
    update: { scheduled_date?: string; status?: "pending" | "completed" }
  ) =>
    request<FollowUp>(`api/follow-ups/${id}`, {
      method: "PATCH",
      body: JSON.stringify(update),
    }),
  getAlerts: () => request<Alert[]>("api/alerts"),
  acknowledgeAlert: (id: number) =>
    request<Alert>(`api/alerts/${id}/acknowledge`, { method: "POST" }),
  updateReferralStatus: (
    id: number,
    status: "not_started" | "referred" | "follow_up_pending" | "completed"
  ) =>
    request<Alert>(`api/alerts/${id}/referral-status`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }),
}
