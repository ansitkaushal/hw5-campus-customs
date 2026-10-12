"""Facilities: lease, rent timing, landlord notices, shop space.

Prompt: backend/prompts/facilities.md. MCP tools: see ROLE_TOOLS["facilities"] in backend/mcp_tools.py.
"""

from .base import make_agent

agent = make_agent("facilities")
