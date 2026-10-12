# Campus Customs · Pit Wall: Dashboard Design

The dashboard (`frontend/`) is where a person watches five AI agents work a ticket and decides whether money moves. That shapes every design choice: it has to be **calm enough to read at a glance, live enough to follow in real time, and serious exactly where cash is involved.**

---

## 1. The concept: a pit wall, not a garage

In motorsport, the *pit wall* is where the team watches telemetry and makes calls while the crew does the physical work. That's exactly the human's role here: agents do the work; the human watches, and authorizes.

- **Tickets are race entries** waiting in the *pit lane*.
- **Starting a run is a pit stop**: the crew (agents) swarms one car.
- **The Boss is the crew chief**; Inventory, Accounting, Facilities, and Customer Service are *Tires, Fuel, Chassis,* and *Comms*.
- **Cash is fuel**: it only goes down, and you watch the level.
- **A payment is the crew chief radioing for a GO.**

### Why the metaphor survived but the costume didn't
The first version took the metaphor literally: warning-tape stripes, brushed metal, checkered flags, a livery color per ticket. It was fun for ten seconds, then it got loud. Every surface competed, and the colors stopped *meaning* anything. The redesign keeps the **story** (pit lane → pit box → finished; crew chief; fuel; GO) and drops the **props**, borrowing instead from how real F1 team apps and timing screens look: dark, precise, sparse, with color reserved for state.

> Principle: *the theme lives in the words and the structure; the visuals stay quiet so the data can talk.*

---

## 2. Visual language

| Choice | What | Why |
|---|---|---|
| **Graphite surfaces** | `#0a0b0d` background, three surface steps, 7–12% white hairline borders, a soft top gradient on panels | A dark, low-contrast base makes the few bright things (live agents, money) pop. Hairlines instead of heavy borders keep it uncluttered. |
| **Two accents, each with one job** | **Racing red** `#ff2d3d` = *live / needs attention*. **Electric green** `#00e08a` = *complete / authorized / cash remaining* | If red only ever means "something is happening or needs you," your eye learns to scan for it. No rainbow: ticket types are distinguished by a text code, not a color. |
| **HUD typography** | SF Pro for prose; **SF Mono with tabular numbers** for every figure, ID, time, and micro-label (uppercase, wide letter-spacing) | Monospaced digits don't jitter as timers tick or balances change, and they read as "instrument" rather than "app." Prose stays in a humanist sans so agent summaries are comfortable to read. |
| **Geometric accents** | A skewed red/white double bar as the logo; a short skewed red tick before each panel title; a red selection rail | Speed and direction suggested with a single slant, not with stripes and flags. |

---

## 3. Layout

```
┌───────────────────────────────────────────────────────────────────────────┐
│ ▮▮ Pit Wall       Race day 2026-08-31   Link ● Connected   (◔) $3,400.00  │  top bar
├──────────────┬────────────────────────────────────────┬───────────────────┤
│ PIT LANE     │ PIT BOX                                │ AUTHORIZATIONS    │
│ 101 Bulldog  │ 102  Rent due                ( 00:29 ) │ Authorizing as …  │
│ 102 Rent due │ ▬▬▬ ▬▬▬ ▬▬▬ ▬▬▬ ▬▬▬  sector strip      │ ┌ Request 001 ──┐ │
│ 103 Hoodies  │ ┌ 01 Boss · Crew Chief ─────── ACTIVE ┐│ │ $840.00       │ │
│              │ └─────────────────────────────────────┘│ │ 3,400 → 2,560 │ │
│              │ ┌ 02 Inventory ┐ ┌ 03 Accounting ┐     │ │ [Decline][Hold]│ │
│              │ ┌ 04 Facilities┐ ┌ 05 Cust. Svc  ┐     │ └───────────────┘ │
│              │ Timeline            │ Debrief          │                   │
├──────────────┴────────────────────────────────────────┴───────────────────┤
│ FINISHED   103 Bulk hoodie discount ● 00:51.0 · 4 handoffs                │
└───────────────────────────────────────────────────────────────────────────┘
```

