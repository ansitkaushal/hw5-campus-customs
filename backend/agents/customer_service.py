"""Customer Service: drafts customer and external messages (never sends).

Prompt: backend/prompts/customer_service.md. MCP tools: see ROLE_TOOLS["customer_service"] in backend/mcp_tools.py.
"""

from .base import make_agent

agent = make_agent("customer_service")
