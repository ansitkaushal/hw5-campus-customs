import { useEffect, useRef } from 'react'
import { CREW, describe } from '../crew'
import type { AgentKey, FeedEvent } from '../types'

/** Chronological feed of what each agent said and did in this run. */
export function Timeline({ events }: { events: FeedEvent[] }) {
  const lines = events
    .map((e) => ({ e, text: describe(e) }))
    .filter((l): l is { e: FeedEvent; text: string } => !!l.text)
  const box = useRef<HTMLOListElement>(null)
  useEffect(() => {
    const el = box.current
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
  }, [lines.length])

  return (
    <div className="timeline">
      <h3 className="label">Timeline</h3>
      <ol className="timeline-list" ref={box} aria-live="polite">
        {lines.length === 0 && <li className="empty">Waiting for the first transmission.</li>}
        {lines.map(({ e, text }) => (
          <li key={e.index} className={`tl ev-${e.event}`} style={{ ['--depth' as string]: e.depth }}>
            <time>{new Date(e.ts).toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })}</time>
            <b>{CREW[e.agent as AgentKey]?.agent ?? e.agent}</b>
            <span>{text}</span>
          </li>
        ))}
      </ol>
    </div>
  )
}
