export type AgentKey = 'boss' | 'inventory' | 'accounting' | 'facilities' | 'customer_service'

export interface Ticket {
  id: number
  type: string
  requester: string
  subject: string
  sku: string | null
  size: string | null
  qty: number | null
  lease_id: number | null
  invoice_id: number | null
  status: string
  notes: string | null
  created_at: string
  state: 'open' | 'resolved'
  agents_running: boolean
}

export interface TicketsResponse {
  today: string
  tickets: Ticket[]
}

export interface AgentReport {
  agent: AgentKey
  summary: string
  findings: string[]
  actions_taken: string[]
  awaiting_human_approval: string[]
  blockers: string[]
  next_steps: string[]
}

export interface Run {
  run_id: string
  ticket_id: number
  status: 'running' | 'done' | 'error'
  started_at: string
  finished_at: string | null
  result: { report: AgentReport | null; delegations: number; total_tokens: number } | null
  error: string | null
  boss_status?: string
}

export interface EventDetail {
  to?: AgentKey
  task?: string
  reason?: string
  refusal?: string
  report?: AgentReport
  kind?: string
}

export interface FeedEvent {
  index: number
  ts: string
  run_id: string
  ticket_id: number | null
  agent: AgentKey | 'human' | 'system'
  depth: number
  event: string
  said: string | null
  tools_used: string[]
  tool_calls: { tool: string; args: Record<string, unknown> }[]
  detail: EventDetail | null
  usage: Record<string, number> | null
}

export interface EventsResponse {
  events: FeedEvent[]
  next_since: number
  total: number
}

export interface PurchaseOrder {
  id: number
  vendor_id: number
  sku: string
  size: string
  qty: number
  unit_cost: number
  total: number
  expected_arrival: string
}

export interface PaymentRequest {
  id: number
  kind: 'invoice' | 'rent' | 'purchase_order'
  ref_id: number
  amount: number
  account: string
  ticket_id: number | null
  requested_by: string
  reason: string | null
  status: string
  created_at: string
  purchase_order?: PurchaseOrder | null
}

export interface Quote {
  id: number
  ticket_id: number | null
  sku: string
  size: string
  qty: number
  list_price: number
  discount_pct: number
  unit_price: number
  total: number
  unit_margin: number
  proposed_by: string
  rationale: string | null
}

export interface Approvals {
  payment_requests: PaymentRequest[]
  quotes: Quote[]
}

export interface Cash {
  today: string
  account: string
  opening_balance: number
  balance: number
  as_of: string
  pending_requests_total: number
  balance_after_pending: number
}
