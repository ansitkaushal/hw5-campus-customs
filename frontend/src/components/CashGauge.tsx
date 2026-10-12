import { useEffect, useRef, useState } from 'react'
import { money } from '../crew'
import type { Cash } from '../types'

const R = 26
const C = 2 * Math.PI * R
const SWEEP = 0.75 // 270° gauge

/** Checking balance as a 270° radial gauge: full = opening balance. A ghost arc shows the balance after pending approvals. */
export function CashGauge({ cash }: { cash: Cash | null }) {
  const [delta, setDelta] = useState<number | null>(null)
  const prev = useRef<number | null>(null)
  useEffect(() => {
    if (!cash) return
    const before = prev.current
    prev.current = cash.balance
    if (before !== null && cash.balance < before) {
      setDelta(before - cash.balance)
      const id = setTimeout(() => setDelta(null), 4000)
      return () => clearTimeout(id)
    }
  }, [cash])

  const full = cash?.opening_balance || 1
  const clamp = (n: number) => Math.min(Math.max(n, 0), 1)
  const frac = cash ? clamp(cash.balance / full) : 0
  const after = cash ? clamp(cash.balance_after_pending / full) : 0
  const pending = (cash?.pending_requests_total ?? 0) > 0
  const low = frac < 0.25

  return (
    <div className={`cash ${low ? 'is-low' : ''}`}>
      <svg viewBox="0 0 64 64" className="cash-ring" aria-hidden="true">
        <g transform="rotate(135 32 32)">
          <circle cx="32" cy="32" r={R} className="cash-track" style={{ strokeDasharray: `${SWEEP * C} ${C}` }} />
          {pending && (
            <circle cx="32" cy="32" r={R} className="cash-pending" style={{ strokeDasharray: `${SWEEP * frac * C} ${C}` }} />
          )}
          <circle cx="32" cy="32" r={R} className="cash-arc"
            style={{ strokeDasharray: `${SWEEP * (pending ? after : frac) * C} ${C}` }} />
        </g>
        <text x="32" y="36" className="cash-pct">{Math.round(frac * 100)}%</text>
      </svg>
      <div className="cash-read">
        <span className="label">Checking</span>
        <span className="cash-amount">{cash ? money(cash.balance) : '—'}</span>
        <span className="cash-sub">
          {cash ? <>of {money(cash.opening_balance)} opening</> : 'connecting'}
          {pending && <> · <span className="cash-hold">{money(cash!.pending_requests_total)} pending</span></>}
        </span>
      </div>
      {delta !== null && <span className="cash-delta" key={delta}>−{money(delta)}</span>}
    </div>
  )
}
