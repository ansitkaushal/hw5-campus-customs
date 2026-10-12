import { API_BASE } from './config'
import type { Approvals, Cash, EventsResponse, Run, TicketsResponse } from './types'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(API_BASE + path, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  })
  const body: unknown = await res.json().catch(() => ({}))
  if (!res.ok) {
    const detail = (body as { detail?: unknown }).detail
    const msg = typeof detail === 'string' ? detail : Array.isArray(detail) ? 'Invalid request' : res.statusText
    throw new ApiError(res.status, msg)
  }
  return body as T
}

export const api = {
  tickets: () => req<TicketsResponse>('/api/tickets'),
  cash: () => req<Cash>('/api/cash'),
  approvals: () => req<Approvals>('/api/approvals'),
  runs: () => req<{ runs: Run[] }>('/api/runs'),
  events: (q: { since?: number; ticket_id?: number; limit?: number }) => {
    const p = new URLSearchParams()
    Object.entries(q).forEach(([k, v]) => v !== undefined && p.set(k, String(v)))
    return req<EventsResponse>(`/api/events?${p}`)
  },
  startRun: (ticketId: number) => req<Run>(`/api/tickets/${ticketId}/run`, { method: 'POST' }),
  approve: (requestId: number, approvedBy: string) =>
    req<Record<string, unknown>>(`/api/approvals/${requestId}/approve`, {
      method: 'POST',
      body: JSON.stringify({ approved_by: approvedBy }),
    }),
  reject: (requestId: number, approvedBy: string, note: string) =>
    req<Record<string, unknown>>(`/api/approvals/${requestId}/reject`, {
      method: 'POST',
      body: JSON.stringify({ approved_by: approvedBy, note }),
    }),
  reset: () => req<{ reset: boolean }>('/api/reset', { method: 'POST' }),
}
