"""Paths, the single model, and run limits for the Campus Customs agent team."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider

HW_DIR = Path(__file__).resolve().parent.parent          # hw5/ (repo root)
PROMPTS_DIR = HW_DIR / "backend" / "prompts"
DB_ORIGINAL = HW_DIR / "data" / "campus_customs.db"
DB_WORKING = HW_DIR / "data" / "campus_customs_new.db"
MCP_SERVER = HW_DIR / "mcp_server" / "server.py"
AUDIT_TRAIL = HW_DIR / "output" / "audit_trail.json"

# The only model used anywhere in this project.
MODEL_NAME = "gpt-6-luna"

# Token / loop limits.
MAX_REQUESTS_PER_AGENT_RUN = 8     # model round-trips one agent may take per task
MAX_TOKENS_PER_AGENT_RUN = 60_000  # tokens one agent may spend per task
MAX_DELEGATION_DEPTH = 3           # Boss -> A -> B -> C, no deeper
MAX_DELEGATIONS_PER_TICKET = 8     # handoffs across the whole team for one ticket
MAX_TOKENS_PER_TICKET = 250_000    # all agents combined, one ticket
AUDIT_TEXT_LIMIT = 2_000           # chars kept per tool result / text in the audit trail

# PORTKEY_API_KEY: use hw5/.env if present, otherwise the nearest .env in a parent folder
# (e.g. a course-level .env). Never committed; see .env.example.
for _d in (HW_DIR, *HW_DIR.parents):
    if (_d / ".env").is_file():
        load_dotenv(_d / ".env")
        break
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")


def build_model() -> OpenAIResponsesModel:
    """gpt-6-luna through Portkey's OpenAI-compatible endpoint. No temperature override.

    Uses the Responses API: through Portkey, gpt-6-luna rejects function tools on
    /v1/chat/completions ("use /v1/responses"), and every agent here needs tools.
    """
    client = AsyncOpenAI(
        api_key=os.environ["PORTKEY_API_KEY"],
        base_url="https://api.portkey.ai/v1",
        default_headers={"x-portkey-provider": "openai"},
    )
    return OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))


def mcp_python() -> str:
    """Python interpreter used to launch the MCP server (this project's .venv)."""
    venv = HW_DIR / ".venv" / "bin" / "python"
    return str(venv if venv.exists() else Path(sys.executable))
