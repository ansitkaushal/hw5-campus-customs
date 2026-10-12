"""FastAPI backend for the Campus Customs dashboard.

Run from the backend/ folder:
    uvicorn main:app --reload --port 8000

All shop data goes through the campus-customs MCP server (one shared stdio connection).
Agents only prepare payments; the approve route is the only thing that moves cash, and it
runs only when a human clicks Approve in the dashboard.
"""

from __future__ import annotations

import asyncio
import json
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Allow `uvicorn main:app` from inside backend/ while keeping the package's imports.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, HTTPException, Query  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import RedirectResponse  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from backend import audit  # noqa: E402
from backend.config import AUDIT_TRAIL, DB_WORKING, MODEL_NAME  # noqa: E402
from backend.mcp_tools import shop_mcp  # noqa: E402
from backend.models import AuditEvent  # noqa: E402
from backend.reset_db import reset  # noqa: E402
from backend.team import new_run_id, run_ticket  # noqa: E402

# run_id -> {"ticket_id", "status": running|done|error, "started_at", "finished_at", "result", "error"}
RUNS: dict[str, dict[str, Any]] = {}
_TASKS: set[asyncio.Task] = set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with shop_mcp:          # one MCP server process for the app's lifetime
        yield


app = FastAPI(title="Campus Customs Back Office", version="1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173",
                   "http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


async def mcp_call(tool: str, args: dict | None = None) -> dict:
    result = await shop_mcp.client.call_tool(tool, args or {})
    data = result.structured_content or {}
    if "error" in data:
        raise HTTPException(404, data["error"])
    return data


def _running_ticket_ids() -> set[int]:
    return {r["ticket_id"] for r in RUNS.values() if r["status"] == "running"}


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    """Opening http://localhost:8000 in a browser lands on the interactive API docs."""
    return RedirectResponse("/docs")


@app.get("/api/health")
async def health() -> dict:
    return {"ok": True, "model": MODEL_NAME, "database": DB_WORKING.name}


# ---------------------------------------------------------------------------
# Tickets
# ---------------------------------------------------------------------------

@app.get("/api/tickets")
async def list_tickets() -> dict:
    """Every ticket with its status, plus a simple open/resolved flag for the board."""
    data = await mcp_call("list_tickets")
    running = _running_ticket_ids()
    for t in data["tickets"]:
        t["state"] = "resolved" if t["status"] == "resolved" else "open"
        t["agents_running"] = t["id"] in running
    return data


@app.get("/api/tickets/{ticket_id}")
async def get_ticket(ticket_id: int) -> dict:
    """One ticket with its linked lease/invoice, update history, and message drafts."""
    data = await mcp_call("get_ticket", {"ticket_id": ticket_id})
    data["drafts"] = (await mcp_call("list_message_drafts", {"ticket_id": ticket_id}))["drafts"]
    return data


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


async def _run_in_background(run_id: str, ticket_id: int) -> None:
    try:
        result = await run_ticket(ticket_id, run_id=run_id)
        # The run is finished, so the ticket leaves the pit as resolved. Anything the agents
        # prepared (payment requests, POs, quotes, drafts) stays in the approval queue.
        boss_status = (await mcp_call("get_ticket", {"ticket_id": ticket_id}))["ticket"]["status"]
        pending = await mcp_call("list_pending_approvals")
        n_pending = len([r for r in pending["payment_requests"] if r["ticket_id"] == ticket_id])
        n_quotes = len([q for q in pending["quotes"] if q["ticket_id"] == ticket_id])
        summary = result.report.summary if result.report else "no report"
        await mcp_call("update_ticket", {
            "ticket_id": ticket_id, "status": "resolved", "updated_by": "Dashboard",
            "note": (f"Agent run {run_id} finished (Boss left it as '{boss_status}'). "
                     f"{n_pending} payment request(s) and {n_quotes} quote(s) await a human. "
                     f"Boss summary: {summary}"),
        })
        RUNS[run_id].update(status="done", finished_at=_now(), result=result.model_dump(),
                            boss_status=boss_status)
    except Exception as exc:  # surfaced to the dashboard via GET /api/runs/{run_id}
        RUNS[run_id].update(status="error", finished_at=_now(), error=str(exc))


@app.post("/api/tickets/{ticket_id}/run", status_code=202)
async def run_ticket_route(ticket_id: int) -> dict:
    """Start the agent team on one ticket (Boss first). Returns immediately with a run_id;
    poll /api/events and /api/runs/{run_id} for progress."""
    await mcp_call("get_ticket", {"ticket_id": ticket_id})        # 404 if unknown
    if ticket_id in _running_ticket_ids():
        raise HTTPException(409, f"Agents are already working on ticket {ticket_id}")
    run_id = new_run_id()
    RUNS[run_id] = {"run_id": run_id, "ticket_id": ticket_id, "status": "running",
                    "started_at": _now(), "finished_at": None, "result": None, "error": None}
    task = asyncio.create_task(_run_in_background(run_id, ticket_id))
    _TASKS.add(task)
    task.add_done_callback(_TASKS.discard)
    return RUNS[run_id]


@app.get("/api/runs")
async def list_runs() -> dict:
    """Every run since the backend started (newest first), so the dashboard can recover after a reload."""
    return {"runs": sorted(RUNS.values(), key=lambda r: r["started_at"], reverse=True)}


@app.get("/api/runs/{run_id}")
async def get_run(run_id: str) -> dict:
    """Status of one team run (running / done / error) and the Boss's final report when done."""
    if run_id not in RUNS:
        raise HTTPException(404, f"Unknown run {run_id}")
    return RUNS[run_id]


# ---------------------------------------------------------------------------
# Agent events (live feed)
# ---------------------------------------------------------------------------

@app.get("/api/events")
async def events(
    since: int = Query(0, ge=0, description="Return events after this index (use next_since)"),
    limit: int = Query(200, ge=1, le=1000),
    ticket_id: int | None = None,
    run_id: str | None = None,
) -> dict:
    """Recent audit-trail events: what each agent said and which tools it called.
    Poll with ?since=<next_since> to get only new events."""
    all_events = json.loads(AUDIT_TRAIL.read_text()) if AUDIT_TRAIL.exists() else []
    out = []
    for i, e in enumerate(all_events[since:], start=since):
        if ticket_id is not None and e.get("ticket_id") != ticket_id:
            continue
        if run_id is not None and e.get("run_id") != run_id:
            continue
        detail = e.get("detail") or {}
        said = (e.get("text")
                or (detail.get("report") or {}).get("summary")              # run_end
                or (detail.get("task") and f"→ {detail['to']}: {detail['task']}"))  # delegation
        out.append({
            "index": i,
            "ts": e.get("ts"),
            "run_id": e.get("run_id"),
            "ticket_id": e.get("ticket_id"),
            "agent": e.get("agent"),
            "depth": e.get("depth", 0),
            "event": e.get("event"),
            "said": said,
            "tools_used": [c["tool"] for c in e.get("tool_calls", [])],
            "tool_calls": e.get("tool_calls", []),
            "detail": e.get("detail"),
            "usage": e.get("usage"),
        })
    return {"events": out[-limit:], "next_since": len(all_events), "total": len(all_events)}


# ---------------------------------------------------------------------------
# Approvals — the only routes that move money, and only on a human click
# ---------------------------------------------------------------------------

class Decision(BaseModel):
    approved_by: str = Field(..., min_length=1, description="Name of the human clicking the button")
    note: str = ""


@app.get("/api/approvals")
async def approvals() -> dict:
    """Everything agents prepared that is waiting on a human: payment requests (invoice, rent,
    purchase order) and discount quotes."""
    return await mcp_call("list_pending_approvals")


@app.post("/api/approvals/{request_id}/approve")
async def approve(request_id: int, body: Decision) -> dict:
    """Human approves a payment request or purchase order. Executes it: writes payments,
    debits cash_accounts, updates the invoice / lease / PO. Refused (409) if cash would go
    negative or the item is no longer payable."""
    result = await mcp_call("approve_payment_request",
                            {"request_id": request_id, "approved_by": body.approved_by})
    audit.append(AuditEvent(run_id="human", ticket_id=None, agent="human", event="human_approval",
                            detail={"request_id": request_id, "approved_by": body.approved_by,
                                    "result": result}))
    if not result.get("paid"):
        raise HTTPException(409, result.get("reason", "Payment refused"))
    return result


@app.post("/api/approvals/{request_id}/reject")
async def reject(request_id: int, body: Decision) -> dict:
    """Human rejects a pending payment request (and any linked purchase order). No cash moves."""
    result = await mcp_call("reject_payment_request",
                            {"request_id": request_id, "rejected_by": body.approved_by,
                             "note": body.note})
    audit.append(AuditEvent(run_id="human", ticket_id=None, agent="human", event="human_rejection",
                            detail={"request_id": request_id, "rejected_by": body.approved_by,
                                    "note": body.note, "result": result}))
    if not result.get("rejected"):
        raise HTTPException(409, result.get("reason", "Rejection refused"))
    return result


# ---------------------------------------------------------------------------
# Cash and reset
# ---------------------------------------------------------------------------

@app.get("/api/cash")
async def cash() -> dict:
    """Current checking balance from cash_accounts, plus what's already queued against it."""
    data = await mcp_call("get_cash_position")
    checking = next((a for a in data["cash_accounts"] if a["name"] == "checking"), None)
    if checking is None:
        raise HTTPException(404, "No checking account")
    return {
        "today": data["today"],
        "account": "checking",
        # No revenue is modeled, so opening balance = current balance + everything paid out.
        "opening_balance": round(checking["balance"] + data["paid_out_total"], 2),
        "balance": checking["balance"],
        "as_of": checking["date"],
        "pending_requests_total": data["pending_requests_total"],
        "balance_after_pending": data["cash_after_pending_requests"],
    }


@app.post("/api/reset")
async def reset_route() -> dict:
    """Copy the original database over the working copy (fresh run). Refused while agents are
    running. The audit trail is kept (append-only); a db_reset event marks the boundary."""
    if _running_ticket_ids():
        raise HTTPException(409, "Agents are running; wait for them to finish before resetting")
    reset()
    audit.append(AuditEvent(run_id="system", ticket_id=None, agent="system", event="db_reset",
                            detail={"database": DB_WORKING.name}))
    return {"reset": True, "database": DB_WORKING.name, "cash": await cash()}
