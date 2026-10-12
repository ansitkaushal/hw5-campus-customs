"""Accounting: cash, invoices, margins, payment requests for human approval.

Prompt: backend/prompts/accounting.md. MCP tools: see ROLE_TOOLS["accounting"] in backend/mcp_tools.py.
"""

from .base import make_agent

agent = make_agent("accounting")
