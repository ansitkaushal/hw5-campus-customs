# Campus Customs: Multi-Agent Back Office (MGT 409, Homework 5)

An agentic back-office team for **Campus Customs**, a campus merch shop. Tickets (customer orders, rent notices, discount requests) land on a board; five AI agents work them through a shared MCP toolset, and a human watches and approves money in a React dashboard.

| Part | What | Where |
|---|---|---|
| MCP server | 17 FastMCP tools: the only path to shop data | `mcp_server/` |
| Agent team | Boss, Inventory, Accounting, Facilities, Customer Service (PydanticAI, `gpt-6-luna` via Portkey); all can delegate to each other | `backend/agents/`, prompts in `backend/prompts/` |
| Backend | FastAPI routes for the dashboard | `backend/main.py` |
| Dashboard | "Pit Wall" React + Vite + TypeScript board | `frontend/` |
| Data | Original DB (never modified) and working copy | `data/campus_customs.db`, `data/campus_customs_new.db` |
| Results | Harness, smoke tests, ticket plans vs actuals, cash ledger, reflection, audit trail | `output/` |

Full reference (tables, tools, agents, routes, safety rules): **`output/harness.md`**. Design rationale: `output/design.md`.

---

## 1. Setup (once)

Requirements: Python 3.11+ and Node.js 20+.

```bash
git clone <this repo URL> hw5
cd hw5

# Python
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# API key: copy the template and put your own Portkey key in .env (never commit .env)
cp .env.example .env

# Frontend
cd frontend && npm install && cd ..
```

Every model call uses `gpt-6-luna` through Portkey (`https://api.portkey.ai/v1`, header `x-portkey-provider: openai`) with the key from `.env` (`PORTKEY_API_KEY`).

## 2. Clean database (copy the original to the working copy)

`data/campus_customs.db` is the original and is never written. Everything (agents, tools, backend) uses **`data/campus_customs_new.db`**. The working copy in this repo is the end state of my graded run (cash $160). To start clean, copy the original over it:

```bash
cp data/campus_customs.db data/campus_customs_new.db
```

Equivalent ways to do the same reset:

```bash
python -m backend.reset_db                     # from hw5/, with .venv active
curl -X POST http://localhost:8000/api/reset   # while the backend is running
```

…or click **Reset** in the dashboard.

## 3. Start the MCP server

The backend starts the MCP server automatically (stdio) when it boots, so for normal use you can skip this step. To run it on its own:

```bash
source .venv/bin/activate
python mcp_server/server.py
```

To give Claude Code the tools directly, open `hw5/` as the project: `.mcp.json` registers the `campus-customs` server (it expects `.venv` from step 1). Tool list: `mcp_server/README.md`.

## 4. Start the FastAPI backend

```bash
cd backend
source ../.venv/bin/activate
uvicorn main:app --reload --port 8000
```

API at http://localhost:8000 (interactive docs at http://localhost:8000/docs). CORS allows the Vite dev server at http://localhost:5173.

## 5. Start the React board

In a second terminal:

```bash
cd frontend
npm run dev
```

Open http://localhost:5173. The board calls the backend at `http://localhost:8000` (override with `VITE_API_BASE`).

## 6. Full three-ticket run

**Always reset the database first**, so the run starts from the original values ($3,400 cash, invoice 501 open, rent due, all three tickets open):

1. Reset: `cp data/campus_customs.db data/campus_customs_new.db` (or **Reset** in the dashboard).
2. In the dashboard, pick ticket **101** in the pit lane → **Start pit stop**. Watch the agent cards and timeline until the completion toast.
3. If the crew requests a payment, it appears under **Authorizations**. Enter your name and **press and hold Authorize** (or **Decline**). Only this human action moves cash.
4. Repeat for **102** and **103**.

Order matters: paying 101's vendor invoice lifts the vendor hold that 103 depends on. My graded run (101 → 102 → 103, approving the $840 invoice and $2,400 rent) went **$3,400 → $160**; see the Cash tab in `output/desk_tickets.html`.

Headless alternative (no dashboard; payment requests are left pending for a human):

```bash
python -m backend.team --all --reset
```

## Safety rules (summary)

- Agents never send email or contact vendors: Customer Service only saves **drafts**.
- Every payment or purchase needs a **named human**: agents can only queue requests; the approve/reject tools are hidden from all agents.
- The pay tool **refuses** anything that would make the balance negative; a payment updates `payments`, `cash_accounts`, and the invoice / lease / PO together.
- A vendor with an open unpaid invoice won't ship: enforced inside the tools.
- "Today" is `desk.date_today`; lead times come from `vendors`; agents only state facts returned by MCP tools.
- Per-agent and per-ticket loop/token caps; every step and handoff is appended to `output/audit_trail.json`.

## Outputs

| File | Contents |
|---|---|
| `output/harness.md` | Final reference: tables, MCP tools, agents, API routes, dashboard, safety; plus the build log |
| `output/mcp_smoke.json` | Evidence that each MCP tool works when called through Claude Code |
| `output/desk_tickets.html` | Per ticket Expected vs Actual, the Cash ledger, and the Reflection |
| `output/design.md` | Dashboard design choices and why |
| `output/resolved_tickets.json` | Per ticket: final status, outcome, agent contributions, human approvals |
| `output/resolved_board.html` | Dashboard screenshots of the three resolved tickets (PNGs in `output/screenshots/`) |
| `output/audit_trail.json` | Append-only log of every agent-loop step, handoff, approval, and reset |
| `output/github_url.txt` | This repository's URL |
| `AI_prompts.md` | Every prompt used to build this, with follow-ups |
