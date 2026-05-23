"""Cosmos DB コンテナクライアントのファクトリ."""
from __future__ import annotations

from azure.cosmos import ContainerProxy, CosmosClient

from agents.config import AgentSettings


class CosmosContainers:
    """4つのコンテナクライアントをまとめて保持する."""

    members:       ContainerProxy
    projects:      ContainerProxy
    meetings:      ContainerProxy
    slack_channels: ContainerProxy

    def __init__(self, settings: AgentSettings) -> None:
        client = CosmosClient.from_connection_string(settings.cosmos_connection_string)
        db = client.get_database_client(settings.cosmos_database)
        self.members       = db.get_container_client("members")
        self.projects      = db.get_container_client("projects")
        self.meetings      = db.get_container_client("meetings")
        self.slack_channels = db.get_container_client("slack_channels")

