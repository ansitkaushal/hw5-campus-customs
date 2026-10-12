# Campus Customs Harness

Shared reference for the Campus Customs back office: an MCP server over SQLite, a five-agent PydanticAI team, a FastAPI backend, and the "Pit Wall" React dashboard.

**Part A** is the final, complete reference (as of Problem 9). **Part B** is the problem-by-problem build log, kept as history; where they differ, Part A is current.

| | |
|---|---|
| Original DB (never modified) | `data/campus_customs.db` |
| Working DB (everything reads/writes here) | `data/campus_customs_new.db` |
| Reset | copy original → working (`python -m backend.reset_db`, `POST /api/reset`, or the dashboard's **Reset**) before every full run |
| "Today" | `desk.date_today` = **2026-08-31** (never the system clock) |
| Model | `gpt-6-luna` only, via Portkey (`PORTKEY_API_KEY` in the project-root `.env`), Responses API, default temperature |
| Run it | `backend/`: `uvicorn main:app --reload --port 8000` · `frontend/`: `npm run dev` → http://localhost:5173 |

---

# Part A: Final reference

## A1. Tables

**Original schema** (shipped in `campus_customs.db`)

| Table | Fields | Why it matters to the agents |
|---|---|---|
| `desk` | date_today, notes | The simulation's "today"; every overdue / due-in / arrival date is measured from it. |
| `tickets` | id, type, requester, subject, sku, size, qty, lease_id → leases, invoice_id → invoices, status, notes, created_at | The work queue; the Boss reads each ticket and its links decide which specialists get involved. |
| `inventory` | sku, name, size, qty, location (PK sku+size) | Stock per SKU **and size**; shortfalls are found here before anything is promised. |
| `pricing` | sku, unit_cost, list_price | Margin and the discount floor; also the per-unit cost of a restock PO. |
| `vendors` | id, name, specialty, lead_days | Who can restock what, and arrival = today + lead_days. |
| `invoices` | id, vendor_id → vendors, amount, due_date, status, description | Money owed; an `open` invoice puts that vendor **on hold** (won't ship). |
| `leases` | id, space_name, landlord, monthly_rent, next_due, notes | Rent amount and due date; paying rent advances `next_due` one month. |
| `cash_accounts` | name, balance, date | The only cash (no revenue modeled); can never go negative. |
| `payments` | id, kind, ref_id, amount, account, paid_at, approved_by | Ledger of every cash outflow, each with the human approver's name. |

**Work tables** (created on demand in the working copy by the MCP server; a reset removes them)

| Table | Written by | Purpose |
|---|---|---|
| `payment_requests` | `request_payment`, `draft_purchase_order` | Payments agents *prepared*: kind (invoice / rent / purchase_order), amount (read from DB), requester, reason, status pending → approved / rejected, decided_by |
| `purchase_orders` | `draft_purchase_order` | Restock POs: vendor, sku, size, qty, unit_cost, total, expected_arrival, status pending_approval → ordered / rejected |
| `quotes` | `propose_bulk_quote` | Discount quotes for human review (never below unit cost) |
| `message_drafts` | `draft_customer_message` | Customer / landlord / vendor messages, always status `draft` (never sent) |
| `ticket_updates` | `update_ticket` | Status history with notes and who changed it |

```
tickets.invoice_id → invoices.id → vendors.id      tickets.lease_id → leases.id
tickets.sku/size   → inventory(sku,size), pricing.sku
payment_requests.ref_id → invoices.id | leases.id | purchase_orders.id (by kind)
payments.ref_id    → invoices.id | leases.id | purchase_orders.id;  payments.account → cash_accounts.name
```

## A2. MCP server: 17 tools (`mcp_server/server.py`, FastMCP, server `campus-customs`)

The **only** path to shop data, for agents and for the backend. Values come from the DB plus arithmetic on them; a missing row returns `{"error": ...}`; amounts are always read from the DB, never accepted from a caller. Registered for Claude Code in the project-root `.mcp.json`.

| # | Tool | Tables | Kind | Agents allowed |
|---|---|---|---|---|
| 1 | `list_tickets` | tickets, desk | read | none (backend / dashboard) |
| 2 | `list_open_tickets` | tickets, desk | read | Boss |
| 3 | `get_ticket` | tickets, leases, invoices, ticket_updates, desk | read | all five |
| 4 | `check_stock_and_pricing` | inventory, pricing | read | Boss, Inventory, Accounting, Customer Service |
| 5 | `list_vendors_with_status` | vendors, invoices, desk | read | Inventory |
| 6 | `get_invoice_vendor_status` | invoices, vendors, desk | read | Boss, Inventory, Accounting |
| 7 | `get_rent_due_and_cash` | leases, cash_accounts, desk | read | Boss, Accounting, Facilities |
| 8 | `get_cash_position` | cash_accounts, invoices, vendors, leases, payment_requests, payments, desk | read | Boss, Accounting, Facilities |
| 9 | `list_pending_approvals` | payment_requests, purchase_orders, quotes | read | Boss, Accounting |
| 10 | `list_message_drafts` | message_drafts | read | none (backend / dashboard) |
| 11 | `draft_purchase_order` | vendors, inventory, pricing, invoices → **purchase_orders, payment_requests** | draft | Inventory |
| 12 | `request_payment` | invoices / leases, cash_accounts → **payment_requests** | draft | Accounting |
| 13 | `propose_bulk_quote` | pricing → **quotes** | draft | Accounting |
| 14 | `draft_customer_message` | → **message_drafts** | draft | Customer Service |
| 15 | `update_ticket` | tickets → **ticket_updates** | write | Boss |
| 16 | `approve_payment_request` | payment_requests, cash_accounts, invoices / leases / purchase_orders → **payments** | **human only** | none |
| 17 | `reject_payment_request` | payment_requests, purchase_orders | **human only** | none |

Guards built into the tools: PO refused while the vendor has an open invoice (re-checked at approval); duplicate payment request refused; request refused if cash can't cover it; quote refused below unit cost; approval refused with a blank approver, a non-pending request, or if the account would go negative; approval is one transaction (`payments` row + `cash_accounts` debit + invoice `paid` / lease `next_due` +1 month / PO `ordered`).

## A3. The five agents (`backend/agents/`, prompts in `backend/prompts/`)

Every agent: `gpt-6-luna`, structured `AgentReport` output (summary, findings, actions_taken, awaiting_human_approval, blockers, next_steps), its own MCP tool allowlist (`backend/mcp_tools.py`), plus `delegate_to_agent(agent, task, reason)` to reach **any** other agent (full connectivity).

| Agent (pit role) | Prompt | Owns | Must check before acting | Never |
|---|---|---|---|---|
| **Boss** (Crew Chief) | `boss.md` | Ticket board, routing, priorities, final call, ticket status | Ticket from the system, today's date, cash position, existing approvals | Pay or approve; promise a blocked delivery; send a job to two owners at once |
| **Inventory** (Tires) | `inventory.md` | Stock by SKU/size, shortfalls, restock vendor, lead time, draft POs | Exact SKU+size stock; vendor specialty and lead days; **open invoices before any restock** | Pay; contact vendors; change stock; route around a refused PO |
| **Accounting** (Fuel) | `accounting.md` | Cash, payables, margins, payment requests, discount quotes | Cash after pending requests; the bill from the DB; duplicates; **no negative balance**; margin before discount | Pay or approve; claim something is paid without a tool result; invent numbers |
| **Facilities** (Chassis) | `facilities.md` | Lease, rent timing, landlord notices, shop space | Lease record vs the notice; days until due; competing bills | Approve payments; sign/change a lease; contact the landlord |
| **Customer Service** (Comms) | `customer_service.md` | Customer and external message drafts | Ticket details; every fact it states; what's still pending | **Send anything**; promise unverified dates, prices, or discounts; share internal details |

**Loop and limits** (`backend/config.py`): per agent run 8 model requests / 60k tokens; per ticket max 8 delegations, depth 3, 250k tokens; no self-delegation or delegating to an agent already waiting in the chain. Every step is appended to `output/audit_trail.json` (run_start, model_request, model_response with tool calls + args, delegation with **reason**, delegation_refused, run_end with report + tokens, error, plus human_approval / human_rejection / db_reset).

## A4. API routes (`backend/main.py`, FastAPI on :8000, CORS for :5173)

| Method | URL | What it does |
|---|---|---|
| GET | `/` | Redirects to `/docs` (interactive API docs) |
| GET | `/api/health` | Liveness; model and DB in use |
| GET | `/api/tickets` | All tickets: DB status, `open`/`resolved`, `agents_running` |
| GET | `/api/tickets/{id}` | One ticket + linked lease/invoice + status history + message drafts |
| POST | `/api/tickets/{id}/run` | Start the team (Boss first) in the background → `202` with run record; `404` unknown, `409` already running. When the run finishes, the ticket is marked `resolved` with a note of the Boss's status and anything still awaiting a human |
| GET | `/api/runs` | All runs since backend start (start/finish times, report, handoffs, tokens) |
| GET | `/api/runs/{run_id}` | One run's status and Boss report |
| GET | `/api/events?since=&limit=&ticket_id=&run_id=` | Live feed from the audit trail: agent, depth, event, what it said, tools used |
| GET | `/api/approvals` | Pending payment requests (with PO detail) and quotes |
| POST | `/api/approvals/{id}/approve` | **Only route that moves cash**; body `{"approved_by": name}`; `409` if refused (e.g. would go negative) |
| POST | `/api/approvals/{id}/reject` | Human declines; no cash moves |
| GET | `/api/cash` | Checking balance, opening balance, pending total, balance after pending |
| POST | `/api/reset` | Restore the original DB (`409` while agents run); audit trail kept |

## A5. Dashboard ("Pit Wall", `frontend/`, React + Vite + TS)

Design rationale: `output/design.md`. Calls `http://localhost:8000` (`src/config.ts`).

| Area | Shows | Route(s) |
|---|---|---|
| Top bar | Race day, backend link status, **radial cash gauge** (balance vs opening, red segment = pending, "−$" tag on approval), Reset | `/api/cash`, `/api/reset` |
| Pit lane | Open tickets as race entries (number, class code, specs, LIVE + progress line while running) | `/api/tickets` |
| Pit box | Selected ticket, **lap ring** timer, **Start pit stop**, **sector strip** (one segment per agent), five **telemetry cards** (status, ON AIR, current action, turns/tools/tokens, tool tags), **timeline** (handoffs with reasons), **debrief** (each agent's summary + Boss's waiting-on-you / blockers / next steps) | `/api/tickets/{id}/run`, `/api/runs`, `/api/events` |
| Authorizations | Each payment request: amount, before→after balance bar, for / reason / prepared by; **press-and-hold Authorize** (named approver required) or two-step Decline; discount quotes listed for review | `/api/approvals`, `/approve`, `/reject` |
| Finished | Resolved tickets with pit time and handoffs; click to reopen the debrief; completion toast on finish | `/api/tickets`, `/api/runs` |

Deep link: `http://localhost:5173/#ticket=101` opens a ticket (used for the Problem 9 screenshots).

## A6. Safety rules

**Customers and money**
1. **No real outbound contact.** No agent has a send tool; Customer Service only saves `message_drafts` with status `draft`. (The Gmail/Outlook MCP servers in this workspace are not connected to the agent team.)
2. **Every payment and purchase needs a named human.** Agents can only queue (`request_payment`, `draft_purchase_order`); `approve_payment_request` / `reject_payment_request` are filtered out of every agent's toolset and are reachable only through the dashboard's hold-to-authorize → `POST /api/approvals/{id}/approve`.
3. **No overdrafts.** The pay tool refuses any payment that would take an account below zero; `request_payment` also refuses up front.
4. **A payment updates every related table atomically:** `payments` (with `approved_by`), `cash_accounts`, and the invoice / lease / PO.
5. **Vendor rule enforced in code:** a vendor with an open unpaid invoice can't get a PO, and approval re-checks it.
6. **No invented data:** facts only from MCP tools over the working DB; amounts read from the DB; missing rows return errors; "today" is `desk.date_today`; lead times from `vendors`.
7. **Least privilege:** each role sees only its own tools (e.g. Facilities can read rent but can't queue payments; Customer Service can't touch money).
8. **Clean, reversible runs:** reset before full runs; the original DB is never written; the audit trail is append-only.

**Token and loop limits**
9. Per-agent caps (8 requests, 60k tokens) and per-ticket caps (8 delegations, depth 3, 250k tokens); a stuck agent returns a "stopped early" report instead of looping.
10. No cycles: an agent can't delegate to itself or to anyone already waiting in its chain.
11. Every handoff is logged with its reason, so redundant delegation is visible (Problem 5 surfaced one, which led to the Boss's "one owner per job" rule; it held in every later run).
12. One fixed model; narrow single-purpose tools with compact outputs; audit-trail tool results clipped to 2,000 characters.

**Known gaps** (what a real deployment would add): the dashboard has no login, so anyone who can reach it can approve; run state is in memory; a PO draft doesn't check cash up front (the approval does); Customer Service's 101 draft mentioned the pending $840 payment, an internal detail the prompt says to omit, so the instructions alone aren't enough and an output check would help.

## A7. Problem 9 results (full run)

Reset → start **$3,400.00** → ran 101, 102, 103 from the dashboard → approved as **Ansit Kaushal**: invoice 501 **−$840.00** (101) and rent lease 1 **−$2,400.00** (102); 103 created no payment → end **$160.00** = `cash_accounts.checking` exactly. All three tickets `resolved`; 3 unsent drafts; 0 POs, 0 quotes, 0 pending. Runs `c7466eb70d3c` (101, 5 s, 3 handoffs, 47,000 tokens), `183685920923` (102, 25 s, 3 handoffs, 33,708 tokens), `8be236ad2d1d` (103, 31 s, 3 handoffs, 33,767 tokens); 122 new audit events (190 → 312). Details: `output/desk_tickets.html` (Actual + Cash tabs), `output/resolved_tickets.json`, `output/resolved_board.html`.

---

# Part B: Build log (by problem)

## Problem 2: Database schema

"Today" in the simulation is `desk.date_today` = **2026-08-31**.

### desk
| Field | Type | Notes |
|---|---|---|
| date_today | TEXT | Simulation "today" (YYYY-MM-DD) |
| notes | TEXT | Free-form desk notes |

**Why it matters:** The single source of "today"; every overdue / due-soon / lead-time calculation must use this date, not the system clock.

### tickets
| Field | Type | Notes |
|---|---|---|
| id | INTEGER PK | Ticket number |
| type | TEXT | `customer_order`, `rent_notice`, `price_override`, ... |
| requester | TEXT | Who raised it (customer, landlord, student org) |
| subject | TEXT | Short title |
| sku | TEXT | → `inventory.sku` / `pricing.sku` (if product-related) |
| size | TEXT | → `inventory.size` |
| qty | INTEGER | Units requested |
| lease_id | INTEGER FK | → `leases.id` |
| invoice_id | INTEGER FK | → `invoices.id` |
| status | TEXT | `open`, ... |
| notes | TEXT | Request details |
| created_at | TEXT | ISO timestamp |

**Why it matters:** The work queue; the Boss reads each ticket and its foreign keys tell it which specialist and which tables are involved.

### inventory
| Field | Type | Notes |
|---|---|---|
| sku | TEXT | Product code (PK part 1) |
| name | TEXT | Product name |
| size | TEXT | S/M/L/XL or OS (PK part 2) |
| qty | INTEGER | Units on hand |
| location | TEXT | Shelf / aisle |

**Why it matters:** Inventory agent checks stock per SKU + size here to spot shortfalls before anything is promised to a customer.

### pricing
| Field | Type | Notes |
|---|---|---|
| sku | TEXT PK | Product code |
| unit_cost | REAL | What we pay per unit |
| list_price | REAL | What we charge per unit |

**Why it matters:** Accounting uses cost vs. price to check margins and set a floor on any discount; also the basis for restock purchase-order cost.

### vendors
| Field | Type | Notes |
|---|---|---|
| id | INTEGER PK | Vendor id |
| name | TEXT | Vendor name |
| specialty | TEXT | What they supply |
| lead_days | INTEGER | Days from order to delivery |

**Why it matters:** Inventory picks the right restock vendor by specialty and computes arrival date = `date_today + lead_days`.

### invoices
| Field | Type | Notes |
|---|---|---|
| id | INTEGER PK | Invoice number |
| vendor_id | INTEGER FK | → `vendors.id` |
| amount | REAL | Amount owed |
| due_date | TEXT | Due date |
| status | TEXT | `open` / `paid` |
| description | TEXT | What it was for |

**Why it matters:** Bills we owe; an `open` invoice blocks that vendor from shipping, and overdue ones are flagged against `date_today`.

### leases
| Field | Type | Notes |
|---|---|---|
| id | INTEGER PK | Lease id |
| space_name | TEXT | The rented space |
| landlord | TEXT | Who we pay |
| monthly_rent | REAL | Rent amount |
| next_due | TEXT | Next rent due date |
| notes | TEXT | Lease notes |

**Why it matters:** Facilities uses this to know rent amount and due date; paying rent should advance `next_due`.

### cash_accounts
| Field | Type | Notes |
|---|---|---|
| name | TEXT PK | Account name |
| balance | REAL | Current balance |
| date | TEXT | Date of balance |

**Why it matters:** The only cash available (no revenue is modeled); the pay tool must refuse any payment that would make the balance negative.

### payments
| Field | Type | Notes |
|---|---|---|
| id | INTEGER PK | Payment id |
| kind | TEXT | e.g. `invoice`, `rent` |
| ref_id | INTEGER | Id of the invoice / lease paid |
| amount | REAL | Amount paid |
| account | TEXT | → `cash_accounts.name` |
| paid_at | TEXT | Date paid (`date_today`) |
| approved_by | TEXT | Human approver (required) |

**Why it matters:** Audit log of every cash outflow; each human-approved payment writes a row here in the same transaction that debits cash and updates the invoice/lease.

### Relationships
```
tickets.invoice_id ─→ invoices.id ─→ vendors.id
tickets.lease_id   ─→ leases.id
tickets.sku/size   ─→ inventory(sku,size), pricing.sku
payments.ref_id    ─→ invoices.id or leases.id (by kind)
payments.account   ─→ cash_accounts.name
```

### Starting state (2026-08-31)
- Cash: checking **$3,400**
- Open invoice #501: Bulldog Print Co, $840, due 2026-08-28 → **overdue**
- Rent: Chapel Street shop, $2,400, due 2026-09-02 (in 2 days)
- Payments: none yet

### Open tickets
| Ticket | Type | Ask | Links | Key facts |
|---|---|---|---|---|
| 101 | customer_order | 1 × CC-TEE-WHITE size S (Tauhid Zaman) | invoice 501 → Bulldog Print Co | Stock S = 0; restock vendor has overdue open invoice $840, so it won't ship until paid; lead 5 days |
| 102 | rent_notice | Shop rent due (Elm City Properties) | lease 1 | $2,400 due 2026-09-02; cash $3,400 |
| 103 | price_override | 20 × CC-HOOD-NAVY size M, bulk discount (Yale AI Club) | sku/size → inventory, pricing | Stock M = 8 → short 12; cost $22 / list $58; restock from Bulldog Print Co (same open invoice) |

### Cross-ticket tension
- Paying invoice 501 ($840) + rent ($2,400) = $3,240 → leaves **$160**.
- Restocking 12 hoodies at $22 = $264 → total $3,504 **exceeds** $3,400 cash.
- Agents can't do everything; the Boss must prioritise (rent and the overdue invoice before new restock spend) and every payment goes to a human for approval.

---

## Problem 3: MCP server tools

Server: `mcp_server/server.py` (FastMCP, name `campus-customs`), reading `data/campus_customs_new.db`. All tools are read-only, return only database values (plus arithmetic on them), and return `{"error": ...}` if a row is missing.

| Tool | Reads tables | Unlocks ticket | Why it's the right tool |
|---|---|---|---|
| `get_invoice_vendor_status(invoice_id)` | `invoices`, `vendors`, `desk` | **101** (Bulldog tee, size S) | Ticket 101 points at invoice 501, and this tool shows that the $840 invoice to Bulldog Print Co is 3 days overdue, so the only apparel vendor is on hold and can't reprint the size-S tee until it's paid, and that it then takes 5 days. |
| `get_rent_due_and_cash(lease_id)` | `leases`, `cash_accounts`, `desk` | **102** (rent notice) | Ticket 102 points at lease 1, and this tool puts the $2,400 rent due in 2 days next to the $3,400 checking balance so Facilities and Accounting can see that paying it is possible and leaves $1,000. |
| `check_stock_and_pricing(sku, size, qty_requested)` | `inventory`, `pricing` | **103** (20 hoodies, size M, bulk discount) | Ticket 103 needs both answers at once: only 8 size-M hoodies exist (short 12), and at $22 cost / $58 list any discount deeper than 62.1% loses money, which sets the floor for the discount reply. |

Note: `check_stock_and_pricing("CC-TEE-WHITE", "S", 1)` also confirms the 0-unit stockout behind ticket 101.

### Verified outputs (2026-08-31 data)
- `get_invoice_vendor_status(501)` → open, 3 days overdue, Bulldog Print Co, lead 5 days, `vendor_on_hold: true`
- `get_rent_due_and_cash(1)` → $2,400 due 2026-09-02 (2 days), cash $3,400, `cash_after_rent: 1000`
- `check_stock_and_pricing("CC-HOOD-NAVY", "M", 20)` → on hand 8, shortfall 12, margin $36/unit, break-even discount 62.1%

---

## Problem 5: Agent team and MCP tools

### Stack
- **Framework:** PydanticAI 2.55 (`backend/agents/`), one `Agent` per role, structured output `AgentReport` (`backend/models.py`).
- **Model:** `gpt-6-luna` only, set once in `backend/config.py` (`MODEL_NAME`), through Portkey (`PORTKEY_API_KEY` from the project-root `.env`). Uses the Responses API because Portkey/`gpt-6-luna` rejects function tools on `/v1/chat/completions`. No temperature override.
- **Tools:** every shop fact comes from the `campus-customs` MCP server over `data/campus_customs_new.db` (`backend/mcp_tools.py` → `MCPToolset`, stdio). There is no other data path.
- **Delegation:** every agent has `delegate_to_agent(agent, task, reason)` and can reach every other agent (full connectivity). Cycles are blocked (an agent already waiting in the chain can't be called again).
- **Audit:** `output/audit_trail.json`, append-only JSON array, one event per agent-loop step.
- **Run:** `python -m backend.team --all --reset` (reset DB, then Boss works each open ticket). Reset alone: `python -m backend.reset_db`.

### Agents
| Agent | Prompt | Owns | MCP tools it can call |
|---|---|---|---|
| Boss | `prompts/boss.md` | Ticket board, routing, priorities, final call, ticket status | `list_open_tickets`, `get_ticket`, `update_ticket`, `get_cash_position`, `list_pending_approvals`, `check_stock_and_pricing`, `get_invoice_vendor_status`, `get_rent_due_and_cash` |
| Inventory | `prompts/inventory.md` | Stock by SKU/size, shortfalls, restock vendor, lead time, draft POs | `get_ticket`, `check_stock_and_pricing`, `list_vendors_with_status`, `get_invoice_vendor_status`, `draft_purchase_order` |
| Accounting | `prompts/accounting.md` | Cash, invoices, margins, payment requests, discount quotes | `get_ticket`, `get_cash_position`, `get_invoice_vendor_status`, `get_rent_due_and_cash`, `check_stock_and_pricing`, `list_pending_approvals`, `request_payment`, `propose_bulk_quote` |
| Facilities | `prompts/facilities.md` | Lease, rent timing, landlord notices, shop space | `get_ticket`, `get_rent_due_and_cash`, `get_cash_position` |
| Customer Service | `prompts/customer_service.md` | Customer / external message drafts | `get_ticket`, `check_stock_and_pricing`, `draft_customer_message` |

All five also have `delegate_to_agent` (a backend tool, not a shop-data tool).

### MCP tools (15 at this point; 17 after Problem 7, see A2)
| Tool | Tables | Type | Who can call |
|---|---|---|---|
| `list_open_tickets` | tickets, desk | read | Boss |
| `get_ticket` | tickets, leases, invoices, ticket_updates, desk | read | all agents |
| `check_stock_and_pricing` | inventory, pricing | read | Boss, Inventory, Accounting, CS |
| `list_vendors_with_status` | vendors, invoices, desk | read | Inventory |
| `get_invoice_vendor_status` | invoices, vendors, desk | read | Boss, Inventory, Accounting |
| `get_rent_due_and_cash` | leases, cash_accounts, desk | read | Boss, Accounting, Facilities |
| `get_cash_position` | cash_accounts, invoices, vendors, leases, payment_requests, desk | read | Boss, Accounting, Facilities |
| `list_pending_approvals` | payment_requests, purchase_orders, quotes | read | Boss, Accounting |
| `draft_purchase_order` | vendors, inventory, pricing, invoices → writes purchase_orders, payment_requests | draft | Inventory |
| `request_payment` | invoices / leases, cash_accounts → writes payment_requests | draft | Accounting |
| `propose_bulk_quote` | pricing → writes quotes | draft | Accounting |
| `draft_customer_message` | writes message_drafts | draft | Customer Service |
| `update_ticket` | tickets → writes ticket_updates | write | Boss |
| `approve_payment_request` | payment_requests, cash_accounts, invoices / leases / purchase_orders → writes payments | **human only** | no agent |
| `reject_payment_request` | payment_requests, purchase_orders | **human only** | no agent |

New work tables (`payment_requests`, `purchase_orders`, `quotes`, `message_drafts`, `ticket_updates`) are created on demand in the working copy; the original database is never modified.

### Audit trail fields (per step)
`ts`, `run_id`, `ticket_id`, `agent`, `depth`, `chain` (who asked whom), `step`, `event` (`run_start`, `model_request`, `model_response`, `delegation`, `delegation_refused`, `run_end`, `error`), `model`, `text`, `tool_calls` (name + args), `tool_results` (clipped to 2,000 chars), `usage` (tokens), `detail` (delegation target/task/reason, final report).

### Verified
- Fake-model check: each agent is offered only its listed tools; none sees `approve_payment_request` / `reject_payment_request`.
- Tool guards on a scratch DB: vendor-on-hold PO refused; duplicate payment request refused; 70% hoodie discount refused (below cost); blank approver refused; $264 PO refused when cash was $160.
- Live run on ticket 102 (`run_id 6bc284578a5c`, 47,614 tokens, 4 delegations): Boss → Facilities + Accounting; Facilities → Accounting + Customer Service. One $2,400 rent request queued (the duplicate from the second Accounting call was refused by the tool), a landlord draft saved, ticket set to `waiting_on_approval`, **no payment made**. DB reset afterwards. The Boss prompt was then tightened to give each job one owner.

### Safety

**Guardrails for customers and money**
- **No real emails or vendor contact.** No agent has a send tool; Customer Service only has `draft_customer_message`, which saves to `message_drafts` with status `draft`. Drafts stay on the board for human review.
- **Human approval for all spend.** Agents can only *queue* (`request_payment`, `draft_purchase_order`). `approve_payment_request` / `reject_payment_request` are filtered out of every agent's toolset and require a named human (`approved_by`). No agent can authorize spend on its own.
- **No overdrafts.** The approve tool refuses any payment that would take a cash account negative; `request_payment` also refuses up front if cash can't cover it.
- **Every payment updates the books in one transaction:** `payments` row, `cash_accounts` debit, and the source (`invoices.status='paid'`, `leases.next_due` advanced a month, or `purchase_orders.status='ordered'`).
- **No invented data.** Prices, stock, balances, dates, and amounts come only from MCP tools reading `campus_customs_new.db`; payment amounts are read from the database, never accepted from the model. Missing rows return `{"error": ...}`. "Today" is always `desk.date_today`.
- **Business rules live in the tools, not just the prompts.** A vendor with an open unpaid invoice can't get a purchase order (`draft_purchase_order` refuses; approval re-checks); discounts below unit cost are refused by `propose_bulk_quote`; duplicate payment requests are refused. No agent can reason its way around them.
- **Least-privilege tool scoping:** each role sees only the tools for its job (e.g. Facilities can read rent but can't queue payments; Customer Service can't touch money).
- **Reset before full runs** (`backend/reset_db.py`) so every run starts from the original values; the original DB is never written.

**Limits to control token use** (all in `backend/config.py`)
- **Per-agent loop cap:** 8 model requests and 60,000 tokens per agent run (`UsageLimits`); a stuck agent stops and returns a "stopped early" report instead of spiraling.
- **Per-ticket caps across the team:** max 8 delegations, max delegation depth 3, and 250,000 tokens; beyond that `delegate_to_agent` refuses and the agent must finish with what it has.
- **No delegation loops:** an agent can't delegate to itself or to anyone already waiting in the chain.
- **Every handoff is logged with its reason** (`delegation` / `delegation_refused` events), so loops or redundant delegation are easy to spot and fix (the ticket-102 test surfaced one, which led to the "one owner per job" rule in the Boss prompt).
- **One fixed model** (`gpt-6-luna`) for every agent, so cost and behavior are predictable.
- **Narrow tools:** each tool does one job and returns a compact dict; tool results in the audit trail are clipped to 2,000 characters.

---

## Problem 7: Backend routes

`backend/main.py` (FastAPI). Run from `backend/`: `uvicorn main:app --reload --port 8000` (with the Homework 5 `.venv` active) → `http://localhost:8000`. Interactive docs at `/docs`. CORS allows the React dev server on ports 5173 and 3000.

The backend holds one MCP connection open for its lifetime and reads/writes shop data **only through the campus-customs MCP tools** (two read tools were added for it: `list_tickets` and `list_message_drafts`, bringing the server to 17 tools).

| Method | URL | What it does |
|---|---|---|
| GET | `/api/health` | Liveness check; returns the model (`gpt-6-luna`) and database file in use. |
| GET | `/api/tickets` | All tickets with their DB `status`, a simple `state` (`open` / `resolved`), and `agents_running` (true while the team is working it). |
| GET | `/api/tickets/{ticket_id}` | One ticket with its linked lease/invoice, status-update history, and saved message drafts. |
| POST | `/api/tickets/{ticket_id}/run` | Starts the agent team on that ticket (Boss first) in the background; returns `202` with a `run_id` right away. `404` for an unknown ticket, `409` if agents are already working it. |
| GET | `/api/runs/{run_id}` | Run status (`running` / `done` / `error`), and the Boss's final report, delegation count, and tokens when done. |
| GET | `/api/events?since=&limit=&ticket_id=&run_id=` | Live feed from `audit_trail.json`: each step's agent, depth, event, what it **said**, and the **tools used** (with args). Poll with `since=<next_since>` to get only new events. |
| GET | `/api/approvals` | Everything agents prepared that is waiting on a human: pending payment requests (invoice / rent / purchase order, with PO details) and discount quotes. |
| POST | `/api/approvals/{request_id}/approve` | **The only route that moves cash.** Body `{"approved_by": "<name>"}` (required; sent when a human clicks Approve). Pays via the human-only MCP tool: writes `payments`, debits `cash_accounts`, marks the invoice paid / advances the lease / orders the PO. `409` if cash would go negative or it's already decided. Logged as a `human_approval` audit event. |
| POST | `/api/approvals/{request_id}/reject` | Human rejects a pending request (and any linked PO); no cash moves. Logged as `human_rejection`. |
| GET | `/api/cash` | Current checking balance from `cash_accounts`, its as-of date, the total already queued for approval, and the balance after those. |
| POST | `/api/reset` | Copies the original `campus_customs.db` over `campus_customs_new.db` for a fresh run. `409` while agents are running. The audit trail is kept and marked with a `db_reset` event. |

### Verified (2026-10-12)
- `POST /api/reset` → cash $3,400; all 9 original tables identical to `campus_customs.db`; work tables empty.
- `POST /api/tickets/999/run` → 404. Second `POST /api/tickets/102/run` while running → 409. `POST /api/reset` while running → 409. `/api/tickets` showed `agents_running: true` for 102 during the run.
- Live run via the API on ticket 102 (`run_id 4f839615bfd8`, 3 delegations, 35,030 tokens): Boss → **Facilities only** (the one-owner rule from Problem 5 held), Facilities → Accounting (rent request queued) and Customer Service (landlord draft). `/api/events` streamed the steps as they happened.
- `POST /api/approvals/1/approve` with `approved_by: "Ansit Kaushal"` → cash $3,400 → $1,000, `payments` row with the approver's name, lease `next_due` 2026-09-02 → 2026-10-02. Approving again → 409 "already approved". Blank approver → 422.
- Reset afterwards; DB back to original values.

---

## Problem 8: Agent dashboard ("Pit Wall")

`frontend/` (React 19 + Vite 8 + TypeScript). Run: `cd frontend && npm install && npm run dev` → `http://localhost:5173`. The API base is `http://localhost:8000` (`src/config.ts`, overridable with `VITE_API_BASE`); the backend's CORS allows `http://localhost:5173`.

### Metaphor → feature
| Garage on race day | Dashboard feature | Backend route |
|---|---|---|
| **Pit lane**: cars waiting | Open tickets as car cards (number roundel, livery stripe by ticket type, SKU/size/qty/lease/invoice specs) | `GET /api/tickets` |
| **"Box, box"**: car pulls in | Pick a ticket → Pit box → start the agent team | `POST /api/tickets/{id}/run` |
| **Crew stations** light up | Crew Chief = Boss, Tires = Inventory, Fuel = Accounting, Chassis = Facilities, Radio Comms = Customer Service. Each station shows Standing by / Working (glowing, blinking light) / Done, an **ON RADIO** tag on whoever spoke last, its latest line, the MCP tools it used, turns, and tokens | `GET /api/events?since=&ticket_id=` (polled every 1.2 s while running) |
| **Stopwatch** | Counts up from the run's `started_at`; freezes at `finished_at` | `GET /api/runs` |
| **Team radio** | Chronological log: handoffs with reasons, tool use, refusals, each agent's final summary | `GET /api/events` |
| **Debrief** | One-line summary per agent + Boss's "waiting on you / blockers / next steps" + handoffs and tokens | `run_end` events, `GET /api/runs` |
| **Checkered flag** → **Finished lane** | When a run finishes, a full-screen waving checkered flag, then the car moves to the Finished lane with its pit time and handoff count | run `running → done` in `GET /api/runs`; ticket `resolved` |
| **Fuel gauge** | Checking balance as a needle gauge (full = opening balance); an amber tick marks the balance after pending requests; the needle sweeps down and a "−$840.00" tag drops when a payment is approved | `GET /api/cash` |
| **Crew chief radios for the GO** | Pit wall panel: each pending payment as a radio call (amount, what it's for, why, who prepared it, fuel after) with big **GO · approve** / **NO-GO · deny** buttons. A sign-off name is required. The pit box also shows a red "crew chief is on the radio" banner for that car | `GET /api/approvals`, `POST /api/approvals/{id}/approve` / `reject` |
| **Reset garage** | Restores the original database (disabled while a car is in the pit) | `POST /api/reset` |

### Backend changes for the dashboard
- `POST /api/tickets/{id}/run` now returns the full run record; runs carry `started_at` / `finished_at`; new `GET /api/runs` (dashboard recovers state after a page reload).
- **A ticket is marked `resolved` when its run finishes.** The backend writes a `ticket_updates` note recording what the Boss left it as (e.g. `waiting_on_approval`) and how many payment requests / quotes still await a human, so nothing pending is hidden: those stay on the pit wall.
- `GET /api/cash` adds `opening_balance` (= balance + everything paid out; there is no revenue), so the gauge knows what "full" means. `get_cash_position` (MCP) now returns `paid_out_total`.

### Verified in the browser (2026-10-12)
- Ticket 101 run from the UI: stations lit up live (Crew Chief → Tires → Fuel → Radio Comms; Chassis stayed on standby), stopwatch counted to **47.0 s**, ticket moved to Finished with "Pit time 0:47 · 3 handoffs".
- Pit wall showed request #1: vendor invoice #501, **$840.00**, prepared by Accounting, fuel after $2,560. Clicked **GO** as "Ansit Kaushal" → gauge **$3,400 → $2,560**, "−$840.00" drop tag, call cleared.
- Fixed during testing: the checkered flag was centered inside the tall pit box (off screen) → now a fixed full-screen overlay; the "IN PIT" badge overlapped the car label.
- Layouts checked at 1440 px (3 columns), ~800 px (2 columns), and 375 px (stacked). No console errors; `tsc`, `oxlint`, and `vite build` clean.
- Database reset afterwards (all three tickets open, cash $3,400).

### Problem 8 follow-up: visual polish pass (premium motorsport HUD)
Same routes, same features; purely visual and interaction changes.

| Before (garage theme) | After (motorsport HUD) |
|---|---|
| Warning-tape stripes, metal textures, checkered patterns, multi-color liveries | Graphite surfaces with hairline borders and soft top gradients; **two accents only**: racing red `#ff2d3d` (live / attention) and electric green `#00e08a` (complete / authorized) |
| Italic condensed display type | SF Pro for text, **SF Mono** with tabular numbers for every figure and label (HUD-style uppercase micro-labels) |
| Car cards with number roundels and livery stripes | Race "entries": mono car number, class code (`ORD` / `RNT` / `DSC`), red selection rail, thin sweeping progress line while live |
| Cartoon stopwatch | **Lap ring**: elapsed-time ring that sweeps once per 60 s while running (red), closes to a full green ring with the final time |
| Icon "stations" | **Telemetry cards** per agent: index, name + role, status chip (Standby / Active / Complete), ON AIR chip on the agent speaking, current action, turns · tools · tokens, tool tags; a sweeping top bar while active |
| (none) | **Sector strip** under the header: five segments (Crew Chief → Comms) showing each agent's state at a glance, like F1 timing sectors |
| Illustrated fuel needle | **Radial cash gauge** (270°): green arc = balance vs opening, red segment = amount pending approval, % in center; arc animates down on payment with a small "−$840.00" tag |
| Checkered-flag overlay | **Completion toast**: frosted panel, a check that draws itself, "Ticket N complete · Final mm:ss.s" |
| Loud GO / NO-GO buttons | **Authorizations** card: amount, a balance-impact bar ($3,400 → $2,560), reason, preparer; **press-and-hold Authorize** (1.1 s, fill bar, works with Space/Enter) plus a Decline with an optional reason and confirm step. A quick click does nothing. |

Motion is limited to 200–400 ms ease-out transitions (panel rise, state changes, gauge sweep), all disabled under `prefers-reduced-motion`.

Verified (2026-10-12): `tsc`, `oxlint`, `vite build` clean; no console errors; 1440 px / ~800 px / 375 px layouts (no horizontal overflow). Live-run and authorization states were checked with **browser-only mocked API responses** (no backend or database writes): sector strip and telemetry update while running; a 0.3 s tap on Authorize made no request; a full hold made exactly one approve call, cleared the card, and moved the gauge $3,400 → $2,560 with the delta tag; the completion toast rendered with the final time. Real data afterwards unchanged (cash $3,400, no payments, ticket 103 resolved from the user's own run).
