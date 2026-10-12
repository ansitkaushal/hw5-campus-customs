import { useEffect, useState } from 'react'
import { fmtElapsed } from '../crew'

const R = 34
const C = 2 * Math.PI * R

/** Elapsed-time ring. While running, the arc sweeps once every 60 s (a "lap"); when finished it closes to a full green ring. */
export function LapRing({ start, end, running }: { start: string | null; end: string | null; running: boolean }) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (!running) return
    let raf = 0
    const tick = () => { setNow(Date.now()); raf = requestAnimationFrame(tick) }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [running])

  const t0 = start ? Date.parse(start) : null
  const t1 = running ? now : end ? Date.parse(end) : null
  const ms = t0 !== null && t1 !== null ? Math.max(t1 - t0, 0) : 0
  const finished = !running && t0 !== null && t1 !== null
  const frac = running ? (ms % 60000) / 60000 : finished ? 1 : 0
  const state = running ? 'is-running' : finished ? 'is-finished' : 'is-idle'

  return (
    <div className={`lapring ${state}`} role="timer" aria-label={`Elapsed ${fmtElapsed(ms)}`}>
      <svg viewBox="0 0 80 80" aria-hidden="true">
        <circle cx="40" cy="40" r={R} className="lapring-track" />
        <circle cx="40" cy="40" r={R} className="lapring-arc"
          style={{ strokeDasharray: `${frac * C} ${C}` }} transform="rotate(-90 40 40)" />
      </svg>
      <div className="lapring-read">
        <span className="lapring-time">{fmtElapsed(ms)}</span>
        <span className="lapring-label">{running ? 'Elapsed' : finished ? 'Final' : 'Ready'}</span>
      </div>
    </div>
  )
}
