"""Data types shared by the Campus Customs agents."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

AgentName = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]

AGENT_TITLES: dict[str, str] = {
    "boss": "Boss",
    "inventory": "Inventory",
    "accounting": "Accounting",
    "facilities": "Facilities",
    "customer_service": "Customer Service",
}


class AgentReport(BaseModel):
    """What every agent hands back at the end of its loop, to the Boss or to the agent that asked."""

    agent: AgentName
    summary: str = Field(description="One or two sentences: the answer or decision.")
    findings: list[str] = Field(default_factory=list,
                                description="Facts from tool results, with the real numbers and dates.")
    actions_taken: list[str] = Field(default_factory=list,
                                     description="Things written to the system (queued request #, draft #, PO #, ticket status).")
    awaiting_human_approval: list[str] = Field(default_factory=list,
                                               description="Payment requests / POs / quotes a human must approve, with amounts.")
    blockers: list[str] = Field(default_factory=list, description="What is stopping progress, if anything.")
    next_steps: list[str] = Field(default_factory=list)


class TicketResult(BaseModel):
    run_id: str
    ticket_id: int | None
    report: AgentReport | None
    error: str | None = None
    delegations: int
    total_tokens: int


@dataclass
class TicketBudget:
    """Shared across every agent working on one ticket, so limits are team-wide."""

    delegations: int = 0
    tokens: int = 0


@dataclass
class TeamDeps:
    """Run context passed to every agent loop (and down through delegations)."""

    run_id: str
    ticket_id: int | None
    agent: AgentName
    depth: int = 0
    chain: list[str] = field(default_factory=list)   # e.g. ["boss", "inventory"]
    budget: TicketBudget = field(default_factory=TicketBudget)


class AuditEvent(BaseModel):
    """One line in output/audit_trail.json: a single step of an agent loop."""

    ts: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))
    run_id: str
    ticket_id: int | None
    agent: AgentName | Literal["human", "system"]
    depth: int = 0
    chain: list[str] = Field(default_factory=list)
    step: int = 0
    event: Literal["run_start", "model_request", "model_response", "delegation",
                   "delegation_refused", "run_end", "error",
                   "human_approval", "human_rejection", "db_reset"]
    model: str | None = None
    text: str | None = None
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    tool_results: list[dict[str, Any]] = Field(default_factory=list)
    usage: dict[str, int] | None = None
    detail: dict[str, Any] | None = None
