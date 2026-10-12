"""Shared agent factory, the delegation tool, and the audited agent loop."""

from __future__ import annotations

import json
from typing import Any

from pydantic_ai import Agent, RunContext
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.messages import RetryPromptPart, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.usage import UsageLimits

from .. import audit
from ..config import (
    AUDIT_TEXT_LIMIT, MAX_DELEGATION_DEPTH, MAX_DELEGATIONS_PER_TICKET,
    MAX_REQUESTS_PER_AGENT_RUN, MAX_TOKENS_PER_AGENT_RUN, MAX_TOKENS_PER_TICKET,
    MODEL_NAME, PROMPTS_DIR, build_model,
)
from ..mcp_tools import toolset_for
from ..models import AGENT_TITLES, AgentName, AgentReport, AuditEvent, TeamDeps

_MODEL = build_model()
REGISTRY: dict[str, Agent[TeamDeps, AgentReport]] = {}


def _clip(value: Any) -> Any:
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    return text if len(text) <= AUDIT_TEXT_LIMIT else text[:AUDIT_TEXT_LIMIT] + "...[truncated]"


def _log(deps: TeamDeps, step: int, event: str, **kw: Any) -> None:
    audit.append(AuditEvent(
        run_id=deps.run_id, ticket_id=deps.ticket_id, agent=deps.agent, depth=deps.depth,
        chain=deps.chain, step=step, event=event, model=MODEL_NAME, **kw,
    ))


def _runtime_context(ctx: RunContext[TeamDeps]) -> str:
    d = ctx.deps
    asked_by = AGENT_TITLES[d.chain[-2]] if len(d.chain) > 1 else "the ticket board"
    return (
        "## This run\n"
        f"- Ticket: #{d.ticket_id}\n"
        f"- You were asked by: {asked_by}\n"
        f"- Delegation chain so far: {' -> '.join(AGENT_TITLES[a] for a in d.chain)} "
        f"(depth {d.depth} of max {MAX_DELEGATION_DEPTH})\n"
        f"- When a tool asks for created_by / requested_by / drafted_by / proposed_by / "
        f"updated_by, use \"{AGENT_TITLES[d.agent]}\".\n"
        "- Shop facts come only from your tools. Finish with your report; keep it to the facts "
        "you verified."
    )


async def delegate_to_agent(ctx: RunContext[TeamDeps], agent: AgentName, task: str, reason: str) -> dict:
    """Hand a specific task to a teammate and get their report back.

    agent: boss | inventory | accounting | facilities | customer_service
    task: exactly what you need them to do, including any facts they'll need (ticket id, SKU,
          size, amounts you already verified).
    reason: one line on why this belongs to them (recorded in the audit trail).
    """
    d = ctx.deps
    refusal = None
    if agent == d.agent:
        refusal = "You can't delegate to yourself; handle it."
    elif agent in d.chain:
        refusal = (f"{AGENT_TITLES[agent]} is already waiting on this chain "
                   f"({' -> '.join(d.chain)}); return your findings to them instead.")
    elif d.depth >= MAX_DELEGATION_DEPTH:
        refusal = f"Delegation depth limit ({MAX_DELEGATION_DEPTH}) reached; finish with what you have."
    elif d.budget.delegations >= MAX_DELEGATIONS_PER_TICKET:
        refusal = f"Ticket delegation budget ({MAX_DELEGATIONS_PER_TICKET}) used up; finish with what you have."
    elif d.budget.tokens >= MAX_TOKENS_PER_TICKET:
        refusal = f"Ticket token budget ({MAX_TOKENS_PER_TICKET}) used up; finish with what you have."

    detail = {"to": agent, "task": task, "reason": reason}
    if refusal:
        _log(d, 0, "delegation_refused", detail={**detail, "refusal": refusal})
        return {"delegated": False, "refusal": refusal}

    d.budget.delegations += 1
    _log(d, 0, "delegation", detail={**detail, "delegation_number": d.budget.delegations})
    child = TeamDeps(run_id=d.run_id, ticket_id=d.ticket_id, agent=agent, depth=d.depth + 1,
                     chain=[*d.chain, agent], budget=d.budget)
    report = await run_agent(agent, task, child)
    return {"delegated": True, "report": report.model_dump()}


def make_agent(role: AgentName) -> Agent[TeamDeps, AgentReport]:
    agent = Agent(
        _MODEL,
        name=role,
        deps_type=TeamDeps,
        output_type=AgentReport,
        instructions=[(PROMPTS_DIR / f"{role}.md").read_text(), _runtime_context],
        toolsets=[toolset_for(role)],
        tools=[delegate_to_agent],
        retries=2,
    )
    REGISTRY[role] = agent
    return agent


async def run_agent(role: AgentName, task: str, deps: TeamDeps) -> AgentReport:
    """One agent loop, with every step appended to the audit trail."""
    agent = REGISTRY[role]
    _log(deps, 0, "run_start", text=_clip(task))
    limits = UsageLimits(request_limit=MAX_REQUESTS_PER_AGENT_RUN,
                         total_tokens_limit=MAX_TOKENS_PER_AGENT_RUN)
    step = 0
    run = None
    try:
        async with agent.iter(task, deps=deps, usage_limits=limits) as run:
            async for node in run:
                step += 1
                if Agent.is_model_request_node(node):
                    results = []
                    for p in node.request.parts:
                        if isinstance(p, ToolReturnPart):
                            results.append({"tool": p.tool_name, "content": _clip(p.content)})
                        elif isinstance(p, RetryPromptPart):
                            results.append({"tool": p.tool_name, "retry": _clip(p.content)})
                    _log(deps, step, "model_request", tool_results=results)
                elif Agent.is_call_tools_node(node):
                    resp = node.model_response
                    calls = [{"tool": p.tool_name, "args": p.args_as_dict()}
                             for p in resp.parts if isinstance(p, ToolCallPart)]
                    text = " ".join(p.content for p in resp.parts if isinstance(p, TextPart)).strip()
                    u = resp.usage
                    _log(deps, step, "model_response", text=_clip(text) if text else None,
                         tool_calls=calls,
                         usage={"input_tokens": u.input_tokens, "output_tokens": u.output_tokens})
        usage = run.usage
        deps.budget.tokens += usage.total_tokens
        report = run.result.output
        _log(deps, step + 1, "run_end", detail={"report": report.model_dump()},
             usage={"requests": usage.requests, "tool_calls": usage.tool_calls,
                    "total_tokens": usage.total_tokens, "ticket_tokens_so_far": deps.budget.tokens})
        return report
    except (UsageLimitExceeded, Exception) as exc:  # a stuck agent must not take down the team
        if run is not None:
            deps.budget.tokens += run.usage.total_tokens
        kind = "limit" if isinstance(exc, UsageLimitExceeded) else type(exc).__name__
        _log(deps, step + 1, "error", text=_clip(str(exc)), detail={"kind": kind})
        return AgentReport(agent=role, summary=f"Stopped early ({kind}): {exc}",
                           blockers=[f"{AGENT_TITLES[role]} did not finish: {exc}"])
