import { CREW, CREW_ORDER, money, stationStates, ticketType } from '../crew'
import type { AgentKey, FeedEvent, PaymentRequest, Run, Ticket } from '../types'
import { LapRing } from './LapRing'
import { Station } from './Station'
import { Timeline } from './Timeline'

interface Props {
  ticket: Ticket | null
  run: Run | null
  events: FeedEvent[]
  calls: PaymentRequest[]
  starting: boolean
  startError: string | null
  onStart: (id: number) => void
}

const isAgent = (e: FeedEvent) => e.agent in CREW

export function PitBox({ ticket, run, events, calls, starting, startError, onStart }: Props) {
  if (!ticket) {
    return (
      <section className="panel pitbox is-empty" aria-label="Pit box">
        <div className="pitbox-empty">
          <span className="pitbox-empty-mark" aria-hidden="true" />
          <p className="pitbox-empty-title">Select a ticket</p>
          <p className="muted">Choose an entry from the pit lane to bring it in and brief the crew.</p>
        </div>
      </section>
    )
  }

  // Show the backend's latest run for this ticket, else the latest one recorded in the audit trail.
  const agentEvents = events.filter(isAgent)
  const runId = run?.run_id ?? agentEvents.at(-1)?.run_id ?? null
  const runEvents = runId ? agentEvents.filter((e) => e.run_id === runId) : []
  const states = stationStates(runEvents)
  const running = run?.status === 'running' || ticket.agents_running
  const liveAgent = running ? (runEvents.at(-1)?.agent as AgentKey | undefined) : undefined
  const start = run?.started_at ?? runEvents[0]?.ts ?? null
  const end = run?.finished_at ?? (running ? null : runEvents.at(-1)?.ts ?? null)
  const bossReport = run?.result?.report ?? states.boss.report
  const tt = ticketType(ticket.type)
  const hasRun = runEvents.length > 0 || !!run
  const reported = CREW_ORDER.filter((k) => states[k].report)

  return (
    <section className={`panel pitbox ${running ? 'is-running' : ''}`} aria-labelledby="box-h">
      <header className="pitbox-h">
        <div className="pitbox-id">
          <span className="pitbox-no">{ticket.id}</span>
          <div className="pitbox-title">
            <span className="label">{tt.label} · {ticket.requester}</span>
            <h2 id="box-h">{ticket.subject}</h2>
            {ticket.notes && <p className="muted">{ticket.notes}</p>}
          </div>
        </div>
        <div className="pitbox-controls">
          <LapRing start={start} end={end} running={running} />
          {ticket.state === 'open' && !running && (
            <button type="button" className="btn primary" disabled={starting} onClick={() => onStart(ticket.id)}>
              {starting ? 'Starting…' : 'Start pit stop'}
              <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M5 3l5 5-5 5" /></svg>
            </button>
          )}
          {ticket.state === 'resolved' && !running && <span className="chip st st-done"><i />Finished</span>}
        </div>
      </header>

      <ol className="sectors" aria-label="Crew progress">
        {CREW_ORDER.map((k) => (
          <li key={k} className={`sector st-${states[k].status} ${liveAgent === k ? 'is-live' : ''}`}>
            <span className="sector-bar" />
            <span className="sector-name">{CREW[k].station}</span>
          </li>
        ))}
      </ol>

      {startError && <p className="call-error" role="alert">{startError}</p>}

      {calls.length > 0 && (
        <div className="notice" role="status">
          <span className="pulse" aria-hidden="true" />
          <span>
            <b>Crew chief requesting a GO</b>: {calls.length} payment{calls.length > 1 ? 's' : ''} for this ticket
            ({money(calls.reduce((s, c) => s + c.amount, 0))}) waiting in Authorizations.
          </span>
        </div>
      )}

      <div className="tele-grid">
        {CREW_ORDER.map((k, i) => (
          <Station key={k} agent={k} index={i + 1} state={states[k]} live={liveAgent === k} wide={k === 'boss'} />
        ))}
      </div>

      {hasRun ? (
        <div className="pitbox-bottom">
          <Timeline events={runEvents} />
          <div className="debrief">
            <h3 className="label">Debrief</h3>
            {reported.length === 0 ? (
              <p className="empty">{running ? 'Reports arrive as each agent finishes.' : 'No reports for this run.'}</p>
            ) : (
              <ul className="debrief-list">
                {reported.map((k) => (
                  <li key={k}><b>{CREW[k].agent}</b><span>{states[k].report!.summary}</span></li>
                ))}
              </ul>
            )}
            {bossReport && !running && (
              <div className="chief">
                {([['Waiting on you', bossReport.awaiting_human_approval], ['Blockers', bossReport.blockers],
                  ['Next steps', bossReport.next_steps]] as const).map(([title, items]) => items.length > 0 && (
                  <div key={title}>
                    <h4 className="label">{title}</h4>
                    <ul>{items.map((x, i) => <li key={i}>{x}</li>)}</ul>
                  </div>
                ))}
              </div>
            )}
            {run?.result && (
              <p className="run-stats mono">
                {run.result.delegations} handoffs · {(run.result.total_tokens / 1000).toFixed(1)}k tokens · {run.run_id}
              </p>
            )}
            {run?.status === 'error' && <p className="call-error">Run failed: {run.error}</p>}
          </div>
        </div>
      ) : (
        <p className="empty pitbox-hint">
          The crew hasn’t worked this ticket yet. Start the pit stop and the crew chief takes it from there. Each agent’s panel goes live as it works.
        </p>
      )}
    </section>
  )
}
