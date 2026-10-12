import type { Ticket } from '../types'
import { CarCard } from './CarCard'

export function PitLane({ tickets, selectedId, onSelect }: {
  tickets: Ticket[]; selectedId: number | null; onSelect: (id: number) => void
}) {
  return (
    <section className="panel lane" aria-labelledby="lane-h">
      <header className="panel-h">
        <h2 id="lane-h">Pit lane</h2>
        <span className="label">{tickets.length} queued</span>
      </header>
      {tickets.length === 0 ? (
        <p className="empty">All clear. Every ticket has finished.</p>
      ) : (
        <div className="lane-list">
          {tickets.map((t) => <CarCard key={t.id} ticket={t} selected={t.id === selectedId} onSelect={onSelect} />)}
        </div>
      )}
    </section>
  )
}
