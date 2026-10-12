"""Campus Customs MCP server — the only way the agent team touches shop data.

Read tools (facts):
    list_tickets               every ticket with its status (dashboard)
    list_open_tickets          every ticket that is not resolved
    get_ticket                 one ticket plus its linked lease / invoice rows
    check_stock_and_pricing    stock on hand, shortfall, cost, list price for a SKU + size
    list_vendors_with_status   every vendor, lead time, earliest arrival, and on-hold flag
    get_invoice_vendor_status  invoice status, days overdue, and whether the vendor is on hold
    get_rent_due_and_cash      rent amount, days until due, and whether cash covers it
    get_cash_position          cash, open invoices, upcoming rent, and pending approvals
    list_pending_approvals     payment requests, purchase orders, and quotes awaiting a human
    list_message_drafts        saved message drafts (never sent)

Draft / request tools (agents; nothing leaves the building, no money moves):
    draft_purchase_order       draft a restock PO; refused if the vendor has an open invoice
    request_payment            queue an invoice / rent payment for human approval
    propose_bulk_quote         queue a discount quote; refused below unit cost
    draft_customer_message     save a customer message as a draft (never sent)
    update_ticket              change a ticket's status and append a note

Human-only tools (the backend filters these out of every agent's toolset):
    approve_payment_request    a named human approves; cash is checked and every table updated
    reject_payment_request     a named human rejects a pending request

All tools use data/campus_customs_new.db (the working copy). Facts are only values in
the database plus arithmetic on them; a missing row returns {"error": ...}. "Today" is
always desk.date_today, never the system clock. Amounts are always read from the
database, never accepted from the caller.

Run standalone (stdio):  python mcp_server/server.py
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import date
from typing import Literal
from pathlib import Path

from fastmcp import FastMCP

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "campus_customs_new.db"

mcp = FastMCP("campus-customs")


def _connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Working database not found: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(_WORK_TABLES)
    return conn


# Work tables the agents write to. Created on demand so a reset (copying the original
# database over the working copy) needs no extra step. The original schema is untouched.
_WORK_TABLES = """
CREATE TABLE IF NOT EXISTS payment_requests (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,              -- invoice | rent | purchase_order
    ref_id INTEGER NOT NULL,         -- invoices.id | leases.id | purchase_orders.id
    amount REAL NOT NULL,
    account TEXT NOT NULL,
    ticket_id INTEGER,
    requested_by TEXT NOT NULL,
    reason TEXT,
    status TEXT NOT NULL,            -- pending | approved | rejected
    created_at TEXT NOT NULL,
    decided_by TEXT,
    decided_at TEXT,
    decision_note TEXT
);
CREATE TABLE IF NOT EXISTS purchase_orders (
    id INTEGER PRIMARY KEY,
    vendor_id INTEGER NOT NULL,
    sku TEXT NOT NULL,
    size TEXT NOT NULL,
    qty INTEGER NOT NULL,
    unit_cost REAL NOT NULL,
    total REAL NOT NULL,
    ticket_id INTEGER,
    status TEXT NOT NULL,            -- pending_approval | ordered | rejected
    expected_arrival TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS quotes (
    id INTEGER PRIMARY KEY,
    ticket_id INTEGER,
    sku TEXT NOT NULL,
    size TEXT NOT NULL,
    qty INTEGER NOT NULL,
    list_price REAL NOT NULL,
    discount_pct REAL NOT NULL,
    unit_price REAL NOT NULL,
    total REAL NOT NULL,
    unit_margin REAL NOT NULL,
    proposed_by TEXT NOT NULL,
    rationale TEXT,
    status TEXT NOT NULL,            -- pending_human_review
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS message_drafts (
    id INTEGER PRIMARY KEY,
    ticket_id INTEGER,
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    drafted_by TEXT NOT NULL,
    status TEXT NOT NULL,            -- draft (never sent by the system)
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ticket_updates (
    id INTEGER PRIMARY KEY,
    ticket_id INTEGER NOT NULL,
    old_status TEXT,
    new_status TEXT NOT NULL,
    note TEXT,
    updated_by TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

TICKET_STATUSES = ("open", "in_progress", "waiting_on_approval", "blocked", "resolved")


def _today(conn: sqlite3.Connection) -> date:
    row = conn.execute("SELECT date_today FROM desk LIMIT 1").fetchone()
    return date.fromisoformat(row["date_today"])


@mcp.tool
def check_stock_and_pricing(sku: str, size: str, qty_requested: int) -> dict:
    """Check whether a SKU in a given size can fill an order, and what it costs vs. sells for.

    Returns units on hand, the shortfall against qty_requested, unit cost, list price,
    per-unit margin, and the break-even discount (the deepest % off list that still
    covers unit cost). Use for customer orders and bulk discount requests.
    """
    with closing(_connect()) as conn:
        stock = conn.execute(
            "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ? AND size = ?",
            (sku, size),
        ).fetchone()
        if stock is None:
            return {"error": f"No inventory row for sku={sku!r} size={size!r}"}
        price = conn.execute(
            "SELECT unit_cost, list_price FROM pricing WHERE sku = ?", (sku,)
        ).fetchone()
        if price is None:
            return {"error": f"No pricing row for sku={sku!r}"}

    on_hand = stock["qty"]
    unit_cost, list_price = price["unit_cost"], price["list_price"]
    return {
        "sku": stock["sku"],
        "name": stock["name"],
        "size": stock["size"],
        "location": stock["location"],
        "qty_on_hand": on_hand,
        "qty_requested": qty_requested,
        "can_fill_from_stock": on_hand >= qty_requested,
        "shortfall": max(qty_requested - on_hand, 0),
        "unit_cost": unit_cost,
        "list_price": list_price,
        "unit_margin": round(list_price - unit_cost, 2),
        "break_even_discount_pct": round((1 - unit_cost / list_price) * 100, 1),
    }


@mcp.tool
def get_invoice_vendor_status(invoice_id: int) -> dict:
    """Look up an invoice and the vendor behind it, as of desk.date_today.

    Returns the amount, due date, status, days overdue, the vendor's specialty and
    lead time, and vendor_on_hold (True while this invoice is open: the vendor will not
    ship new product until it is paid). Also lists every other open invoice for the
    same vendor so nothing blocking them is missed.
    """
    with closing(_connect()) as conn:
        today = _today(conn)
        inv = conn.execute(
            """SELECT i.id, i.amount, i.due_date, i.status, i.description,
                      v.id AS vendor_id, v.name AS vendor_name, v.specialty, v.lead_days
               FROM invoices i JOIN vendors v ON v.id = i.vendor_id
               WHERE i.id = ?""",
            (invoice_id,),
        ).fetchone()
        if inv is None:
            return {"error": f"No invoice with id={invoice_id}"}
        open_for_vendor = conn.execute(
            "SELECT id, amount, due_date FROM invoices WHERE vendor_id = ? AND status = 'open'",
            (inv["vendor_id"],),
        ).fetchall()

    days_overdue = (today - date.fromisoformat(inv["due_date"])).days
    is_open = inv["status"] == "open"
    return {
        "today": today.isoformat(),
        "invoice_id": inv["id"],
        "description": inv["description"],
        "amount": inv["amount"],
        "due_date": inv["due_date"],
        "status": inv["status"],
        "is_overdue": is_open and days_overdue > 0,
        "days_overdue": max(days_overdue, 0) if is_open else 0,
        "vendor_id": inv["vendor_id"],
        "vendor_name": inv["vendor_name"],
        "vendor_specialty": inv["specialty"],
        "vendor_lead_days": inv["lead_days"],
        "vendor_on_hold": len(open_for_vendor) > 0,
        "vendor_open_invoices": [dict(r) for r in open_for_vendor],
    }


@mcp.tool
def get_rent_due_and_cash(lease_id: int) -> dict:
    """Look up a lease's rent and compare it with cash on hand, as of desk.date_today.

    Returns the landlord, monthly rent, next due date, days until due (negative means
    late), each cash account balance, and whether total cash can cover the rent
    without going negative. Read-only: it does not pay anything.
    """
    with closing(_connect()) as conn:
        today = _today(conn)
        lease = conn.execute(
            "SELECT id, space_name, landlord, monthly_rent, next_due, notes FROM leases WHERE id = ?",
            (lease_id,),
        ).fetchone()
        if lease is None:
            return {"error": f"No lease with id={lease_id}"}
        accounts = conn.execute("SELECT name, balance, date FROM cash_accounts").fetchall()

    total_cash = sum(a["balance"] for a in accounts)
    rent = lease["monthly_rent"]
    return {
        "today": today.isoformat(),
        "lease_id": lease["id"],
        "space_name": lease["space_name"],
        "landlord": lease["landlord"],
        "monthly_rent": rent,
        "next_due": lease["next_due"],
        "days_until_due": (date.fromisoformat(lease["next_due"]) - today).days,
        "cash_accounts": [dict(a) for a in accounts],
        "total_cash": total_cash,
        "cash_covers_rent": total_cash >= rent,
        "cash_after_rent": round(total_cash - rent, 2),
    }


def _add_month(d: date) -> date:
    import calendar
    y, m = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def _open_invoices(conn: sqlite3.Connection, vendor_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT id, amount, due_date FROM invoices WHERE vendor_id = ? AND status = 'open'",
        (vendor_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Read tools
# ---------------------------------------------------------------------------

@mcp.tool
def list_open_tickets() -> dict:
    """List every ticket that is not resolved, oldest first, with today's date from desk."""
    with closing(_connect()) as conn:
        today = _today(conn)
        rows = conn.execute(
            "SELECT * FROM tickets WHERE status != 'resolved' ORDER BY created_at"
        ).fetchall()
    return {"today": today.isoformat(), "tickets": [dict(r) for r in rows]}


@mcp.tool
def get_ticket(ticket_id: int) -> dict:
    """Get one ticket with its linked lease and invoice rows (if any) and its update history."""
    with closing(_connect()) as conn:
        today = _today(conn)
        t = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if t is None:
            return {"error": f"No ticket with id={ticket_id}"}
        lease = (
            conn.execute("SELECT * FROM leases WHERE id = ?", (t["lease_id"],)).fetchone()
            if t["lease_id"] is not None else None
        )
        invoice = (
            conn.execute("SELECT * FROM invoices WHERE id = ?", (t["invoice_id"],)).fetchone()
            if t["invoice_id"] is not None else None
        )
        history = conn.execute(
            "SELECT * FROM ticket_updates WHERE ticket_id = ? ORDER BY id", (ticket_id,)
        ).fetchall()
    return {
        "today": today.isoformat(),
        "ticket": dict(t),
        "linked_lease": dict(lease) if lease else None,
        "linked_invoice": dict(invoice) if invoice else None,
        "updates": [dict(h) for h in history],
    }


@mcp.tool
def list_vendors_with_status() -> dict:
    """List every vendor with specialty, lead days, earliest arrival if ordered today,
    and whether they are on hold (any open invoice means they will not ship new product)."""
    with closing(_connect()) as conn:
        today = _today(conn)
        vendors = conn.execute("SELECT * FROM vendors ORDER BY id").fetchall()
        out = []
        for v in vendors:
            open_inv = _open_invoices(conn, v["id"])
            out.append({
                **dict(v),
                "earliest_arrival_if_ordered_today": date.fromordinal(
                    today.toordinal() + v["lead_days"]).isoformat(),
                "on_hold": bool(open_inv),
                "open_invoices": open_inv,
            })
    return {"today": today.isoformat(), "vendors": out}


@mcp.tool
def get_cash_position() -> dict:
    """Summarise cash on hand against what is owed: open invoices, the next rent on every
    lease, and payment requests already pending approval. No revenue is modeled, so cash
    only goes down."""
    with closing(_connect()) as conn:
        today = _today(conn)
        accounts = [dict(a) for a in conn.execute("SELECT * FROM cash_accounts")]
        invoices = [dict(r) for r in conn.execute(
            "SELECT i.*, v.name AS vendor_name FROM invoices i JOIN vendors v ON v.id = i.vendor_id "
            "WHERE i.status = 'open' ORDER BY i.due_date")]
        leases = [dict(r) for r in conn.execute("SELECT * FROM leases ORDER BY next_due")]
        pending = [dict(r) for r in conn.execute(
            "SELECT * FROM payment_requests WHERE status = 'pending' ORDER BY id")]
        paid_out = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM payments").fetchone()[0]
    for inv in invoices:
        inv["days_overdue"] = max((today - date.fromisoformat(inv["due_date"])).days, 0)
    for le in leases:
        le["days_until_due"] = (date.fromisoformat(le["next_due"]) - today).days
    total_cash = sum(a["balance"] for a in accounts)
    pending_total = sum(p["amount"] for p in pending)
    return {
        "today": today.isoformat(),
        "cash_accounts": accounts,
        "total_cash": total_cash,
        "paid_out_total": paid_out,
        "open_invoices": invoices,
        "open_invoices_total": sum(i["amount"] for i in invoices),
        "leases": leases,
        "pending_payment_requests": pending,
        "pending_requests_total": pending_total,
        "cash_after_pending_requests": round(total_cash - pending_total, 2),
    }


@mcp.tool
def list_pending_approvals() -> dict:
    """List everything waiting on a human: pending payment requests (with any linked
    purchase order) and discount quotes awaiting review."""
    with closing(_connect()) as conn:
        reqs = [dict(r) for r in conn.execute(
            "SELECT * FROM payment_requests WHERE status = 'pending' ORDER BY id")]
        for r in reqs:
            if r["kind"] == "purchase_order":
                po = conn.execute("SELECT * FROM purchase_orders WHERE id = ?", (r["ref_id"],)).fetchone()
                r["purchase_order"] = dict(po) if po else None
        quotes = [dict(q) for q in conn.execute(
            "SELECT * FROM quotes WHERE status = 'pending_human_review' ORDER BY id")]
    return {"payment_requests": reqs, "quotes": quotes}


@mcp.tool
def list_tickets() -> dict:
    """List every ticket (open and resolved) with its status, oldest first."""
    with closing(_connect()) as conn:
        today = _today(conn)
        rows = conn.execute("SELECT * FROM tickets ORDER BY created_at").fetchall()
    return {"today": today.isoformat(), "tickets": [dict(r) for r in rows]}


@mcp.tool
def list_message_drafts(ticket_id: int | None = None) -> dict:
    """List saved message drafts (never sent), optionally for one ticket."""
    with closing(_connect()) as conn:
        if ticket_id is None:
            rows = conn.execute("SELECT * FROM message_drafts ORDER BY id").fetchall()
        else:
            rows = conn.execute("SELECT * FROM message_drafts WHERE ticket_id = ? ORDER BY id",
                                (ticket_id,)).fetchall()
    return {"drafts": [dict(r) for r in rows]}


# ---------------------------------------------------------------------------
# Draft / request tools — agents may call these; no money moves, nothing is sent
# ---------------------------------------------------------------------------

@mcp.tool
def draft_purchase_order(vendor_id: int, sku: str, size: str, qty: int,
                         created_by: str, ticket_id: int | None = None) -> dict:
    """Draft a restock purchase order and queue its payment for human approval.

    Refused if the vendor has any open invoice (they will not ship), or if the SKU/size
    is unknown. Cost = qty x pricing.unit_cost; arrival = desk.date_today + vendor lead_days.
    Nothing is sent to the vendor."""
    if qty <= 0:
        return {"created": False, "reason": "qty must be positive"}
    with closing(_connect()) as conn:
        today = _today(conn)
        v = conn.execute("SELECT * FROM vendors WHERE id = ?", (vendor_id,)).fetchone()
        if v is None:
            return {"error": f"No vendor with id={vendor_id}"}
        if conn.execute("SELECT 1 FROM inventory WHERE sku = ? AND size = ?", (sku, size)).fetchone() is None:
            return {"error": f"No inventory row for sku={sku!r} size={size!r}"}
        price = conn.execute("SELECT unit_cost FROM pricing WHERE sku = ?", (sku,)).fetchone()
        if price is None:
            return {"error": f"No pricing row for sku={sku!r}"}
        open_inv = _open_invoices(conn, vendor_id)
        if open_inv:
            return {
                "created": False,
                "reason": f"{v['name']} is on hold: open unpaid invoice(s) {[i['id'] for i in open_inv]}. "
                          "They will not ship until paid.",
                "vendor_open_invoices": open_inv,
            }
        total = round(qty * price["unit_cost"], 2)
        arrival = date.fromordinal(today.toordinal() + v["lead_days"]).isoformat()
        with conn:
            po_id = conn.execute(
                "INSERT INTO purchase_orders (vendor_id, sku, size, qty, unit_cost, total, ticket_id, "
                "status, expected_arrival, created_by, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (vendor_id, sku, size, qty, price["unit_cost"], total, ticket_id,
                 "pending_approval", arrival, created_by, today.isoformat()),
            ).lastrowid
            req_id = conn.execute(
                "INSERT INTO payment_requests (kind, ref_id, amount, account, ticket_id, requested_by, "
                "reason, status, created_at) VALUES ('purchase_order',?,?,'checking',?,?,?,'pending',?)",
                (po_id, total, ticket_id, created_by,
                 f"Restock {qty} x {sku} {size} from {v['name']}", today.isoformat()),
            ).lastrowid
    return {
        "created": True, "purchase_order_id": po_id, "payment_request_id": req_id,
        "vendor": v["name"], "total": total, "expected_arrival_if_approved_today": arrival,
        "status": "pending_approval",
    }


@mcp.tool
def request_payment(kind: Literal["invoice", "rent"], ref_id: int, requested_by: str,
                    reason: str, ticket_id: int | None = None) -> dict:
    """Queue an invoice or rent payment for human approval. Does NOT pay anything.

    The amount is read from the database (invoices.amount or leases.monthly_rent). Refused
    if the invoice is not open, a request for the same item is already pending, or cash
    could not cover it."""
    with closing(_connect()) as conn:
        today = _today(conn)
        if kind == "invoice":
            row = conn.execute("SELECT amount, status FROM invoices WHERE id = ?", (ref_id,)).fetchone()
            if row is None:
                return {"error": f"No invoice with id={ref_id}"}
            if row["status"] != "open":
                return {"created": False, "reason": f"Invoice {ref_id} is already {row['status']}"}
            amount = row["amount"]
        else:
            row = conn.execute("SELECT monthly_rent FROM leases WHERE id = ?", (ref_id,)).fetchone()
            if row is None:
                return {"error": f"No lease with id={ref_id}"}
            amount = row["monthly_rent"]
        dup = conn.execute(
            "SELECT id FROM payment_requests WHERE kind = ? AND ref_id = ? AND status = 'pending'",
            (kind, ref_id),
        ).fetchone()
        if dup:
            return {"created": False, "reason": f"Already pending as payment request {dup['id']}"}
        cash = conn.execute("SELECT balance FROM cash_accounts WHERE name = 'checking'").fetchone()
        if cash is None or cash["balance"] < amount:
            return {"created": False,
                    "reason": f"Insufficient cash: need {amount}, have {cash['balance'] if cash else 0}"}
        with conn:
            req_id = conn.execute(
                "INSERT INTO payment_requests (kind, ref_id, amount, account, ticket_id, requested_by, "
                "reason, status, created_at) VALUES (?,?,?,'checking',?,?,?,'pending',?)",
                (kind, ref_id, amount, ticket_id, requested_by, reason, today.isoformat()),
            ).lastrowid
    return {"created": True, "payment_request_id": req_id, "kind": kind, "ref_id": ref_id,
            "amount": amount, "status": "pending", "cash_now": cash["balance"],
            "cash_after_if_approved": round(cash["balance"] - amount, 2)}


@mcp.tool
def propose_bulk_quote(sku: str, size: str, qty: int, discount_pct: float,
                       proposed_by: str, rationale: str, ticket_id: int | None = None) -> dict:
    """Queue a discounted quote for human review. Refused if the discounted unit price
    would fall below pricing.unit_cost. Nothing is sent to the customer."""
    if not 0 <= discount_pct < 100 or qty <= 0:
        return {"created": False, "reason": "discount_pct must be in [0, 100) and qty positive"}
    with closing(_connect()) as conn:
        today = _today(conn)
        p = conn.execute("SELECT unit_cost, list_price FROM pricing WHERE sku = ?", (sku,)).fetchone()
        if p is None:
            return {"error": f"No pricing row for sku={sku!r}"}
        unit_price = round(p["list_price"] * (1 - discount_pct / 100), 2)
        margin = round(unit_price - p["unit_cost"], 2)
        if margin < 0:
            return {"created": False,
                    "reason": f"{discount_pct}% off puts unit price {unit_price} below unit cost {p['unit_cost']}"}
        total = round(unit_price * qty, 2)
        with conn:
            qid = conn.execute(
                "INSERT INTO quotes (ticket_id, sku, size, qty, list_price, discount_pct, unit_price, total, "
                "unit_margin, proposed_by, rationale, status, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,'pending_human_review',?)",
                (ticket_id, sku, size, qty, p["list_price"], discount_pct, unit_price, total,
                 margin, proposed_by, rationale, today.isoformat()),
            ).lastrowid
    return {"created": True, "quote_id": qid, "unit_price": unit_price, "total": total,
            "unit_margin": margin, "total_margin": round(margin * qty, 2),
            "status": "pending_human_review"}


@mcp.tool
def draft_customer_message(recipient: str, subject: str, body: str, drafted_by: str,
                           ticket_id: int | None = None) -> dict:
    """Save a customer or vendor message as a draft for human review. It is NEVER sent."""
    with closing(_connect()) as conn:
        today = _today(conn)
        with conn:
            did = conn.execute(
                "INSERT INTO message_drafts (ticket_id, recipient, subject, body, drafted_by, status, "
                "created_at) VALUES (?,?,?,?,?,'draft',?)",
                (ticket_id, recipient, subject, body, drafted_by, today.isoformat()),
            ).lastrowid
    return {"saved": True, "draft_id": did, "status": "draft", "sent": False}


@mcp.tool
def update_ticket(ticket_id: int,
                  status: Literal["open", "in_progress", "waiting_on_approval", "blocked", "resolved"],
                  note: str, updated_by: str) -> dict:
    """Set a ticket's status and record a dated note in ticket_updates."""
    with closing(_connect()) as conn:
        today = _today(conn)
        t = conn.execute("SELECT status FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if t is None:
            return {"error": f"No ticket with id={ticket_id}"}
        with conn:
            conn.execute("UPDATE tickets SET status = ? WHERE id = ?", (status, ticket_id))
            conn.execute(
                "INSERT INTO ticket_updates (ticket_id, old_status, new_status, note, updated_by, "
                "created_at) VALUES (?,?,?,?,?,?)",
                (ticket_id, t["status"], status, note, updated_by, today.isoformat()),
            )
    return {"ticket_id": ticket_id, "old_status": t["status"], "new_status": status}


# ---------------------------------------------------------------------------
# Human-only tools — filtered out of every agent's toolset by the backend
# ---------------------------------------------------------------------------

@mcp.tool
def approve_payment_request(request_id: int, approved_by: str) -> dict:
    """HUMAN ONLY. Approve a pending payment request and execute it in one transaction.

    Refuses if the request is not pending, approved_by is blank, the item is no longer
    payable, or the account would go negative. On success it writes a payments row,
    debits cash_accounts, and updates the source: invoices.status='paid', leases.next_due
    advanced one month, or purchase_orders.status='ordered'."""
    if not approved_by.strip():
        return {"paid": False, "reason": "approved_by (a human name) is required"}
    with closing(_connect()) as conn:
        today = _today(conn)
        r = conn.execute("SELECT * FROM payment_requests WHERE id = ?", (request_id,)).fetchone()
        if r is None:
            return {"error": f"No payment request with id={request_id}"}
        if r["status"] != "pending":
            return {"paid": False, "reason": f"Request {request_id} is already {r['status']}"}
        cash = conn.execute("SELECT balance FROM cash_accounts WHERE name = ?", (r["account"],)).fetchone()
        if cash is None:
            return {"error": f"No cash account {r['account']!r}"}
        amount = r["amount"]
        if cash["balance"] - amount < 0:
            return {"paid": False,
                    "reason": f"Refused: {r['account']} has {cash['balance']}, payment is {amount}; "
                              "no negative balances allowed"}
        if r["kind"] == "invoice":
            inv = conn.execute("SELECT status FROM invoices WHERE id = ?", (r["ref_id"],)).fetchone()
            if inv is None or inv["status"] != "open":
                return {"paid": False, "reason": f"Invoice {r['ref_id']} is not open"}
        elif r["kind"] == "purchase_order":
            po = conn.execute("SELECT * FROM purchase_orders WHERE id = ?", (r["ref_id"],)).fetchone()
            if po is None or po["status"] != "pending_approval":
                return {"paid": False, "reason": f"Purchase order {r['ref_id']} is not pending"}
            if _open_invoices(conn, po["vendor_id"]):
                return {"paid": False, "reason": "Vendor still has an open invoice; they will not ship"}
        with conn:
            if r["kind"] == "invoice":
                conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (r["ref_id"],))
                effect = {"invoice_id": r["ref_id"], "invoice_status": "paid"}
            elif r["kind"] == "rent":
                le = conn.execute("SELECT next_due FROM leases WHERE id = ?", (r["ref_id"],)).fetchone()
                nxt = _add_month(date.fromisoformat(le["next_due"])).isoformat()
                conn.execute("UPDATE leases SET next_due = ? WHERE id = ?", (nxt, r["ref_id"]))
                effect = {"lease_id": r["ref_id"], "rent_paid_for": le["next_due"], "next_due": nxt}
            else:
                arrival = date.fromordinal(today.toordinal() + conn.execute(
                    "SELECT lead_days FROM vendors WHERE id = ?", (po["vendor_id"],)).fetchone()[0]).isoformat()
                conn.execute("UPDATE purchase_orders SET status = 'ordered', expected_arrival = ? WHERE id = ?",
                             (arrival, r["ref_id"]))
                effect = {"purchase_order_id": r["ref_id"], "po_status": "ordered", "expected_arrival": arrival}
            new_balance = round(cash["balance"] - amount, 2)
            conn.execute("UPDATE cash_accounts SET balance = ?, date = ? WHERE name = ?",
                         (new_balance, today.isoformat(), r["account"]))
            pay_id = conn.execute(
                "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) VALUES (?,?,?,?,?,?)",
                (r["kind"], r["ref_id"], amount, r["account"], today.isoformat(), approved_by.strip()),
            ).lastrowid
            conn.execute(
                "UPDATE payment_requests SET status = 'approved', decided_by = ?, decided_at = ? WHERE id = ?",
                (approved_by.strip(), today.isoformat(), request_id),
            )
    return {"paid": True, "payment_id": pay_id, "amount": amount, "account": r["account"],
            "balance_before": cash["balance"], "balance_after": new_balance, **effect}


@mcp.tool
def reject_payment_request(request_id: int, rejected_by: str, note: str) -> dict:
    """HUMAN ONLY. Reject a pending payment request; any linked purchase order is rejected too."""
    if not rejected_by.strip():
        return {"rejected": False, "reason": "rejected_by (a human name) is required"}
    with closing(_connect()) as conn:
        today = _today(conn)
        r = conn.execute("SELECT * FROM payment_requests WHERE id = ?", (request_id,)).fetchone()
        if r is None:
            return {"error": f"No payment request with id={request_id}"}
        if r["status"] != "pending":
            return {"rejected": False, "reason": f"Request {request_id} is already {r['status']}"}
        with conn:
            conn.execute(
                "UPDATE payment_requests SET status = 'rejected', decided_by = ?, decided_at = ?, "
                "decision_note = ? WHERE id = ?",
                (rejected_by.strip(), today.isoformat(), note, request_id),
            )
            if r["kind"] == "purchase_order":
                conn.execute("UPDATE purchase_orders SET status = 'rejected' WHERE id = ?", (r["ref_id"],))
    return {"rejected": True, "request_id": request_id}


if __name__ == "__main__":
    mcp.run(show_banner=False)
