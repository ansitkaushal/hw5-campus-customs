# Campus Customs MCP Server

The shared toolbox for the Campus Customs agent team (Boss, Inventory, Accounting, Facilities, Customer Service). Agents don't query SQLite directly — they call these tools, so every answer comes from the database and nothing is invented. Missing rows return `{"error": ...}`.

## Database

- Reads and writes: `data/campus_customs_new.db` (the working copy, resolved relative to this folder).
- Never touches the original `data/campus_customs.db`.
- "Today" is `desk.date_today`, not the system clock.

## Tools

**Read (facts)**

| Tool | Inputs | Tables | Returns |
|---|---|---|---|
| `list_tickets` | none | tickets, desk | Every ticket with its status (dashboard board) |
| `list_open_tickets` | none | tickets, desk | Every unresolved ticket, oldest first |
| `get_ticket` | `ticket_id` | tickets, leases, invoices, ticket_updates | The ticket, its linked lease/invoice, its update history |
| `check_stock_and_pricing` | `sku`, `size`, `qty_requested` | inventory, pricing | On hand, shortfall, unit cost, list price, margin, break-even discount % |
| `list_vendors_with_status` | none | vendors, invoices, desk | Each vendor's specialty, lead days, earliest arrival, on-hold flag |
| `get_invoice_vendor_status` | `invoice_id` | invoices, vendors, desk | Amount, due date, days overdue, vendor lead time, on-hold flag |
| `get_rent_due_and_cash` | `lease_id` | leases, cash_accounts, desk | Rent, next due, days until due, whether cash covers it |
| `get_cash_position` | none | cash_accounts, invoices, leases, payment_requests | Cash vs. open invoices, rent, and pending requests |
| `list_pending_approvals` | none | payment_requests, purchase_orders, quotes | Everything waiting on a human |
| `list_message_drafts` | `ticket_id` (optional) | message_drafts | Saved drafts (never sent) |

**Draft / request (agents; no money moves, nothing is sent)**

| Tool | Writes | Guard |
|---|---|---|
| `draft_purchase_order` | purchase_orders, payment_requests | Refused if the vendor has an open unpaid invoice |
| `request_payment` | payment_requests | Amount read from the DB; refused if not open, duplicate, or cash can't cover it |
| `propose_bulk_quote` | quotes | Refused if the discounted price is below unit cost |
| `draft_customer_message` | message_drafts | Saved as `draft`; never sent |
| `update_ticket` | tickets, ticket_updates | Status must be one of open / in_progress / waiting_on_approval / blocked / resolved |

**Human only (filtered out of every agent's toolset by the backend)**

| Tool | Effect |
|---|---|
| `approve_payment_request` | Needs a named approver. Refuses if cash would go negative or the item is no longer payable (or the PO vendor is on hold). In one transaction: inserts `payments`, debits `cash_accounts`, marks the invoice paid / advances `leases.next_due` / marks the PO ordered. |
| `reject_payment_request` | Needs a named rejecter; marks the request (and any linked PO) rejected. |

The draft tools create these work tables in the working copy on first use: `payment_requests`, `purchase_orders`, `quotes`, `message_drafts`, `ticket_updates`. Reset with `python -m backend.reset_db`.

## Run

```bash
cd hw5
source .venv/bin/activate
python mcp_server/server.py   # stdio; the backend and Claude Code launch it automatically
```
