import type { AgentKey, AgentReport, FeedEvent } from './types'

export interface CrewMember {
  key: AgentKey
  station: string // pit-crew role
  agent: string // business role
  blurb: string
}

export const CREW: Record<AgentKey, CrewMember> = {
  boss: { key: 'boss', station: 'Crew Chief', agent: 'Boss', blurb: 'Reads the ticket and directs the crew' },
  inventory: { key: 'inventory', station: 'Tires', agent: 'Inventory', blurb: 'Stock, sizes, restock vendors' },
  accounting: { key: 'accounting', station: 'Fuel', agent: 'Accounting', blurb: 'Cash, invoices, margins' },
  facilities: { key: 'facilities', station: 'Chassis', agent: 'Facilities', blurb: 'Lease, rent, the shop' },
  customer_service: { key: 'customer_service', station: 'Comms', agent: 'Customer Service', blurb: 'Drafts every outbound message' },
}

export const CREW_ORDER: AgentKey[] = ['boss', 'inventory', 'accounting', 'facilities', 'customer_service']

export const PIT_STATIONS: AgentKey[] = ['inventory', 'accounting', 'facilities', 'customer_service']

const TOOL_LABELS: Record<string, string> = {
  get_ticket: 'read ticket',
  list_open_tickets: 'scan board',
  list_tickets: 'scan board',
  check_stock_and_pricing: 'stock & price check',
  list_vendors_with_status: 'vendor status',
  get_invoice_vendor_status: 'invoice check',
  get_rent_due_and_cash: 'rent vs cash',
  get_cash_position: 'cash position',
  list_pending_approvals: 'approval queue',
  draft_purchase_order: 'draft PO',
  request_payment: 'request payment',
  propose_bulk_quote: 'propose quote',
  draft_customer_message: 'draft message',
  update_ticket: 'update ticket',
  delegate_to_agent: 'hand off',
  final_result: 'file report',
}

export const toolLabel = (t: string) => TOOL_LABELS[t] ?? t.replaceAll('_', ' ')

export interface StationState {
  status: 'idle' | 'working' | 'done' | 'error'
  turns: number
  tools: string[]
  lastLine: string | null
  report: AgentReport | null
  tokens: number
  lastIndex: number
}

const blank = (): StationState => ({
  status: 'idle', turns: 0, tools: [], lastLine: null, report: null, tokens: 0, lastIndex: -1,
})

/** Fold one run's events into a state per station. */
export function stationStates(events: FeedEvent[]): Record<AgentKey, StationState> {
  const out = Object.fromEntries(
    (Object.keys(CREW) as AgentKey[]).map((k) => [k, blank()]),
  ) as Record<AgentKey, StationState>
  const open: Record<string, number> = {}
  for (const e of events) {
    if (!(e.agent in out)) continue
    const s = out[e.agent as AgentKey]
    s.lastIndex = e.index
    if (e.event === 'run_start') {
      s.turns += 1
      open[e.agent] = (open[e.agent] ?? 0) + 1
    } else if (e.event === 'run_end' || e.event === 'error') {
      open[e.agent] = Math.max((open[e.agent] ?? 1) - 1, 0)
      if (e.detail?.report) s.report = e.detail.report
      if (e.event === 'error') s.status = 'error'
      if (e.usage?.total_tokens) s.tokens += e.usage.total_tokens
    }
    for (const t of e.tools_used) if (t !== 'final_result' && !s.tools.includes(t)) s.tools.push(t)
    const line = describe(e)
    if (line) s.lastLine = line
  }
  for (const k of Object.keys(out) as AgentKey[]) {
    const s = out[k]
    if (s.turns === 0) continue
    if ((open[k] ?? 0) > 0) s.status = 'working'
    else if (s.status !== 'error') s.status = 'done'
  }
  return out
}

const who = (a: string) => (a in CREW ? CREW[a as AgentKey].station : a)

/** One human-readable radio line per event (null = not worth showing). */
export function describe(e: FeedEvent): string | null {
  const d = e.detail ?? {}
  switch (e.event) {
    case 'run_start':
      return e.depth === 0 ? 'Takes the ticket.' : `Picks up: ${e.said ?? ''}`
    case 'delegation':
      return `Calls ${who(d.to ?? '')}: ${d.reason ?? ''}`
    case 'delegation_refused':
      return `Handoff to ${who(d.to ?? '')} blocked: ${d.refusal ?? ''}`
    case 'model_response': {
      const tools = e.tools_used.filter((t) => t !== 'final_result' && t !== 'delegate_to_agent')
      if (e.tools_used.includes('final_result')) return 'Filing report'
      if (tools.length) return tools.map(toolLabel).join(' · ')
      return e.said ? `“${e.said}”` : null
    }
    case 'run_end':
      return d.report?.summary ?? 'Done.'
    case 'error':
      return `Stopped: ${e.said ?? 'error'}`
    default:
      return null
  }
}

export const money = (n: number) =>
  n.toLocaleString('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2 })

export const TICKET_TYPE: Record<string, { label: string; code: string }> = {
  customer_order: { label: 'Customer order', code: 'ORD' },
  rent_notice: { label: 'Rent notice', code: 'RNT' },
  price_override: { label: 'Discount request', code: 'DSC' },
}

export const ticketType = (t: string) =>
  TICKET_TYPE[t] ?? { label: t.replaceAll('_', ' '), code: t.slice(0, 3).toUpperCase() }

export function fmtElapsed(ms: number) {
  const t = Math.max(ms, 0)
  const m = Math.floor(t / 60000)
  const s = Math.floor((t % 60000) / 1000)
  const d = Math.floor((t % 1000) / 100)
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}.${d}`
}
