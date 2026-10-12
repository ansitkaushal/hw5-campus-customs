# AI Prompts Log — Homework 5: Campus Customs Multi-Agent Operations

## Problem 1: Vibe coder prompts

### Prompt

> Before we start on the actual problems, help me set up `AI_prompts.md`, a log file I need to keep updated throughout this assignment.
> For each problem we work on, add a section with:
>
> * The problem number and title
> * The prompt I give you
> * A follow-up prompt if I need one, plus a sentence on what was missing after my first prompt
>
> create the file now with a header "Problem 1: Vibe coder prompts." and put this text in there. Hope you understand

### Follow-up prompt

None so far.

**What was missing after the first prompt:** N/A

## Problem 2: Study the Campus Customs database

### Prompt

> Now let's work on Problem 2: Study the Campus Customs database.
>
> Open data/campus_customs.db and walk me through every table and its fields. Copy the original file to data/campus_customs_new.db, we'll update that working copy in later problems and keep the original untouched.
>
> Also look at the three open tickets so I can see how they link to the other tables.
>
> Start output/harness.md. For each table, list the fields and one short line on why that table matters for the agents. I'll keep growing this harness file in later problems, so set it up in a way that's easy to add to.

### Follow-up prompt

None so far.

**What was missing after the first prompt:** N/A

## Problem 3: Build the MCP server

### Prompt

> Now let's work on Problem 3: Build the MCP server.
>
> Write an MCP server in mcp_server/ using FastMCP. It should talk to data/campus_customs_new.db. I don't need to connect or run it yet in this problem.
>
> Every agent in this homework will use the tools in this MCP server. We'll add more tools later, but for now write three tools that I know I'll need for the three open tickets in the database. Keep the tool names clear and specific. The tools must never invent data, only pull from what's actually in the database.
>
> Also add a short mcp_server/README.md that explains what the MCP server is for, which database file it uses, and the three tools it has.
>
> In output/harness.md, list each of the three tools. For every tool include: which table it reads, which ticket it helps unlock (101, 102, or 103), and one sentence on why that tool is the right one for that ticket. Be specific, don't just say something vague like "reads inventory," tie it clearly to the ticket it helps resolve.

### Follow-up prompt

None so far.

**What was missing after the first prompt:** N/A

## Problem 4: Add the MCP server to vibe coder and test each tool

### Prompt

> Now let's work on Problem 4: Add the MCP server to vibe coder and test each tool.
> Help me add the MCP server from `mcp_server/` to this project so you can call the tools directly. Save the connection JSON in `.mcp.json` at the project root, or wherever is standard for how you handle local MCP server configs.
> Once it's connected, test each of the three MCP tools and confirm they're working.
> Save the evidence to `output/mcp_smoke.json`. For every tool, include:
>
> * the prompt I asked you to run the tool
> * the tool name
> * the tool output (it needs to match the actual values in `data/campus_customs_new.db`)

### Follow-up prompt

> Use the campus-customs MCP to check invoice 501's vendor status

**What was missing after the first prompt:** The server was registered in `.mcp.json`, but its tools only load when a session starts, so I had to restart the session and approve `campus-customs` before the tools could be called and tested.

## Problem 5: Build the agent team and grow the MCP tools

### Prompt

