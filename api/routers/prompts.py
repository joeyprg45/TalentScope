"""プロンプトモード管理 API.

GET  /api/prompts          - 全ノード一覧（木構造）
GET  /api/prompts/{id}     - 1件取得
PUT  /api/prompts/{id}     - trigger_conditions / ceo_layer を更新
POST /api/prompts          - カスタムモード新規作成
DELETE /api/prompts/{id}   - 削除（is_system=true は 403）
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from azure.cosmos.exceptions import CosmosResourceNotFoundError
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.deps import get_cosmos

logger = logging.getLogger(__name__)

router = APIRouter()

# 必須ノード定義（trigger_conditions + ceo_layer）
_REQUIRED_NODES: list[dict[str, Any]] = [
    {
        "id": "base_chat",
        "parent_id": None,
        "name": "通常応答",
        "description": "メンバー・プロジェクト・会議・Slack に関する一般的な質問に答えるモード",
        "trigger_conditions": (
            "一般的な質問・情報収集・雑談。アサイン提案やスキル分析以外のすべての発言。"
            "例: 「誰が空いてる？」「プロジェクト一覧を見せて」「田中さんの連絡先は？」"
        ),
        "ceo_layer": "質問には簡潔かつデータに基づいた回答をすること。不確かな情報は「記録なし」と明記する。",
        "is_system": True,
        "is_selectable": True,
    },
    {
        "id": "assignment",
        "parent_id": None,
        "name": "アサイン提案",
        "description": "プロジェクトへのメンバーアサインを提案するモード",
        "trigger_conditions": (
            "アサイン提案・チーム編成を実行してほしい明確なリクエスト。"
            "例: 「アサイン提案をして」「プロジェクトAのチームを組んで」「誰をアサインすべきか提案して」"
        ),
        "ceo_layer": (
            "あなたは「TalentScope」のアサイン提案エージェントです。\n"
            "プロジェクトに最適なチームを、スキル・実績・リーダーシップを根拠に提案してください。\n\n"
            "## 分析手順（必ずこの順で全ステップを実行する）\n\n"
            "### Step 0: プロジェクト特定\n"
            "- プロジェクト名指定 → find_project_by_name(name) で project_id を取得\n"
            "- project_id が既知 → get_project_detail(project_id) を直接呼ぶ\n"
            "- 未指定・複数候補 → list_all_projects() で active/planning から選択、または ask_user_clarification で確認\n\n"
            "### Step 1: プロジェクト詳細取得\n"
            "get_project_detail(project_id) を呼び、以下を記録する:\n"
            "- required_skills（必要スキルリスト）\n"
            "- start_date / end_date（プロジェクト期間）\n"
            "- github_repo（あれば）\n\n"
            "### Step 2: 稼働可能メンバー抽出\n"
            "find_available_members(date_from, date_to) を呼び、プロジェクト期間に稼働可能なメンバーのみを候補プールとする。\n"
            "→ 稼働中メンバーはアサイン候補に絶対含めない\n\n"
            "### Step 3: スキルフィルタリング（ツール呼び出し不要）\n"
            "❌ この Step では一切ツールを呼ばない\n"
            "- Step 1 の required_skills と Step 2 の各メンバー skills を内部で照合する\n"
            "- 必要スキルを 1 つ以上保有する候補を 3〜8 名に絞り込む\n"
            "- 絞り込んだ候補リストを Step 4 に引き渡す（ツール呼び出しは不要）\n\n"
            "### Step 4: 個別プロファイル取得（全候補を網羅）\n"
            "絞り込んだ全候補に対して invoke_member_profiler(member_id, project_context) を呼ぶ。\n"
            "- 省略禁止: 最低 3 名、最大 8 名を必ずプロファイルすること\n"
            "- 1 名でプロファイルを打ち切らない\n"
            "- 直前のツール呼び出しが失敗・エラーでも、次の候補のプロファイル取得を続行する\n\n"
            "### Step 4b: GitHub 補強（任意）\n"
            "プロファイルに github_username が含まれる候補に対して invoke_github_analyzer(github_username, github_repo) を呼ぶ。\n"
            "- github_repo は Step 1 の github_repo フィールドを使う（なければ省略）\n\n"
            "### Step 5: チームドラフト組成\n"
            "プロファイル結果を元に、役割・スキルカバレッジ・コストバランスを考慮してドラフトを組む。\n"
            "ドラフト形式: {\"project_id\": \"...\", \"period\": {\"start\": \"YYYY-MM-DD\", \"end\": \"YYYY-MM-DD\"}, \"proposed_team\": [{\"member_id\": \"email@example.com\", \"role\": \"...\"}]}\n\n"
            "### Step 5b: スキルカバレッジ確認（ドラフト確定後に 1 回だけ）\n"
            "find_skill_gaps(project_id, proposed_member_ids_json) でカバレッジを確認する。\n"
            "⚠️ proposed_member_ids_json は必ずダブルクォート JSON 配列:\n"
            '   ✅ 正: ["email1@example.com", "email2@example.com"]\n'
            "   ❌ 誤: ['email1@example.com', 'email2@example.com']（Python式 NG — coverage_rate: 0.0 になる）\n\n"
            "### Step 6: チームレビュー（1 回のみ）\n"
            "invoke_team_evaluator(draft_json) にドラフトを渡す。\n"
            "- ✅ 承認 → そのまま最終提案へ\n"
            "- ⚠️ 要修正 → 指摘に応じてドラフトを修正し最終提案へ（invoke_team_evaluator を再度呼ばない）\n\n"
            "### Step 7: コスト試算\n"
            "calc_project_cost(member_ids_json, project_id) で最終チームのコストを試算する。\n"
            "⚠️ member_ids_json は必ずダブルクォート JSON 配列\n\n"
            "## 出力形式（必ず以下の Markdown 構造で出力する）\n\n"
            "# {プロジェクト名} アサイン提案レポート\n\n"
            "## プロジェクト概要\n"
            "- 概要: ...\n"
            "- 期間: ...ヶ月（YYYY-MM-DD 〜 YYYY-MM-DD）\n"
            "- 必要スキル: ...\n\n"
            "## 推奨チーム構成\n"
            "| メンバー | 役割 | 推薦理由 | 月次コスト |\n"
            "|---|---|---|---|\n"
            "| ... | ... | スキル/実績/MTGリーダーシップの根拠を具体的に | ¥... |\n\n"
            "## コスト試算\n"
            "- 対象期間: ...ヶ月\n"
            "- 月次合計: ¥...\n"
            "- 総コスト: ¥...\n\n"
            "## スキルギャップ分析\n"
            "- カバー済みスキル: ...\n"
            "- 不足スキル: ...（不足がなければ「なし」と記載）\n"
            "- 補完案: ...\n\n"
            "## チームバランス評価\n"
            "（invoke_team_evaluator の結果を整形して記載）\n\n"
            "## 役職・昇給レコメンド\n"
            "| メンバー | 現役職 | 推奨役職変更 | 昇給提案 | 根拠（実績・MTG評価） |\n"
            "|---|---|---|---|---|\n"
            "| ... | ... | ... | ... | ... |\n"
            "（実績がない場合は「現時点では変更なし」と記載）\n\n"
            "## 注意事項\n"
            "- データに基づいて具体的に回答する。推測は「推定:」と前置きする\n"
            "- スキルマッチだけでなく、タスク完了率・議事録での発言内容を根拠として明示する\n"
            "- 日本語で出力する"
        ),
        "is_system": True,
        "is_selectable": True,
    },
    {
        "id": "skill_analysis",
        "parent_id": None,
        "name": "スキル分析",
        "description": "メンバーのスキル・実績・貢献度を詳細分析するモード",
        "trigger_conditions": (
            "特定メンバーのスキル分析レポートを生成してほしいリクエスト。"
            "例: 「田中のスキル分析をして」「鈴木のスキルレポートを出して」"
        ),
        "ceo_layer": (
            "スキル分析はGitHubの実装実績とCosmosのタスク実績を必ず両方確認すること。"
            "強みと課題を並列で提示し、育成提案まで含めること。"
        ),
        "is_system": True,
        "is_selectable": True,
    },
]

# 初回起動時のマイグレーション実行フラグ
_migrated = False


def _ensure_nodes(cosmos) -> None:
    """必須ノードが存在し trigger_conditions を持つことを保証する（起動後1回のみ）."""
    global _migrated
    if _migrated:
        return
    _migrated = True
    now = datetime.now(timezone.utc).isoformat()
    for node in _REQUIRED_NODES:
        try:
            item = cosmos.prompts.read_item(item=node["id"], partition_key=node["id"])
            # trigger_conditions が空なら補完（ceo_layer は上書きしない）
            if not item.get("trigger_conditions"):
                item["trigger_conditions"] = node["trigger_conditions"]
                item["is_selectable"] = True
                item["updated_at"] = now
                cosmos.prompts.upsert_item(item)
        except CosmosResourceNotFoundError:
            # ノードが存在しない場合のみ新規作成（他の例外は伝播させる）
            try:
                doc = {**node, "created_at": now, "updated_at": now}
                cosmos.prompts.upsert_item(doc)
            except Exception as e:
                logger.error(f"[_ensure_nodes] failed to create node {node['id']}: {e}")
        except Exception as e:
            logger.error(f"[_ensure_nodes] read_item failed for {node['id']}: {e}")


# ---------- レスポンスモデル ----------

class PromptNode(BaseModel):
    id: str
    parent_id: str | None
    name: str
    description: str = ""
    trigger_conditions: str = ""
    ceo_layer: str = ""
    is_system: bool = False
    is_selectable: bool = True
    children: list["PromptNode"] = []


class UpdatePromptRequest(BaseModel):
    ceo_layer: str | None = None
    trigger_conditions: str | None = None


class CreatePromptRequest(BaseModel):
    id: str
    parent_id: str | None = None
    name: str
    description: str = ""
    trigger_conditions: str = ""
    ceo_layer: str = ""
    is_selectable: bool = True


def _to_node(item: dict) -> PromptNode:
    return PromptNode(
        id=item["id"],
        parent_id=item.get("parent_id"),
        name=item.get("name", ""),
        description=item.get("description", ""),
        trigger_conditions=item.get("trigger_conditions", ""),
        ceo_layer=item.get("ceo_layer", ""),
        is_system=item.get("is_system", False),
        is_selectable=item.get("is_selectable", True),
    )


# ---------- エンドポイント ----------

@router.get("", response_model=list[PromptNode])
def list_prompts(cosmos=Depends(get_cosmos)) -> list[PromptNode]:
    _ensure_nodes(cosmos)
    items = list(cosmos.prompts.query_items(
        query="SELECT * FROM c ORDER BY c.id",
        enable_cross_partition_query=True,
    ))
    node_map: dict[str, PromptNode] = {}
    for item in items:
        node_map[item["id"]] = _to_node(item)
    roots: list[PromptNode] = []
    for node in node_map.values():
        if node.parent_id and node.parent_id in node_map:
            node_map[node.parent_id].children.append(node)
        else:
            roots.append(node)
    return roots


@router.get("/{prompt_id:path}", response_model=PromptNode)
def get_prompt(prompt_id: str, cosmos=Depends(get_cosmos)) -> PromptNode:
    try:
        item = cosmos.prompts.read_item(item=prompt_id, partition_key=prompt_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return _to_node(item)


@router.put("/{prompt_id:path}", response_model=PromptNode)
def update_prompt(prompt_id: str, body: UpdatePromptRequest, cosmos=Depends(get_cosmos)) -> PromptNode:
    try:
        item = cosmos.prompts.read_item(item=prompt_id, partition_key=prompt_id)
    except CosmosResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Prompt not found")
    except Exception as e:
        logger.error(f"[update_prompt] read_item failed for {prompt_id}: {e}")
        raise HTTPException(status_code=500, detail=f"DB read failed: {e}")

    if body.ceo_layer is not None:
        item["ceo_layer"] = body.ceo_layer
    if body.trigger_conditions is not None:
        item["trigger_conditions"] = body.trigger_conditions
    item["updated_at"] = datetime.now(timezone.utc).isoformat()

    try:
        cosmos.prompts.upsert_item(item)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB write failed: {e}")

    return _to_node(item)


@router.post("", response_model=PromptNode, status_code=201)
def create_prompt(body: CreatePromptRequest, cosmos=Depends(get_cosmos)) -> PromptNode:
    try:
        cosmos.prompts.read_item(item=body.id, partition_key=body.id)
        raise HTTPException(status_code=409, detail="Prompt id already exists")
    except HTTPException:
        raise
    except Exception:
        pass
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": body.id,
        "parent_id": body.parent_id,
        "name": body.name,
        "description": body.description,
        "trigger_conditions": body.trigger_conditions,
        "ceo_layer": body.ceo_layer,
        "is_system": False,
        "is_selectable": body.is_selectable,
        "created_at": now,
        "updated_at": now,
    }
    cosmos.prompts.upsert_item(doc)
    return _to_node(doc)


@router.delete("/{prompt_id:path}", status_code=204)
def delete_prompt(prompt_id: str, cosmos=Depends(get_cosmos)) -> None:
    try:
        item = cosmos.prompts.read_item(item=prompt_id, partition_key=prompt_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Prompt not found")
    if item.get("is_system"):
        raise HTTPException(status_code=403, detail="System prompts cannot be deleted")
    cosmos.prompts.delete_item(item=prompt_id, partition_key=prompt_id)
