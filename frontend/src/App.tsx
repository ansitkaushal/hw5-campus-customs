import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './api'
import { Authorizations } from './components/Authorizations'
import { CashGauge } from './components/CashGauge'
import { FinishedLane } from './components/FinishedLane'
import { FinishToast } from './components/FinishToast'
import { PitBox } from './components/PitBox'
import { PitLane } from './components/PitLane'
import { API_BASE, POLL_IDLE_MS, POLL_LIVE_MS } from './config'
import type { Approvals, Cash, FeedEvent, Run, Ticket } from './types'

const FINISH_MS = 4200

export default function App() {
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [today, setToday] = useState('')
  const [cash, setCash] = useState<Cash | null>(null)
  const [approvals, setApprovals] = useState<Approvals>({ payment_requests: [], quotes: [] })
  const [runs, setRuns] = useState<Run[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [events, setEvents] = useState<FeedEvent[]>([])
  const [online, setOnline] = useState(true)
  const [starting, setStarting] = useState(false)
  const [startError, setStartError] = useState<string | null>(null)
  const [finish, setFinish] = useState<{ ticketId: number; ms: number | null } | null>(null)
  const [approver, setApproverState] = useState(() => localStorage.getItem('pitwall.approver') ?? '')
  const [resetting, setResetting] = useState(false)

  const cursor = useRef(0)
  const selectedRef = useRef<number | null>(null)
  const prevRuns = useRef<Record<string, Run['status']>>({})
  const onFinish = useRef<(id: number) => void>(() => {})

  const setApprover = (s: string) => {
    setApproverState(s)
    localStorage.setItem('pitwall.approver', s)
  }

  const refresh = useCallback(async () => {
    try {
      const [t, c, a, r] = await Promise.all([api.tickets(), api.cash(), api.approvals(), api.runs()])
      setTickets(t.tickets)
      setToday(t.today)
      setCash(c)
      setApprovals(a)
      setRuns(r.runs)
      setOnline(true)
      // A run that just went running -> done gets the completion toast.
      for (const run of r.runs) {
        if (prevRuns.current[run.run_id] === 'running' && run.status === 'done') {
          onFinish.current(run.ticket_id)
          const ms = run.finished_at ? Date.parse(run.finished_at) - Date.parse(run.started_at) : null
          setFinish({ ticketId: run.ticket_id, ms })
          setTimeout(() => setFinish((f) => (f?.ticketId === run.ticket_id ? null : f)), FINISH_MS)
        }
        prevRuns.current[run.run_id] = run.status
      }
    } catch {
      setOnline(false)
    }
  }, [])

  const pollEvents = useCallback(async () => {
    const id = selectedRef.current
    if (id === null) return
    try {
      const res = await api.events({ since: cursor.current, ticket_id: id, limit: 1000 })
      if (selectedRef.current !== id) return
      cursor.current = res.next_since
      if (res.events.length) {
        setEvents((prev) => {
          const last = prev.at(-1)?.index ?? -1
          return [...prev, ...res.events.filter((e) => e.index > last)]
        })
      }
    } catch {
      setOnline(false)
    }
  }, [])

  // Selecting a different car loads its full event history from the start.
  const selectTicket = useCallback((id: number | null) => {
    if (id === selectedRef.current) return
    selectedRef.current = id
    cursor.current = 0
    setSelectedId(id)
    setEvents([])
    setStartError(null)
    history.replaceState(null, '', id === null ? location.pathname : `#ticket=${id}`)
    if (id !== null) void pollEvents()
  }, [pollEvents])

  useEffect(() => { onFinish.current = selectTicket }, [selectTicket])

  // Deep link: /#ticket=101 opens that ticket in the pit box (used for shareable views and screenshots).
  useEffect(() => {
    const m = location.hash.match(/ticket=(\d+)/)
    if (m) selectTicket(Number(m[1]))
  }, [selectTicket])

  const anyRunning = runs.some((r) => r.status === 'running')
  useEffect(() => {
    const first = setTimeout(() => void refresh(), 0)
    const id = setInterval(() => {
      void refresh()
      void pollEvents()
    }, anyRunning ? POLL_LIVE_MS : POLL_IDLE_MS)
    return () => { clearTimeout(first); clearInterval(id) }
  }, [anyRunning, refresh, pollEvents])

  async function start(ticketId: number) {
    setStarting(true)
    setStartError(null)
    try {
      const run = await api.startRun(ticketId)
      prevRuns.current[run.run_id] = 'running'
      setRuns((rs) => [run, ...rs])
      setTickets((ts) => ts.map((t) => (t.id === ticketId ? { ...t, agents_running: true } : t)))
    } catch (err) {
      setStartError(err instanceof Error ? err.message : String(err))
    } finally {
      setStarting(false)
    }
  }

  async function approve(id: number) {
    await api.approve(id, approver.trim())
    await refresh()
  }

  async function reject(id: number, note: string) {
    await api.reject(id, approver.trim(), note)
    await refresh()
  }

  async function resetGarage() {
    if (!window.confirm('Reset to the original data? This restores the original database: cash, invoices, tickets, and clears drafts and approvals.')) return
    setResetting(true)
    try {
      await api.reset()
      selectTicket(null)
      await refresh()
    } catch (err) {
      window.alert(err instanceof Error ? err.message : String(err))
    } finally {
      setResetting(false)
    }
  }

  const open = tickets.filter((t) => t.state === 'open')
  const finished = tickets.filter((t) => t.state === 'resolved')
  const selected = tickets.find((t) => t.id === selectedId) ?? null
  const selectedRun = runs.find((r) => r.ticket_id === selectedId) ?? null
  const calls = approvals.payment_requests.filter((r) => r.ticket_id === selectedId)

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true"><i /><i /></span>
          <div>
            <p className="label">Campus Customs</p>
            <h1>Pit Wall</h1>
          </div>
        </div>
        <div className="topbar-meta">
          <span className="label">Race day</span>
          <span className="mono">{today || '—'}</span>
        </div>
        <div className="topbar-meta">
          <span className="label">Link</span>
          <span className={`link ${online ? 'ok' : 'down'}`} title={API_BASE}><i />{online ? 'Connected' : 'Offline'}</span>
        </div>
        <CashGauge cash={cash} />
        <button type="button" className="btn ghost" onClick={resetGarage} disabled={resetting || anyRunning}
          title={anyRunning ? 'Wait for the crew to finish' : 'Restore the original database'}>
          {resetting ? 'Resetting…' : 'Reset'}
        </button>
      </header>

      <main className="grid">
        <PitLane tickets={open} selectedId={selectedId} onSelect={selectTicket} />
        <PitBox ticket={selected} run={selectedRun} events={events} calls={calls} starting={starting}
          startError={startError} onStart={start} />
        <Authorizations approvals={approvals} cash={cash} approver={approver} setApprover={setApprover}
          onApprove={approve} onReject={reject} />
        <FinishedLane tickets={finished} runs={runs} selectedId={selectedId} onSelect={selectTicket} />
      </main>

      {finish && <FinishToast ticketId={finish.ticketId} ms={finish.ms} />}
    </div>
  )
}
