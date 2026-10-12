import { useState } from 'react'
import { money } from '../crew'
import type { Approvals, Cash, PaymentRequest } from '../types'
import { HoldButton } from './HoldButton'

const KIND: Record<PaymentRequest['kind'], { label: string; ref: (r: PaymentRequest) => string }> = {
  invoice: { label: 'Vendor invoice', ref: (r) => `Invoice #${r.ref_id}` },
  rent: { label: 'Rent', ref: (r) => `Lease ${r.ref_id}` },
  purchase_order: {
    label: 'Purchase order',
    ref: (r) => r.purchase_order
      ? `PO #${r.ref_id} · ${r.purchase_order.qty} × ${r.purchase_order.sku} ${r.purchase_order.size} · ETA ${r.purchase_order.expected_arrival}`
      : `PO #${r.ref_id}`,
  },
}

interface Props {
  approvals: Approvals
  cash: Cash | null
  approver: string
  setApprover: (s: string) => void
  onApprove: (id: number) => Promise<void>
  onReject: (id: number, note: string) => Promise<void>
}

/** The crew chief's call for a GO. Agents only prepare payments; a human holding Authorize is what moves cash. */
export function Authorizations({ approvals, cash, approver, setApprover, onApprove, onReject }: Props) {
  const [busy, setBusy] = useState<number | null>(null)
  const [errors, setErrors] = useState<Record<number, string>>({})
  const [declining, setDeclining] = useState<number | null>(null)
  const [note, setNote] = useState('')
  const reqs = approvals.payment_requests
  const named = approver.trim().length > 0

  async function act(id: number, fn: () => Promise<void>) {
    setBusy(id)
    setErrors((e) => ({ ...e, [id]: '' }))
    try { await fn(); setDeclining(null); setNote('') }
    catch (err) { setErrors((e) => ({ ...e, [id]: err instanceof Error ? err.message : String(err) })) }
    finally { setBusy(null) }
  }

  return (
    <section className={`panel auth ${reqs.length ? 'has-calls' : ''}`} aria-labelledby="auth-h">
      <header className="panel-h">
        <h2 id="auth-h">Authorizations</h2>
        <span className={`label ${reqs.length ? 'accent' : ''}`}>{reqs.length ? `${reqs.length} awaiting` : 'Clear'}</span>
      </header>

      <label className="field">
        <span className="label">Authorizing as</span>
        <input value={approver} onChange={(e) => setApprover(e.target.value)} placeholder="Your name" autoComplete="name" />
      </label>

      {reqs.length === 0 && (
        <p className="empty">Agents prepare payments but can’t send them. When the crew chief needs a GO, it lands here.</p>
      )}

      <ul className="calls" aria-live="polite">
        {reqs.map((r) => {
          const k = KIND[r.kind]
          const after = cash ? cash.balance - r.amount : null
          const short = after !== null && after < 0
          const frac = cash && cash.balance > 0 ? Math.min(r.amount / cash.balance, 1) : 1
          return (
            <li key={r.id} className={`call ${short ? 'is-short' : ''} ${busy === r.id ? 'is-busy' : ''}`}>
              <div className="call-top">
                <span className="label">Request {String(r.id).padStart(3, '0')}{r.ticket_id ? ` · Ticket ${r.ticket_id}` : ''}</span>
                <span className="call-kind">{k.label}</span>
              </div>
              <p className="call-amount">{money(r.amount)}</p>
              <div className="call-impact" aria-label="Effect on checking balance">
                <span className="call-impact-bar"><i style={{ width: `${frac * 100}%` }} /></span>
                <span className="call-impact-txt">
                  {cash ? money(cash.balance) : '—'} <span className="arrow">→</span>{' '}
                  <b className={short ? 'bad' : ''}>{after === null ? '—' : money(after)}</b>
                </span>
              </div>
              <dl className="call-facts">
                <dt>For</dt><dd>{k.ref(r)}</dd>
                <dt>Reason</dt><dd>{r.reason || '—'}</dd>
                <dt>Prepared by</dt><dd>{r.requested_by}</dd>
              </dl>
              {short && <p className="call-error">Not enough cash. This will be refused.</p>}

              {declining === r.id ? (
                <div className="call-decline">
                  <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Reason (optional)" autoFocus />
                  <div className="call-row">
                    <button type="button" className="btn ghost" onClick={() => { setDeclining(null); setNote('') }}>Cancel</button>
                    <button type="button" className="btn danger" disabled={!named || busy !== null}
                      onClick={() => act(r.id, () => onReject(r.id, note))}>Confirm decline</button>
                  </div>
                </div>
              ) : (
                <div className="call-row">
                  <button type="button" className="btn ghost" disabled={busy !== null} onClick={() => setDeclining(r.id)}>Decline</button>
                  <HoldButton label={busy === r.id ? 'Authorizing…' : 'Authorize'} disabled={!named || busy !== null}
                    onConfirm={() => act(r.id, () => onApprove(r.id))} />
                </div>
              )}
              {!named && <p className="hint">Enter your name to authorize.</p>}
              {errors[r.id] && <p className="call-error" role="alert">{errors[r.id]}</p>}
            </li>
          )
        })}
      </ul>

      {approvals.quotes.length > 0 && (
        <div className="quotes">
          <h3 className="label">Discount quotes for review</h3>
          {approvals.quotes.map((q) => (
            <p key={q.id} className="quote">
              <span className="mono">Q{q.id}</span> {q.qty} × {q.sku} {q.size} at {q.discount_pct}% off · {money(q.unit_price)} ea · {money(q.total)} · margin {money(q.unit_margin)}/unit
            </p>
          ))}
          <p className="hint">Quotes aren’t payments, so no cash moves. Review before replying to the customer.</p>
        </div>
      )}
    </section>
  )
}
