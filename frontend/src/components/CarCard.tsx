import { ticketType } from '../crew'
import type { Ticket } from '../types'

interface Props {
  ticket: Ticket
  selected: boolean
  onSelect: (id: number) => void
  compact?: boolean
  meta?: React.ReactNode
}

/** A ticket as a race entry: car number, class code, subject, driver (requester), specs. */
export function CarCard({ ticket, selected, onSelect, compact, meta }: Props) {
  const tt = ticketType(ticket.type)
  const specs = [
    ticket.sku,
    ticket.size && `Size ${ticket.size}`,
    ticket.qty != null && `Qty ${ticket.qty}`,
    ticket.lease_id != null && `Lease ${ticket.lease_id}`,
    ticket.invoice_id != null && `Inv ${ticket.invoice_id}`,
  ].filter(Boolean) as string[]
  return (
    <button
      type="button"
      className={`entry ${selected ? 'is-selected' : ''} ${ticket.agents_running ? 'is-running' : ''} ${compact ? 'is-compact' : ''} ${ticket.state === 'resolved' ? 'is-done' : ''}`}
      onClick={() => onSelect(ticket.id)}
      aria-pressed={selected}
    >
      <span className="entry-no">{ticket.id}</span>
      <span className="entry-main">
        <span className="entry-top">
          <span className="entry-code">{tt.code}</span>
          <span className="entry-class">{tt.label}</span>
          {ticket.agents_running && <span className="chip live"><i />Live</span>}
        </span>
        <span className="entry-title">{ticket.subject}</span>
        <span className="entry-sub">{ticket.requester}</span>
        {!compact && specs.length > 0 && <span className="entry-specs">{specs.join('  ·  ')}</span>}
        {meta}
      </span>
      {ticket.agents_running && <span className="entry-progress" aria-hidden="true" />}
    </button>
  )
}