- **Left → center → right follows the workflow**: *choose* a ticket, *watch* the crew, *decide* on money. The eye moves the same way the job does.
- **The pit box is the hero.** It gets the most space because that's where the live action is. Everything else is a supporting column.
- **Authorizations are sticky** on wide screens, so a payment request is never scrolled out of view while you read the timeline.
- **Finished runs along the bottom** like a results board: out of the way, but one click brings any finished ticket's full debrief back into the pit box.
- **Responsive**: three columns on desktop, two on laptops (authorizations tuck under the lane), a single stacked column on phones (lane → pit box → authorizations → finished) with no horizontal scroll.

---

## 4. How the agents read differently

The core problem: five agents, sometimes two running in parallel, each calling tools and handing off. A wall of chat bubbles would be unreadable. Instead each agent is a **telemetry card**, a live readout of *what this agent is doing right now*.

**Each card shows:**
- **Index + name + role**: `01 Boss · CREW CHIEF`, `03 Accounting · FUEL`. The index gives a fixed reading order; the role keeps the pit-crew story.
- **A status chip**: `STANDBY` (dim) → `ACTIVE` (red) → `COMPLETE` (green). Idle cards sit at reduced opacity so the working ones stand forward.
- **An "ON AIR" chip** on whichever agent produced the latest event, so when two agents run in parallel you can still tell who just spoke.
- **One current line**: the tools it's using in plain words (*"stock & price check · vendor status"*), then, when it finishes, its own one-sentence summary. The card always answers "what is it doing / what did it find?"
- **Telemetry numbers**: turns · tools · tokens, in mono, for anyone who wants to see the cost.
- **Tool tags**: every MCP tool it actually called, so you can audit the work at a glance.
- **A thin sweeping bar** across the top while active, a solid green line when complete.

**Supporting views:**
- **Sector strip**: five slim segments under the ticket header, one per agent, like F1 timing sectors. You see the shape of the whole run (who's done, who's live, who was never called) without reading anything.
- **Timeline**: the chronological team radio. Handoffs are indented by delegation depth and marked `↳` with the reason; completions get a green ✓; refusals and errors are red.
- **Debrief**: once agents finish, their one-line summaries stack up, followed by the Boss's *Waiting on you / Blockers / Next steps*. This is the "what happened" a human actually wants, without reading the timeline.

**Why the Boss card is full-width:** the crew chief directs everyone else, so it sits above the four specialists, which visually explains the delegation structure before you read a word.

---

## 5. Resolved tickets

- **While running**, the ticket's entry in the pit lane shows a red `LIVE` chip and a sweeping progress line along its bottom edge, so you can see which car is in the box even while looking at another one.
- **The lap ring** (top-right of the pit box) is the clock: it sweeps red once per minute while the crew works, then **closes to a full green ring** showing the final time. The time is the hero number, in mono.
- **Completion moment**: a frosted-glass toast drops in at the top: *"Ticket 102 complete · Final 00:53.6 · moved to Finished,"* with a check mark that draws itself. It's satisfying without hijacking the screen, and it disappears on its own.
- **Finished lane**: the ticket leaves the pit lane and appears in Finished with a green dot, its pit time, and how many handoffs it took. Clicking it reloads the full debrief and timeline.
- **Honest status**: a ticket is marked resolved when its run ends, but anything still needing a human (a payment request, a quote) stays visible in Authorizations, and the ticket's note records that it was left "waiting on approval." Nothing pending hides behind a green check.

---

## 6. Cash

- **A 270° radial gauge** in the top bar: the green arc is the checking balance as a share of the opening balance (full = $3,400), with the percentage in the center and the exact amount in large mono beside it.
- **Pending money is shown before it moves**: when agents have queued payments, the arc splits. Green is what will remain; a **red segment** is the amount awaiting approval, and the label reads *"$840.00 pending."* You can see the consequence of saying yes before you say it.
- **When a payment is approved**, the arc animates down smoothly and a small red **"−$840.00"** tag appears and fades, so the drop is noticeable without being alarming.
- **Low fuel**: below 25% the arc turns red. There's no revenue in this business, so a low tank is a real warning.

*Why a ring, not a number:* a number tells you the balance; a ring tells you **how much of the runway is left** at a glance, which is the question that matters when cash only goes out.

---

## 7. The approval moment

