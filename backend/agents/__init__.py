"""The five Campus Customs agents. Importing this package builds and registers all of them,
so any agent can delegate to any other through delegate_to_agent."""

from . import accounting, boss, customer_service, facilities, inventory  # noqa: F401
from .base import REGISTRY, run_agent

__all__ = ["REGISTRY", "run_agent"]
