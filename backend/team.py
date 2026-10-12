"""Run the Campus Customs team on tickets. The Boss gets every ticket first.

    python -m backend.team --ticket 102           # one ticket
    python -m backend.team --all --reset          # reset the DB, then every open ticket
"""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid

from .agents import run_agent
from .mcp_tools import shop_mcp
from .models import TeamDeps, TicketResult
from .reset_db import reset


def new_run_id() -> str:
    return uuid.uuid4().hex[:12]


async def run_ticket(ticket_id: int, run_id: str | None = None) -> TicketResult:
    deps = TeamDeps(run_id=run_id or new_run_id(), ticket_id=ticket_id, agent="boss", chain=["boss"])
    task = (f"Ticket #{ticket_id} is on the board. Read it, route the work to the right teammates, "
            "make the final call, and update the ticket status with a clear note.")
    async with shop_mcp:
        report = await run_agent("boss", task, deps)
    return TicketResult(run_id=deps.run_id, ticket_id=ticket_id, report=report,
                        delegations=deps.budget.delegations, total_tokens=deps.budget.tokens)


async def open_ticket_ids() -> list[int]:
    async with shop_mcp:
        result = await shop_mcp.client.call_tool("list_open_tickets", {})
    return [t["id"] for t in result.structured_content["tickets"]]


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticket", type=int, action="append", help="ticket id (repeatable)")
    ap.add_argument("--all", action="store_true", help="every open ticket")
    ap.add_argument("--reset", action="store_true", help="reset the working DB first")
    args = ap.parse_args()
    if args.reset:
        reset()
    ids = await open_ticket_ids() if args.all else (args.ticket or [])
    for tid in ids:
        result = await run_ticket(tid)
        print(json.dumps(result.model_dump(), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
