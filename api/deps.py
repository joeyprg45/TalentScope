"""依存性注入: orchestrator / cosmos のシングルトン提供."""
from __future__ import annotations

from functools import lru_cache

from agents.config import AgentSettings
from agents.cosmos_client import CosmosContainers
from agents.orchestrator import TalentScopeOrchestrator


@lru_cache(maxsize=1)
def get_settings() -> AgentSettings:
    return AgentSettings.from_env()


@lru_cache(maxsize=1)
def get_orchestrator() -> TalentScopeOrchestrator:
    return TalentScopeOrchestrator(get_settings())


@lru_cache(maxsize=1)
def get_cosmos() -> CosmosContainers:
    return CosmosContainers(get_settings())
