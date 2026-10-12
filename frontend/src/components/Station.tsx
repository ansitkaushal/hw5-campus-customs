import { CREW, toolLabel, type StationState } from '../crew'
import type { AgentKey } from '../types'

const STATUS = { idle: 'Standby', working: 'Active', done: 'Complete', error: 'Stopped' }

/** Live telemetry readout for one agent. */
export function Station({ agent, index, state, live, wide }: {
  agent: AgentKey; index: number; state: StationState; live: boolean; wide?: boolean
}) {
  const c = CREW[agent]
  const line = state.status === 'done' && state.report ? state.report.summary : state.lastLine
  return (
    <article className={`tele st-${state.status} ${live ? 'is-live' : ''} ${wide ? 'is-wide' : ''}`}
      aria-label={`${c.agent}: ${STATUS[state.status]}`}>
      <span className="tele-bar" aria-hidden="true" />
      <header className="tele-h">
        <span className="tele-idx">{String(index).padStart(2, '0')}</span>
        <span className="tele-names">
          <span className="tele-agent">{c.agent}</span>
          <span className="tele-role">{c.station}</span>
        </span>
        {live && <span className="chip live"><i />On air</span>}
        <span className={`chip st st-${state.status}`}><i />{STATUS[state.status]}</span>
      </header>
      <p className={`tele-line ${line ? '' : 'is-placeholder'}`}>{line ?? c.blurb}</p>
      <footer className="tele-f">
        <span><b>{state.turns}</b> {state.turns === 1 ? 'turn' : 'turns'}</span>
        <span><b>{state.tools.length}</b> tools</span>
        <span><b>{state.tokens ? (state.tokens / 1000).toFixed(1) + 'k' : '0'}</b> tokens</span>
      </footer>
      {state.tools.length > 0 && (
        <ul className="tele-tools" aria-label="Tools used">
          {state.tools.map((t) => <li key={t} title={t}>{toolLabel(t)}</li>)}
        </ul>
      )}
    </article>
  )
}
