"""Connects the agents to the Campus Customs MCP server, with a narrow tool list per role.

This is the only path from an agent to shop data: there is no second tools layer.
"""

from __future__ import annotations

from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from pydantic_ai.mcp import MCPToolset

from .config import HW_DIR, MCP_SERVER, mcp_python

# Only a named human (via the dashboard) may call these. No agent ever sees them.
HUMAN_ONLY_TOOLS = {"approve_payment_request", "reject_payment_request"}

ROLE_TOOLS: dict[str, set[str]] = {
    "boss": {
        "list_open_tickets", "get_ticket", "update_ticket", "get_cash_position",
        "list_pending_approvals", "check_stock_and_pricing", "get_invoice_vendor_status",
        "get_rent_due_and_cash",
    },
    "inventory": {
        "get_ticket", "check_stock_and_pricing", "list_vendors_with_status",
        "get_invoice_vendor_status", "draft_purchase_order",
    },
    "accounting": {
        "get_ticket", "get_cash_position", "get_invoice_vendor_status", "get_rent_due_and_cash",
        "check_stock_and_pricing", "list_pending_approvals", "request_payment", "propose_bulk_quote",
    },
    "facilities": {"get_ticket", "get_rent_due_and_cash", "get_cash_position"},
    "customer_service": {"get_ticket", "check_stock_and_pricing", "draft_customer_message"},
}

assert not any(HUMAN_ONLY_TOOLS & tools for tools in ROLE_TOOLS.values())

# One MCP server process shared by the whole team.
shop_mcp = MCPToolset(
    Client(StdioTransport(command=mcp_python(), args=[str(MCP_SERVER)], cwd=str(HW_DIR))),
    id="campus-customs",
)


def toolset_for(role: str):
    allowed = ROLE_TOOLS[role]
    return shop_mcp.filtered(lambda ctx, tool_def: tool_def.name in allowed)
