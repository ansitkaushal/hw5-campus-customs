import { fmtElapsed } from '../crew'

/** Quiet completion moment: a check that draws itself and the final time. */
export function FinishToast({ ticketId, ms }: { ticketId: number; ms: number | null }) {
  return (
    <div className="finish" role="status" aria-live="assertive">
      <svg viewBox="0 0 24 24" className="finish-check" aria-hidden="true">
        <circle cx="12" cy="12" r="10.5" />
        <path d="M7 12.5l3.2 3.2L17 9" />
      </svg>
      <div>
        <p className="finish-title">Ticket {ticketId} complete</p>
        <p className="finish-sub">{ms !== null ? `Final ${fmtElapsed(ms)} · moved to Finished` : 'Moved to Finished'}</p>
      </div>
    </div>
  )
}