> Now let's work on Problem 5: Build the agent team and grow the MCP tools.
>
> Build the agentic team for Campus Customs using PydanticAI: Boss, Inventory, Accounting, Facilities, and Customer Service. Include prompts, models, and agent loops so they can all delegate work to each other with full connectivity.
>
> Put the agent prompts in backend/prompts/, one file per agent. Put data types in backend/models.py, and the agent files under backend/. Use my PORTKEY_API_KEY and only gpt-6-luna for every agent, no other models anywhere.
>
> I need you to write the system prompt for each of the five agents (Boss, Inventory, Accounting, Facilities, Customer Service), and I want them to actually feel like job descriptions for someone who works at this shop, not generic AI assistant boilerplate.
> For each agent, write the prompt as if you're onboarding a new employee into that specific role. Include:
>
> * Who they are and what they own: their title, what part of the business is their responsibility, and what "a good day" looks like for them
> * What they must check before acting: the specific shop rules that apply to their role (e.g. Inventory must check vendor unpaid invoices before suggesting a restock; Accounting must never pay without human approval and must refuse if cash would go negative)
> * When they should delegate vs. handle it themselves: concrete examples of the kind of request that belongs to them vs. one they should hand off to another agent
> * Boundaries: what they're explicitly not allowed to do (e.g. Customer Service never actually sends an email, Facilities never approves a payment)
> * Tone: a short note on how they should "sound" when drafting messages or explaining decisions, since these are meant to read like a real team member, not a script
>
> Make each prompt long enough to actually cover the role properly, I'd rather have a thorough, specific prompt than a short one that just repeats "you are the Inventory agent" and leaves out the actual rules. Pull the rules from the shop's database and from what we've already established about the business (vendor lead times, no negative cash balances, human approval for payments, drafts-only for customer comms, etc.).
> Save each one to its own file in `backend/prompts/`
>
> Add any tools the agents need to the MCP server so they can work on the open tickets. All shop facts must come from the MCP server over data/campus_customs_new.db, don't create a second shop-tools layer that bypasses MCP.
>
> Wire the agents so they append to output/audit_trail.json as they run, recording enough per agent-loop step to audit later. Append to the file, don't wipe it on each run.
>
> In output/harness.md, list each agent and each MCP tool (including any new ones added in this problem) along with which table each tool uses. Also add a short safety section covering the guardrails a real business would want when agents touch real customers and real money, plus limits that keep token use in check.
>
> Update mcp_server/README.md so the tool list matches what we have now.

### Follow-up prompt

