"""Boss: reads each ticket, routes work, makes the final call.

Prompt: backend/prompts/boss.md. MCP tools: see ROLE_TOOLS["boss"] in backend/mcp_tools.py.
"""

from .base import make_agent

agent = make_agent("boss")
