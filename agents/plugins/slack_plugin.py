"""Slack チャンネルメッセージ取得プラグイン.

slack_channels コンテナの 1 メッセージ = 1 ドキュメント設計をそのまま使う。
- 定量集計: get_slack_speaker_counts（SQL GROUP BY）
- 定性テキスト: get_project_slack_messages / get_member_slack_messages
未指定時は直近 3 ヶ月を返す（コンテキスト保護）。
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Annotated

from azure.cosmos import ContainerProxy
from semantic_kernel.functions import kernel_function

_DEFAULT_LOOKBACK_DAYS = 90


def _default_date_from() -> str:
    return (datetime.now(timezone.utc) - timedelta(days=_DEFAULT_LOOKBACK_DAYS)).date().isoformat()


def _normalize_date(value: str, *, fallback: str | None = None) -> str | None:
    v = (value or "").strip()
    if not v:
        return fallback
    return v


class SlackPlugin:
    """slack_channels コンテナへのアクセスを提供する."""

    def __init__(self, slack_channels_container: ContainerProxy) -> None:
        self._slack = slack_channels_container

    @kernel_function(
        description=(
            "プロジェクトの Slack チャンネル発言回数を発言者ごとに集計して返す（SQL集計・LLM不要）"
        )
    )
    def get_slack_speaker_counts(
        self,
        project_id: Annotated[str, "プロジェクトID"],
        date_from: Annotated[str, "期間下限 ISO日付（例: 2026-01-01）。空文字なら直近3ヶ月"] = "",
        date_to: Annotated[str, "期間上限 ISO日付。空文字なら現在"] = "",
    ) -> str:
        df = _normalize_date(date_from, fallback=_default_date_from())
        dt = _normalize_date(date_to)

        clauses = ["c.project_id = @pid", "c.type = 'slack_message'"]
        params: list[dict] = [{"name": "@pid", "value": project_id}]
        if df:
            clauses.append("c.posted_at >= @df")
            params.append({"name": "@df", "value": df})
        if dt:
            clauses.append("c.posted_at <= @dt")
            params.append({"name": "@dt", "value": dt})

        query = (
            "SELECT c.speaker_id, c.speaker, COUNT(1) AS count "
            "FROM c WHERE " + " AND ".join(clauses) +
            " GROUP BY c.speaker_id, c.speaker"
        )
        items = list(
            self._slack.query_items(
                query=query, parameters=params, enable_cross_partition_query=True,
            )
        )
        items.sort(key=lambda x: x.get("count", 0), reverse=True)
        return json.dumps(
            {"project_id": project_id, "date_from": df, "date_to": dt, "counts": items},
            ensure_ascii=False,
        )

    @kernel_function(
        description=(
            "プロジェクトの Slack チャンネル本文を時系列で連結して返す（LLM が定性分析するためのテキスト）"
        )
    )
    def get_project_slack_messages(
        self,
        project_id: Annotated[str, "プロジェクトID"],
        date_from: Annotated[str, "期間下限 ISO日付。空文字なら直近3ヶ月"] = "",
        date_to: Annotated[str, "期間上限 ISO日付。空文字なら現在"] = "",
        speaker_id: Annotated[str, "特定発言者のemailで絞り込み（空文字なら全員）"] = "",
    ) -> str:
        df = _normalize_date(date_from, fallback=_default_date_from())
        dt = _normalize_date(date_to)
        sp = _normalize_date(speaker_id)

        clauses = ["c.project_id = @pid", "c.type = 'slack_message'"]
        params: list[dict] = [{"name": "@pid", "value": project_id}]
        if df:
            clauses.append("c.posted_at >= @df")
            params.append({"name": "@df", "value": df})
        if dt:
            clauses.append("c.posted_at <= @dt")
            params.append({"name": "@dt", "value": dt})
        if sp:
            clauses.append("c.speaker_id = @sp")
            params.append({"name": "@sp", "value": sp})

        query = (
            "SELECT c.speaker, c.posted_at, c.text "
            "FROM c WHERE " + " AND ".join(clauses) + " ORDER BY c.posted_at ASC"
        )
        items = list(
            self._slack.query_items(
                query=query, parameters=params, enable_cross_partition_query=True,
            )
        )
        lines = [
            f"{(m.get('posted_at') or '')[:10]} {m.get('speaker','?')}: {m.get('text','').strip()}"
            for m in items if m.get("text")
        ]
        return "\n".join(lines) if lines else "（該当発言なし）"

    @kernel_function(
        description=(
            "特定メンバーの Slack 発言テキストを時系列で連結して返す。"
            "プロジェクト指定があればその PJ チャンネル内のみ"
        )
    )
    def get_member_slack_messages(
        self,
        member_id: Annotated[str, "メンバーのemail（speaker_id と一致）"],
        project_id: Annotated[str, "プロジェクトIDで絞り込み（空文字なら全PJ横断）"] = "",
        date_from: Annotated[str, "期間下限 ISO日付。空文字なら直近3ヶ月"] = "",
        date_to: Annotated[str, "期間上限 ISO日付。空文字なら現在"] = "",
    ) -> str:
        df = _normalize_date(date_from, fallback=_default_date_from())
        dt = _normalize_date(date_to)
        pid = _normalize_date(project_id)

        clauses = ["c.speaker_id = @mid", "c.type = 'slack_message'"]
        params: list[dict] = [{"name": "@mid", "value": member_id}]
        if pid:
            clauses.append("c.project_id = @pid")
            params.append({"name": "@pid", "value": pid})
        if df:
            clauses.append("c.posted_at >= @df")
            params.append({"name": "@df", "value": df})
        if dt:
            clauses.append("c.posted_at <= @dt")
            params.append({"name": "@dt", "value": dt})

        query = (
            "SELECT c.channel_name, c.posted_at, c.text "
            "FROM c WHERE " + " AND ".join(clauses) + " ORDER BY c.posted_at ASC"
        )
        items = list(
            self._slack.query_items(
                query=query, parameters=params, enable_cross_partition_query=True,
            )
        )
        lines = [
            f"{(m.get('posted_at') or '')[:10]} [#{m.get('channel_name','?')}] {m.get('text','').strip()}"
            for m in items if m.get("text")
        ]
        return "\n".join(lines) if lines else "（該当発言なし）"