> Safety
> Guardrails for customers and money
>
> * No agent sends real emails or contacts real vendors. Customer Service only drafts messages; drafts stay on the board for human review.
> * Any payment or purchase order must be approved by a human before it executes. No agent can authorize spend on its own.
> * The pay tool refuses any transaction that would take a cash account negative, there are no overdrafts in this system.
> * Agents never invent data. Prices, stock levels, balances, and dates come only from the MCP server's tools reading `campus_customs_new.db`, never from the model's own assumptions.
> * Vendor restocking rules are enforced in the tools themselves (e.g. a vendor with an open unpaid invoice won't ship), so no agent can bypass that by reasoning around it.
>
> Limits to control token use
>
> * Each agent has a capped number of loop iterations per ticket, so a stuck or confused agent can't spiral into endless back-and-forth delegation.
> * Delegation between agents is logged in the audit trail, including the reason for the handoff, so loops or redundant delegation are easy to spot and fix.
> * All agents use a single fixed model (`gpt-6-luna`) rather than mixing models, keeping cost and behavior predictable across a multi-agent run.
> * Tool calls are scoped narrowly, each tool does one job (e.g. "check inventory for SKU X") rather than open-ended queries, which keeps responses short and avoids unnecessary back-and-forth with the model.
>
> some ideas for safety section

**What was missing after the first prompt:** The first prompt asked for a safety section but didn't say which guardrails and token limits mattered, so the follow-up listed them specifically (drafts-only messages, human approval for all spend, no overdrafts, no invented data, vendor rules enforced in the tools, capped agent loops, logged delegation reasons, one fixed model, narrowly scoped tools).

## Problem 6: Plan the three tickets

### Prompt

> Now let's work on Problem 6: Plan the three tickets.
> Build `output/desk_tickets.html`, a page I can double-click open, with one tab per ticket (101, 102, and 103), plus two empty tabs for later, Cash and Reflection (leave them blank or with a "coming later" note for now).
> For each ticket tab, add an Expected section with my predictions below, and leave room underneath for an Actual section I'll fill in after running the agents.
>
> Ticket 101 (assuming this is a low-stock customer order):
>
> * First call: Boss should call Inventory first, since the core question is whether we can even fulfill the order before anyone drafts a customer response or touches money.
> * Delegations: Inventory checks stock for the SKU/size. If short, Inventory delegates to itself (or flags) which vendor can restock, checking lead time and whether that vendor has an unpaid invoice blocking shipment. Only after stock status is known does Boss loop in Customer Service to draft a message to the customer (e.g. "shipping is delayed" or "item is in stock, confirming order"). Accounting and Facilities should NOT be touched on this ticket, there's no payment or lease issue here.
> * Expected MCP tools: an inventory-lookup tool (by SKU/size), a vendor-lookup tool (lead time, open invoices), and possibly a drafting tool for Customer Service.
>
> Ticket 102 (assuming this is an unpaid vendor invoice / cash issue):
>
> * First call: Boss should call Accounting first, since this is fundamentally a cash and invoice question, not a stock question.
> * Delegations: Accounting checks the invoice amount, due date, and current cash balance. If paying would risk a negative balance, Accounting flags it for human approval and does NOT pay automatically. Accounting may delegate to Inventory only if the invoice is tied to a shipment that's currently blocked, to confirm the business impact of staying unpaid. Facilities and Customer Service should NOT be involved, this is an internal vendor/cash matter.
> * Expected MCP tools: an invoice-lookup tool, a cash-balance-check tool, and a payment tool that refuses if funds are insufficient.
>
> Ticket 103 (assuming this is a customer discount request):
>
> * First call: Boss should call Customer Service first, to understand the nature and tone of the request before deciding if it needs escalation.
> * Delegations: Customer Service drafts a response. If the discount would affect margins meaningfully, Customer Service delegates to Accounting to check margin impact before finalizing the draft. Inventory and Facilities should NOT be involved, there's no stock or lease angle here.
> * Expected MCP tools: a pricing/margin-lookup tool, and a drafting tool for the customer message.
>
> Once the page is built with these predictions, I'll come back and fill in the Actual sections myself after running the agents, so don't do that part yet.

### Follow-up prompt

> Tweak the assumptions to be more around the actual database

**What was missing after the first prompt:** My first predictions assumed ticket types instead of checking the database (102 is a rent notice for lease 1, not a vendor invoice; 101 is blocked by overdue invoice 501; 103 is short 12 hoodies), so the expected routing, agents, and tools didn't match the real tickets or the agent team we built.

## Problem 7: Backend routes

### Prompt

> Now let's work on Problem 7: Backend routes.
> My React frontend dashboard needs a backend it can call. In `backend/main.py`, use FastAPI and add routes that:
>
> * Return the three tickets and whether each is open or resolved
> * Take a ticket id and run the agent team on that ticket
> * Return recent agent events (what each agent said and which tools it used) so the dashboard can refresh with live updates
> * Approve a payment or purchase only after a human clicks approve, agents should only prepare the payment, this route is what actually changes cash
> * Return the current checking balance from `cash_accounts`
> * Reset the database back to the original values so I can try a fresh run whenever I want
>
> Make sure it can run from the `backend/` folder with:
>
> ```
> uvicorn main:app --reload --port 8000
> ```
>
> so the backend is available at `http://localhost:8000` for the frontend to call.
> Help me write the harness entry, List each route in `output/harness.md` :URL and what it does.

### Follow-up prompt

None so far.

**What was missing after the first prompt:** N/A

## Problem 8: Agent dashboard

### Prompt

> Now let's work on Problem 8: Agent dashboard.
> Build the frontend dashboard in `frontend/` with React + Vite + TypeScript. It should call the backend routes from Problem 7. At minimum it needs to:
>
> * List all three tickets
> * Let me pick one ticket and start the agent team on it
> * Show each agent and what they're saying/doing while the ticket runs
> * Mark a ticket resolved when the run finishes
> * Show a short summary of what each agent did
> * Let a human approve a pay or purchase when asked
> * Show the checking balance (it should drop after an approved payment)
>
> I want the whole thing themed like a pit crew garage on race day, not literally, just the feel and metaphor:
>
> * Open tickets are "cars" waiting to come into the pit, shown as cards on a "pit lane" / queue
> * When I pick a ticket, it "pulls into the pit" and I see the crew (the agents) working on it in real time, like separate "stations" lighting up as each agent takes their turn (Inventory = tires, Accounting = fuel, Facilities = chassis, Customer Service = radio comms, Boss = crew chief directing everyone)
> * A live stopwatch/timer counts up while a ticket is being resolved
> * When a ticket resolves, it gets a checkered-flag animation and moves to a "finished" lane
> * The cash balance is shown like a fuel gauge, dropping visibly when a payment is approved
> * When a human needs to approve a payment, show it like a crew chief radioing in for the "go" signal, a clear, obvious approve/deny control
>
> Keep the color palette and typography bold and garage-like (think racing stripes, metal textures, warning-tape yellow/black accents) but still clean and easy to read, this needs to be something a person would actually want to use at a real desk, not just a gimmick.
> Tell the frontend to call the backend at `http://localhost:8000`. On the backend, allow the Vite origin (`http://localhost:5173`) so the browser can call those routes.

### Follow-up prompt

> I don't love how this looks right now, it feels a bit dated and cluttered rather than sleek. Let's keep the pit-crew/racing concept, but execute it in a much more modern, minimal way, think premium motorsport branding (like an F1 team's own app) rather than a literal garage or warning-tape aesthetic.
> Specifically:
>
> * Ditch any literal checkered-flag or hazard-stripe textures, replace with clean geometric accents, subtle gradients, and a refined color palette (deep charcoal/graphite background, one or two sharp accent colors like a racing red or electric green, not a childish rainbow of colors)
> * Typography should feel precise and technical, like a dashboard HUD, not playful or cartoonish
> * Use motion sparingly and smoothly: subtle transitions when a ticket moves between states, a clean animated progress ring or bar instead of a cartoon stopwatch
> * The "stations" for each agent should feel like sleek status cards or panels, not literal pit-stop icons, think more like a live telemetry readout for each agent's current action
> * The fuel-gauge idea for cash is good, but render it as a clean, modern radial or bar gauge, not a literal illustrated fuel needle
> * Keep the "approve payment" moment feeling important and deliberate, like a confirmation on a high-stakes dashboard, but make it elegant rather than loud
>
> The goal is something that feels premium, intuitive, and genuinely fun to use, a human should look at this and think "this is slick," not "this is themed." Keep all the functional requirements from before exactly as they are, this is purely a visual and interaction polish pass.

**What was missing after the first prompt:** The first prompt asked for a literal garage theme (racing stripes, metal textures, warning tape, checkered flag), which came out busy and dated, so the follow-up redirected to a premium, minimal motorsport-HUD style with a restrained palette, technical typography, subtle motion, telemetry-style agent cards, a modern gauge, and an elegant but deliberate approval control.

## Dashboard design write-up (output/design.md)

### Prompt

> Now, write output/design.md with what we chose for the dashboard look (layout, how agents read differently, how resolved tickets and cash show up) and why, including the creative choices that make it feel special and something humans would actually enjoy using.

### Follow-up prompt

None so far.

**What was missing after the first prompt:** N/A

## Problem 9: Resolve the tickets

### Prompt

> Now let's work on Problem 9: Resolve the tickets.
> Before running the agents on all three tickets, reset the working database `data/campus_customs_new.db` so we start clean, and note down the starting checking balance.
> Then run all three tickets (101, 102, 103) through the dashboard until each is resolved.
> Open `output/desk_tickets.html` from Problem 6. On each ticket tab, fill in the Actual section based on this run: which agents worked on it, what they delegated, and which tools they used. Keep the Expected section as-is so I can compare the two.
> On the Cash tab of the same file, itemize the money:
>
> * Starting checking balance (after the reset)
> * For each ticket, how cash changed when it resolved and why (which payment/purchase, dollar amount)
> * Ending checking balance, this needs to match `cash_accounts` in the working database exactly
>
> Also save:
>
> * `output/resolved_tickets.json`: for each ticket, include id, final status, short outcome, what each agent contributed, and any human approvals
> * `output/resolved_board.html`: a page I can double-click open with a screenshot of the dashboard for each resolved ticket (101, 102, 103)
>
> Make sure real runs get appended to `output/audit_trail.json`.
> Finish `output/harness.md` so it fully covers the tables, MCP tools, the five agents, API routes, the dashboard, and safety rules.

### Follow-up prompt

> (Answer to the approval question) Approve invoice + rent (Recommended); approver name: Ansit Kaushal

**What was missing after the first prompt:** It didn't say which payments a human should approve or under what name. That matters because invoice 501 ($840), rent ($2,400), and any restock ($264) total more than the $3,400 in cash, so the approval policy (pay the overdue invoice and rent, decline anything unaffordable) and the approver ("Ansit Kaushal") had to be confirmed before running.

## Problem 10: Reflection

### Prompt

> Now let's work on Problem 10: Reflection.
> Open `output/desk_tickets.html` and help me fill in the Reflection tab. I need to answer these questions myself, in my own words and tied to the specific tickets I ran, not a generic essay, so don't write the answers for me. Instead, help me gather the facts I need from the ticket tabs, Cash tab, and audit trail so I can write thoughtful answers to:
>
> * How would I evaluate the performance of the agents on each ticket, and why?
> * For each ticket, how did the Actual result compare to the Expected plan I wrote earlier?
> * What would have been simpler as one agent with tools instead of five, and why?
> * Three new problems Campus Customs might face that this agent team could solve with the tools I built
> * Three new problems Campus Customs might face that this agent team could NOT solve with the tools I built, and what tools/agents would be needed to solve them
>
> Pull together the relevant details from my Expected vs Actual sections, the Cash tab, and the audit trail so I have everything in front of me to write honest, specific answers.

### Follow-up prompt

> here are the answers
>
> *(followed by my five written answers, which are saved in the Reflection tab of `output/desk_tickets.html`)*

**What was missing after the first prompt:** The first prompt deliberately asked only for the facts, so the answers themselves were still missing; the follow-up supplied my own written answers to be placed into the Reflection tab as written.

> fix those three points in my answers

*(Second follow-up for Problem 10: corrected three factual points in my Reflection answers against the audit trail: no restock PO was actually recommended/drafted for 103; the "blocked" 103 outcome came from my earlier pre-reset run; and 101's differences from my plan came from how the agents worked, not from shared state, while 102's path still matched.)*

## Problem 11: Submit to GitHub

### Prompt

> Now let's finish up with Problem 11: Submit to GitHub.
> Help me push my code to a public GitHub repository so graders can clone it. I'll submit the repo URL to Canvas, and it should also be saved to `output/github_url.txt`.
> Make sure my real `.env` is not pushed to the repo, set up `.gitignore` for that. Both database files under `data/` (the original and my working copy) should be included so graders can run the app easily.
> The expected file layout is: *(hw5/ with AI_prompts.md, requirements.txt, .env.example, .gitignore, .mcp.json, README.md, data/, mcp_server/, frontend/, backend/ with main.py, models.py and prompts/, and output/ with harness.md, mcp_smoke.json, desk_tickets.html, design.md, resolved_tickets.json, resolved_board.html, audit_trail.json, github_url.txt)*
>
> Write `README.md` to explain: how to copy the original DB to the working copy when I need a clean run, how to start the MCP server, how to start the FastAPI backend, how to start the React board, and to reset the DB before doing a full three-ticket run.
> Walk me through organizing everything into this layout, initializing the repo, committing, creating the GitHub repo, and pushing, since I'll need to do the actual GitHub steps myself.

### Follow-up prompt

None so far.

**What was missing after the first prompt:** N/A
