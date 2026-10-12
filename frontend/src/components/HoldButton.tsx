import { useEffect, useRef, useState } from 'react'

/** Press-and-hold confirmation for high-stakes actions. Works with pointer and keyboard (hold Space/Enter).
 *  The fill is a CSS transition and the confirm is a timer, so it stays smooth even in a throttled tab. */
export function HoldButton({ onConfirm, disabled, label, holdMs = 1100 }: {
  onConfirm: () => void; disabled?: boolean; label: string; holdMs?: number
}) {
  const [phase, setPhase] = useState<'idle' | 'holding' | 'done'>('idle')
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const clear = () => { if (timer.current) clearTimeout(timer.current); timer.current = null }
  const begin = () => {
    if (disabled || timer.current) return
    setPhase('holding')
    timer.current = setTimeout(() => {
      timer.current = null
      setPhase('done')
      onConfirm()
      setTimeout(() => setPhase('idle'), 900) // ready again if the action fails
    }, holdMs)
  }
  const cancel = () => {
    if (!timer.current) return
    clear()
    setPhase('idle')
  }
  useEffect(() => clear, [])

  return (
    <button
      type="button"
      className={`hold is-${phase}`}
      disabled={disabled}
      aria-label={`${label}: press and hold to confirm`}
      onPointerDown={(e) => { e.currentTarget.setPointerCapture?.(e.pointerId); begin() }}
      onPointerUp={cancel}
      onPointerCancel={cancel}
      onKeyDown={(e) => { if ((e.key === ' ' || e.key === 'Enter') && !e.repeat) { e.preventDefault(); begin() } }}
      onKeyUp={(e) => { if (e.key === ' ' || e.key === 'Enter') cancel() }}
      style={{ ['--hold' as string]: `${holdMs}ms` }}
    >
      <span className="hold-fill" aria-hidden="true" />
      <span className="hold-label">{phase === 'done' ? 'Authorizing…' : phase === 'holding' ? 'Keep holding' : label}</span>
      <span className="hold-hint" aria-hidden="true">Hold</span>
    </button>
  )
}
