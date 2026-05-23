"""エージェント設定.

環境変数から AgentSettings を生成する唯一の場所。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv


@dataclass
class AgentSettings:
    cosmos_connection_string: str
    azure_openai_api_key: str
    azure_openai_endpoint: str
    azure_openai_chat_deployment: str = "gpt-4o"
    azure_openai_api_version: str = "2024-12-01-preview"
    cosmos_database: str = "talentscope"

    @classmethod
    def from_env(cls) -> "AgentSettings":
        load_dotenv()
        required: dict[str, str | None] = {
            "COSMOS_CONNECTION_STRING": os.getenv("COSMOS_CONNECTION_STRING"),
            "AZURE_OPENAI_API_KEY":     os.getenv("AZURE_OPENAI_API_KEY"),
            "AZURE_OPENAI_ENDPOINT":    os.getenv("AZURE_OPENAI_ENDPOINT"),
        }
        missing = [k for k, v in required.items() if not v]
        if missing:
            raise EnvironmentError(f"必須の環境変数が未設定: {missing}")
        return cls(
            cosmos_connection_string=required["COSMOS_CONNECTION_STRING"],  # type: ignore[arg-type]
            azure_openai_api_key=required["AZURE_OPENAI_API_KEY"],          # type: ignore[arg-type]
            azure_openai_endpoint=required["AZURE_OPENAI_ENDPOINT"],        # type: ignore[arg-type]
            azure_openai_chat_deployment=os.getenv(
                "AZURE_OPENAI_CHAT_DEPLOYMENT_NAME", "gpt-4o"
            ),
            azure_openai_api_version=os.getenv(
                "AZURE_OPENAI_API_VERSION", "2024-12-01-preview"
            ),
        )
