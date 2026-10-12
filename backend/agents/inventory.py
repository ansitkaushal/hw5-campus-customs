"""Inventory: stock by SKU/size, shortfalls, restock vendors, draft POs.

Prompt: backend/prompts/inventory.md. MCP tools: see ROLE_TOOLS["inventory"] in backend/mcp_tools.py.
"""

from .base import make_agent

agent = make_agent("inventory")
