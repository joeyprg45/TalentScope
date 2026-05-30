"""GitHub MCP サーバーの読み取り専用ツールを @kernel_function として公開するプラグイン.

呼び出しごとに Node.js サブプロセスを起動して MCP ツールを実行する。
書き込み系ツール（create_*, push_*, merge_*）は意図的に含めない。
"""
from __future__ import annotations

import os
import shutil
from typing import Annotated

from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from semantic_kernel.functions import kernel_function

load_dotenv()


def _build_server_params() -> StdioServerParameters:
    npx_path = shutil.which("npx") or "npx"
    token = os.getenv("GITHUB_ACCESS_TOKEN", "")
    return StdioServerParameters(
        command=npx_path,
        args=["-y", "@modelcontextprotocol/server-github"],
        env={**os.environ, "GITHUB_PERSONAL_ACCESS_TOKEN": token},
    )


async def _call_mcp(tool_name: str, args: dict) -> str:
    """GitHub MCP サーバーを起動してツールを 1 回呼び出す."""
    params = _build_server_params()
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, args)
            parts = [
                item.text if hasattr(item, "text") else str(item)
                for item in result.content
            ]
            return "\n".join(parts) if parts else "(no content)"


class GitHubMCPPlugin:
    """GitHub MCP 経由の GitHub 読み取りツール群."""

    @kernel_function(
        description="GitHubユーザーの公開リポジトリを検索する。'user:username' 形式でユーザーを絞り込める"
    )
    async def search_repositories(
        self,
        query: Annotated[str, "検索クエリ（例: 'user:alice' / 'user:alice language:python'）"],
        per_page: Annotated[int, "1ページあたりの件数（最大100、デフォルト30）"] = 30,
    ) -> str:
        return await _call_mcp("search_repositories", {"query": query, "perPage": per_page})

    @kernel_function(
        description="リポジトリのファイル内容を取得する（package.json / requirements.txt / go.mod 等で技術スタック特定に使う）"
    )
    async def get_file_contents(
        self,
        owner: Annotated[str, "リポジトリオーナー（ユーザー名または組織名）"],
        repo: Annotated[str, "リポジトリ名"],
        path: Annotated[str, "ファイルパス（例: 'package.json'）"],
        branch: Annotated[str, "ブランチ名（省略時はデフォルトブランチ）"] = "",
    ) -> str:
        from mcp.shared.exceptions import McpError
        args: dict = {"owner": owner, "repo": repo, "path": path}
        if branch:
            args["branch"] = branch
        try:
            return await _call_mcp("get_file_contents", args)
        except (McpError, Exception) as e:
            if "not found" in str(e).lower():
                return f"(ファイルなし: {path})"
            raise

    @kernel_function(
        description="リポジトリのコミット一覧を取得する（コミット頻度・活動履歴の確認に使う）"
    )
    async def list_commits(
        self,
        owner: Annotated[str, "リポジトリオーナー"],
        repo: Annotated[str, "リポジトリ名"],
        per_page: Annotated[int, "取得件数（デフォルト30）"] = 30,
    ) -> str:
        return await _call_mcp("list_commits", {"owner": owner, "repo": repo, "perPage": per_page})

    @kernel_function(
        description="リポジトリのイシュー一覧を取得する"
    )
    async def list_issues(
        self,
        owner: Annotated[str, "リポジトリオーナー"],
        repo: Annotated[str, "リポジトリ名"],
        state: Annotated[str, "'open' / 'closed' / 'all'（デフォルト: 'all'）"] = "all",
        per_page: Annotated[int, "取得件数（デフォルト20）"] = 20,
    ) -> str:
        return await _call_mcp("list_issues", {"owner": owner, "repo": repo, "state": state, "per_page": per_page})

    @kernel_function(
        description="イシューの詳細を取得する"
    )
    async def get_issue(
        self,
        owner: Annotated[str, "リポジトリオーナー"],
        repo: Annotated[str, "リポジトリ名"],
        issue_number: Annotated[int, "イシュー番号"],
    ) -> str:
        return await _call_mcp("get_issue", {"owner": owner, "repo": repo, "issue_number": issue_number})

    @kernel_function(
        description="リポジトリのプルリクエスト一覧を取得する（実装活動・コラボレーション確認に使う）"
    )
    async def list_pull_requests(
        self,
        owner: Annotated[str, "リポジトリオーナー"],
        repo: Annotated[str, "リポジトリ名"],
        state: Annotated[str, "'open' / 'closed' / 'all'（デフォルト: 'all'）"] = "all",
        per_page: Annotated[int, "取得件数（デフォルト20）"] = 20,
    ) -> str:
        return await _call_mcp(
            "list_pull_requests",
            {"owner": owner, "repo": repo, "state": state, "per_page": per_page},
        )

    @kernel_function(
        description="プルリクエストの詳細を取得する"
    )
    async def get_pull_request(
        self,
        owner: Annotated[str, "リポジトリオーナー"],
        repo: Annotated[str, "リポジトリ名"],
        pull_number: Annotated[int, "プルリクエスト番号"],
    ) -> str:
        return await _call_mcp("get_pull_request", {"owner": owner, "repo": repo, "pull_number": pull_number})

    @kernel_function(
        description="プルリクエストで変更されたファイル一覧を取得する（実装規模・影響範囲の確認に使う）"
    )
    async def get_pull_request_files(
        self,
        owner: Annotated[str, "リポジトリオーナー"],
        repo: Annotated[str, "リポジトリ名"],
        pull_number: Annotated[int, "プルリクエスト番号"],
    ) -> str:
        return await _call_mcp("get_pull_request_files", {"owner": owner, "repo": repo, "pull_number": pull_number})

    @kernel_function(
        description="プルリクエストのレビュー一覧を取得する（コードレビュー活動の確認に使う）"
    )
    async def get_pull_request_reviews(
        self,
        owner: Annotated[str, "リポジトリオーナー"],
        repo: Annotated[str, "リポジトリ名"],
        pull_number: Annotated[int, "プルリクエスト番号"],
    ) -> str:
        return await _call_mcp("get_pull_request_reviews", {"owner": owner, "repo": repo, "pull_number": pull_number})

    @kernel_function(
        description="プルリクエストのコメント一覧を取得する"
    )
    async def get_pull_request_comments(
        self,
        owner: Annotated[str, "リポジトリオーナー"],
        repo: Annotated[str, "リポジトリ名"],
        pull_number: Annotated[int, "プルリクエスト番号"],
    ) -> str:
        return await _call_mcp(
            "get_pull_request_comments", {"owner": owner, "repo": repo, "pull_number": pull_number}
        )

    @kernel_function(
        description="GitHub でコードを検索する（特定ライブラリ・フレームワークの使用パターン確認に使う）"
    )
    async def search_code(
        self,
        q: Annotated[str, "検索クエリ（例: 'user:alice react useState'）"],
        per_page: Annotated[int, "取得件数（デフォルト20）"] = 20,
    ) -> str:
        return await _call_mcp("search_code", {"q": q, "per_page": per_page})

    @kernel_function(
        description="GitHub ユーザーを検索する（ユーザー名の存在確認に使う）"
    )
    async def search_users(
        self,
        q: Annotated[str, "検索クエリ（例: 'alice'）"],
        per_page: Annotated[int, "取得件数（デフォルト10）"] = 10,
    ) -> str:
        return await _call_mcp("search_users", {"q": q, "per_page": per_page})