This is the one place the interface asks a human to take an irreversible, real-money action, so it's designed to be **important and deliberate, but not loud**.

- **The crew chief's request** surfaces twice: a soft red notice inside the pit box (*"Crew chief requesting a GO: 1 payment ($840.00) waiting in Authorizations"*) and as a card in the Authorizations panel, which gains a thin red hairline when something is waiting.
- **The card is a decision brief**: the amount is the largest number on the screen; an **impact bar** shows its bite out of the balance (`$3,400.00 → $2,560.00`); then *For* (Invoice #501), *Reason* (in the agent's words), *Prepared by* (Accounting). If cash can't cover it, the card says so before you try.
- **Your name is required** ("Authorizing as…") and is written to the `payments` table as `approved_by`, so every dollar has a human owner.
- **Press and hold to authorize** (≈1.1 s). A green fill sweeps across the button and the label changes to *"Keep holding."* Release early and it springs back. A stray click can't spend money, but a deliberate one feels decisive. It works with Space/Enter for keyboard users.
- **Declining is a calm two-step**: *Decline* opens an optional reason field and a *Confirm decline*. No money moves.
- **Agents physically can't do this**: the approve/reject tools are filtered out of every agent's toolset; this button is the only path.

---

## 8. Motion

Motion is used only to explain change, never to decorate:

| Moment | Motion |
|---|---|
| Panels, cards, timeline lines appear | 6 px rise + fade, 300–400 ms ease-out |
| Agent becomes active | Card border warms to red; a light sweep runs across its top bar |
| Agent finishes | Top bar settles to solid green; chip turns green |
| Selection | Red rail grows from the center of the entry |
| Payment approved | Gauge arc eases down (1.2 s); "−$" tag fades in and out |
| Run complete | Ring closes to green; toast slides in; check draws itself |

Everything respects `prefers-reduced-motion`: animations collapse to instant state changes.

---

## 9. What makes it feel special

1. **The story is in the structure.** Pit lane → pit box → finished, crew chief and crew, fuel, a GO. You understand the system's flow from the layout before reading any text.
2. **You can feel the agents working.** Cards light up, the ON AIR tag hops between agents during a handoff, the sector strip fills in. A multi-agent system that's normally invisible becomes something you can *watch*.
3. **One glance answers the three questions that matter:** *Who's working?* (sector strip), *How long?* (lap ring), *How much runway?* (cash ring).
4. **Restraint makes the important things land.** Because red only means "live / needs you," the authorization card and the active agent are unmissable without flashing or sound.
5. **The money moment has weight.** Hold-to-authorize, the before→after impact bar, and a named approver make spending feel like a real decision, the way it should with real money.
6. **Everything is honest.** Tool tags, token counts, the full timeline, and pending items that never hide behind "resolved" mean the human can trust what they see, which is what turns a demo into something you'd actually use at a desk.

---

## 10. Accessibility and practicality

- Status is never color-only: every state also has a text label (`ACTIVE`, `COMPLETE`, `ON AIR`, `pending`).
- Text contrast on graphite stays high for body copy; dim tones are reserved for secondary metadata.
- Every interactive element is a real button or input with visible focus; hold-to-authorize works from the keyboard; live regions announce new timeline lines, new requests, and completions.
- The dashboard recovers on reload (runs, events, and pending approvals are re-fetched from the backend), and it shows **Connected / Offline** in the top bar so a dead backend is obvious.

---

## Files

| Area | File |
|---|---|
| Tokens, layout, motion | `frontend/src/index.css` |
| Top bar, polling, run lifecycle | `frontend/src/App.tsx` |
| Pit lane / Finished entries | `components/CarCard.tsx`, `PitLane.tsx`, `FinishedLane.tsx` |
| Pit box, sector strip, debrief | `components/PitBox.tsx` |
| Agent telemetry cards | `components/Station.tsx` |
| Team radio timeline | `components/Timeline.tsx` |
| Lap ring | `components/LapRing.tsx` |
| Cash gauge | `components/CashGauge.tsx` |
| Authorizations + hold button | `components/Authorizations.tsx`, `HoldButton.tsx` |
| Completion toast | `components/FinishToast.tsx` |
| Crew roles, tool labels, state folding | `frontend/src/crew.ts` |
