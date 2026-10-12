import { fmtElapsed } from '../crew'
import type { Run, Ticket } from '../types'
import { CarCard } from './CarCard'

export function FinishedLane({ tickets, runs, selectedId, onSelect }: {
  tickets: Ticket[]; runs: Run[]; selectedId: number | null; onSelect: (id: number) => void
}) {
  return (
    <section className="panel finished" aria-labelledby="fin-h">
      <header className="panel-h">
        <h2 id="fin-h">Finished</h2>
        <span className="label">{tickets.length} resolved</span>
      </header>
      {tickets.length === 0 ? (
        <p className="empty">No finishers yet.</p>
      ) : (
        <div className="finished-list">
          {tickets.map((t) => {
            const run = runs.find((r) => r.ticket_id === t.id && r.status === 'done')
            const ms = run?.finished_at ? Date.parse(run.finished_at) - Date.parse(run.started_at) : null
            return (
              <CarCard key={t.id} ticket={t} compact selected={t.id === selectedId} onSelect={onSelect}
                meta={
                  <span className="entry-meta">
                    <span className="ok-dot" aria-hidden="true" />
                    {ms !== null ? fmtElapsed(ms) : 'Resolved'}
                    {run?.result && <span className="muted">· {run.result.delegations} handoffs</span>}
                  </span>
                } />
            )
          })}
        </div>
      )}
    </section>
  )
}
