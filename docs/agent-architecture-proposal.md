# エージェントアーキテクチャ設計提案

> 作成: 2026-05-25  
> ステータス: 議論中（随時更新）  
> 目的: コンテキスト長の問題を解消し、モード別に最適化されたマルチエージェント構成に再設計する

---

## 1. 現状の問題点

### 1-1. 全プラグインが常に1つのKernelに同居している

現在の実装では、モードに関わらず6プラグイン・20+ツールが常に1つのKernelに登録されている。
`FunctionChoiceBehavior.Auto()` はすべてのツール定義をシステムプロンプトに展開するため、
実際には不要なツールの定義が毎回コンテキストを消費している。

```
現状: [Kernel] ← MemberPlugin + ProjectPlugin + ContributionPlugin
                  + MeetingPlugin + TeamBalancePlugin + SynergyPlugin
     すべてのモードで全ツールが見える（= ノイズ）
```

### 1-2. アサインモードのコンテキスト爆発

アサイン提案では以下が順次チャット履歴に蓄積される:

```
get_project_detail()         → ~1,000 tokens
get_member_detail() × 10    → ~500 tokens × 10 = 5,000 tokens (slack_vlog 20件込み)
get_member_task_stats() × 10 → ~300 tokens × 10 = 3,000 tokens
get_member_meeting_analyses() × 10 → ~400 tokens × 10 = 4,000 tokens
────────────────────────────────────────────────────
合計データ量: ~13,000 tokens（推論・プロンプト除く）
```

10名全員のデータを取得してから候補を絞り込もうとすると、中盤で実用的なコンテキスト上限を超える。

### 1-3. 候補者の事前絞り込みがない

現状は「全員のフル詳細を取ってから考える」アプローチ。  
実際は「スキル一致で5〜7名に絞ってから詳細取得」が正しい順序。

### 1-4. サブエージェントが「エージェント」ではなくプラグイン

計画ドキュメント（§6.5）ではサブエージェントを定義しているが、実装は全ツールが
Orchestratorの同一Kernelに同居するプラグインのまま。コンテキスト分離の効果がない。

---

## 2. 設計方針（決定事項）

### 決定: ReAct は全モード共通・固定

`FunctionChoiceBehavior.Auto()` + `ChatCompletionAgent` による ReAct パターンは  
全モードで統一する。「コードでフローを強制しない、でもプロンプトとツールセットで行動を誘導する」。

**モードの特別さはこの2つで出す:**

| 軸 | ベースチャット | アサイン提案 | 個人スキル分析 |
|---|---|---|---|
| **使えるツール** | 汎用5本（概要把握） | 専門ツール含む最大12本 | メンバー深掘り5本 |
| **システムプロンプト** | 「質問に何でも答えよ」 | 「必ず候補絞り→詳細→チーム評価の順で包括レポートを出せ」 | 「対象メンバーを5軸で深く分析しレポート出力せよ」 |

→ 同じ ReAct エンジンでも、**ツールセット × プロンプト** でエージェントの行動範囲と深さが自然に変わる。

### その他の設計方針

1. **モード別カーネル**: 各モードに必要なプラグインだけを登録した専用Kernelを使う
2. **候補者事前絞り込み**: アサイン時のプロンプトで「まずスキル絞り込み → 候補者詳細取得」を明示指示
3. **出力サイズキャップ**: 各ツールの返却データ量に上限を設ける（Slack vlog件数制限など）
4. **サブエージェントはKernelFunctionとして実装**: 独立LLM呼び出しが必要なものだけ真のサブエージェント化

---

## 3. 新アーキテクチャ全体像

```
[User Message]
      │
      ▼
[IntentClassifier]  ← gpt-4o-mini 直接呼び出し（SKなし、max_tokens=10）
      │
      ├─ "chat" ──────────────────────► [BaseChatAgent]
      │                                   Kernel: ChatPlugin のみ
      │                                   ツール数: 4
      │                                   コンテキスト目標: 8K tokens
      │
      ├─ "skill" ─────────────────────► [SkillAnalysisAgent]
      │                                   Kernel: MemberPlugin + ContributionPlugin + MeetingPlugin
      │                                   ツール数: 5
      │                                   コンテキスト目標: 12K tokens
      │
      ├─ "assignment" ─────────────────► [AssignmentOrchestrator]
      │                                   Kernel: サブエージェント呼び出しツールのみ
      │                                   ツール数: 4（全部サブエージェント委譲）
      │                                   コンテキスト目標: 16K tokens
      │                                      │
      │                                      ├─ [CandidateScreenerAgent]
      │                                      │    Kernel: MemberPlugin（slim）
      │                                      │    目的: 候補者を5〜7名に絞る
      │                                      │    コンテキスト: 3K tokens
      │                                      │
      │                                      ├─ [MemberProfilerAgent] × 並列
      │                                      │    Kernel: MemberPlugin + ContributionPlugin + MeetingPlugin
      │                                      │    目的: 候補者1名の詳細プロファイル生成
      │                                      │    コンテキスト: 4K tokens / 1名
      │                                      │    出力: 構造化200-300 token サマリー
      │                                      │
      │                                      └─ [TeamEvaluatorAgent]
      │                                           Kernel: SynergyPlugin + TeamBalancePlugin
      │                                           目的: チーム全体のバランス・コスト評価
      │                                           コンテキスト: 4K tokens
      │
      └─ "refine" ─────────────────────► 既存レポート + フィードバック → 対応モードで再実行
```

---

## 4. エージェント別ツール設計

### 4.0 IntentClassifier（変更なし）

| 属性 | 内容 |
|---|---|
| 実装 | `AsyncAzureOpenAI.chat.completions.create()` 直接呼び出し |
| モデル | gpt-4o（`max_tokens=10, temperature=0`） |
| ツール | なし |
| 出力 | `"chat"` / `"skill"` / `"assignment"` / `"refine"` |

---

### 4.1 BaseChatAgent（改善）

**現状からの変更**: SynergyPlugin / TeamBalancePlugin / ContributionPlugin を除外

| ツール | プラグイン | 変更 |
|---|---|---|
| `list_all_members()` | MemberPlugin | 変更なし（compact） |
| `list_all_projects(status?)` | ProjectPlugin | 変更なし（compact） |
| `get_member_detail(member_id)` | MemberPlugin | Slack vlog を 5件に削減 |
| `get_project_summary(project_id)` | ProjectPlugin | **新規**: tasks[] を含まない軽量版 |
| `search_slack_context(query)` | SlackPlugin | **新規**: slack_channels全文検索 |

**コンテキスト予算**: ~8K tokens

---

### 4.2 SkillAnalysisAgent（改善）

**現状からの変更**: ProjectPlugin / SynergyPlugin / TeamBalancePlugin を除外

| ツール | プラグイン | 変更 |
|---|---|---|
| `get_member_detail(member_id)` | MemberPlugin | Slack vlog を 10件に制限 |
| `get_member_schedule(member_id)` | MemberPlugin | 変更なし |
| `get_member_task_stats(member_id)` | ContributionPlugin | 変更なし |
| `get_member_meeting_analyses(member_id)` | MeetingPlugin | `full_text` を除外して返す |
| `find_members_by_skill(skill)` | MemberPlugin | メンバー名検索に使用 |

**コンテキスト予算**: ~12K tokens（対象1名のフル分析）

---

### 4.3 AssignmentOrchestrator（大幅改善）

**現状からの変更**: Cosmos DB直接ツールをすべて除去。サブエージェント呼び出し口のみ持つ。

| ツール（=サブエージェント呼び出し） | 概要 | 実装 |
|---|---|---|
| `screen_candidates(project_id, required_skills_json)` | CandidateScreenerAgentを呼び出し。候補者IDリストを返す | Python関数 → SK Agent 呼び出し |
| `get_member_profile(member_id, project_context)` | MemberProfilerAgentを呼び出し。1名の構造化プロファイルを返す | Python関数 → SK Agent 呼び出し |
| `evaluate_team(member_ids_json, project_id)` | TeamEvaluatorAgentを呼び出し。チーム全体評価を返す | Python関数 → SK Agent 呼び出し |
| `find_project_info(project_name_or_id)` | ProjectPlugin直接呼び出し（例外的に直接持つ） | ProjectPlugin |

**Orchestratorのシステムプロンプト役割**: コーディネーション + 最終レポート合成のみ

**コンテキスト予算**: 
- サブエージェント結果（コンパクトサマリー × 7名以内）: ~7K tokens
- 自身の推論 + プロンプト: ~5K tokens
- 合計目標: ~16K tokens

---

### 4.4 CandidateScreenerAgent（新規）

**目的**: プロジェクト要件を元に全メンバー概要を見て、詳細取得する候補を5〜7名に絞る。

| ツール | プラグイン | 備考 |
|---|---|---|
| `list_all_members_compact()` | MemberPlugin | **新規**: id/name/role/skills/monthly_cost のみ |
| `find_members_by_skill(skill)` | MemberPlugin | 変更なし |
| `get_member_schedule(member_id)` | MemberPlugin | 空き期間確認 |

**出力形式**:
```json
{
  "candidates": ["kobayashi@abc.com", "nakamura@abc.com", ...],
  "reason": "Pythonスキル必須 → 8名候補 → スケジュール空き → 6名に絞り込み"
}
```

**コンテキスト予算**: ~3K tokens（全メンバー概要 + 推論）

---

### 4.5 MemberProfilerAgent（新規・LLMバック）

**目的**: 候補者1名について、プロジェクト文脈を踏まえた詳細プロファイルを生成する。  
**実行**: 候補者ごとに独立したLLM呼び出し（並列実行可能）

| ツール | プラグイン | 変更 |
|---|---|---|
| `get_member_detail(member_id)` | MemberPlugin | Slack vlog 5件のみ |
| `get_member_task_stats(member_id)` | ContributionPlugin | 変更なし |
| `get_member_meeting_analyses(member_id)` | MeetingPlugin | full_text 除外 |
| `get_member_schedule(member_id)` | MemberPlugin | 変更なし |

**入力**: `member_id` + `project_context`（必要スキル・期間・役割要件）  
**出力形式**（上限300 tokens）:

```markdown
## [氏名] プロファイル
- スキルマッチ: ★★★★☆（Python/RAG/Azure全カバー）
- 稼働可否: ○（PJ-Aが7/31終了、8/1〜空き）
- 貢献実績: PJ-BでSP合計42、完了率88%
- リーダー適性: 議事録3件で「施策提案2件・ファシリテーション◎」
- 月次コスト: ¥850,000
- 推薦役割: テックリード候補
```

**コンテキスト予算**: ~4K tokens / 1名

---

### 4.6 TeamEvaluatorAgent（新規・既存2プラグインを統合）

**目的**: 提案チームのシナジー・バランス・コストをワンショットで評価する。

| ツール | プラグイン | 備考 |
|---|---|---|
| `get_collaboration_matrix(member_ids_json)` | SynergyPlugin | 変更なし |
| `evaluate_team_balance(team_json)` | TeamBalancePlugin | 変更なし |
| `calc_project_cost(member_ids, project_id)` | ContributionPlugin | 変更なし |

**入力**: 提案チーム（member_ids + roles）+ project_id  
**出力**: チームバランス評価 + シナジーマトリクス + コスト試算（構造化Markdown）

**コンテキスト予算**: ~4K tokens

---

## 5. 出力サイズキャップ（ツール実装の変更）

| ツール | 現状 | 改善後 |
|---|---|---|
| `get_member_detail` | Slack vlog 20件 | モード別: BaseChatは5件 / SkillAnalysisは10件 / Profilerは5件 |
| `get_project_detail` | tasks[]全件（生テキスト含む） | `get_project_summary`（tasks除外）と`get_project_tasks`に分離 |
| `get_member_meeting_analyses` | `full_text`フィールドを含む | `full_text`を除外（`member_analyses[]`と`overall_summary`のみ） |
| `list_all_members` | 6フィールド | CandidateScreener用は`id/name/role/skills/monthly_cost`の5フィールドのみ |

---

## 6. コンテキスト予算比較

| フロー | 現状 | 改善後 |
|---|---|---|
| ベースチャット | 全プラグイン定義 ~3K + データ ~2K = **~5K** | 必要定義 ~1K + データ ~2K = **~3K** |
| スキル分析（1名） | 全プラグイン定義 ~3K + 1名データ ~8K = **~11K** | 専用定義 ~1K + 1名データ ~5K = **~6K** |
| アサイン提案（10名） | 全プラグイン定義 ~3K + 全員フルデータ ~13K = **~16K+** | 絞込後サマリー ~7K + オーケストレーション ~5K = **~12K** |

---

## 7. 実装上の変更箇所

### 変更が必要なファイル

| ファイル | 変更内容 |
|---|---|
| `agents/orchestrator.py` | `_build_kernel()` をモード別に分割。AssignmentモードはサブエージェントKernelを構築 |
| `agents/plugins/member_plugin.py` | `list_all_members_compact()` 追加。`get_member_detail`のSlack vlog件数をパラメータ化 |
| `agents/plugins/project_plugin.py` | `get_project_summary()`（tasks除外）を追加 |
| `agents/plugins/meeting_plugin.py` | `get_member_meeting_analyses`のfull_text除外オプションを追加 |
| `agents/sub_agents/` | **新規ディレクトリ**: CandidateScreenerAgent / MemberProfilerAgent / TeamEvaluatorAgent |

### 新規ファイル

| ファイル | 内容 |
|---|---|
| `agents/sub_agents/candidate_screener.py` | CandidateScreenerAgent クラス |
| `agents/sub_agents/member_profiler.py` | MemberProfilerAgent クラス |
| `agents/sub_agents/team_evaluator.py` | TeamEvaluatorAgent クラス |
| `agents/plugins/slack_plugin.py` | SlackPlugin（slack_channels検索） |
| `agents/prompts/candidate_screener.txt` | CandidateScreener用システムプロンプト |
| `agents/prompts/member_profiler.txt` | MemberProfiler用システムプロンプト |
| `agents/prompts/team_evaluator.txt` | TeamEvaluator用システムプロンプト |

---

## 8. サブエージェント呼び出しの実装パターン（Semantic Kernel）

```python
# agents/sub_agents/member_profiler.py（実装例）

class MemberProfilerAgent:
    """候補者1名のプロファイルをLLMで生成するサブエージェント."""

    def __init__(self, settings: AgentSettings) -> None:
        # 専用Kernelを構築（必要な3プラグインのみ）
        kernel = Kernel()
        kernel.add_service(AzureChatCompletion(...))
        kernel.add_plugin(MemberPlugin(slim_vlog=5), "MemberPlugin")
        kernel.add_plugin(ContributionPlugin(...), "ContributionPlugin")
        kernel.add_plugin(MeetingPlugin(exclude_full_text=True), "MeetingPlugin")
        
        self._agent = ChatCompletionAgent(
            kernel=kernel,
            name="MemberProfilerAgent",
            instructions=_load_prompt("member_profiler.txt"),
            function_choice_behavior=FunctionChoiceBehavior.Auto(),
        )

    async def profile(self, member_id: str, project_context: str) -> str:
        """候補者1名の構造化プロファイルを300tokens以内で返す."""
        history = ChatHistory()
        history.add_user_message(
            f"メンバー {member_id} を以下のプロジェクト文脈で評価してください:\n{project_context}"
        )
        result = ""
        async for response in self._agent.invoke(messages=history):
            result += str(response.message) if response.message else ""
        return result


# AssignmentOrchestratorから呼ぶKernelFunction
@kernel_function(description="候補者1名の詳細プロファイルを生成する（~300tokens）")
async def get_member_profile(
    self,
    member_id: Annotated[str, "メンバーのemail"],
    project_context: Annotated[str, "プロジェクト要件・必要スキルの要約"],
) -> str:
    return await self._profiler.profile(member_id, project_context)
```

---

## 9. 並列実行戦略

CandidateScreenerAgentで絞り込んだ候補者に対して、MemberProfilerAgentを並列実行する:

```python
# AssignmentOrchestratorの内部（サブエージェント起動部）

candidates = json.loads(await screen_candidates(project_id, required_skills))
profiles = await asyncio.gather(*[
    self._profiler.profile(mid, project_context)
    for mid in candidates["candidates"]
])
```

これにより10名全員の逐次処理（= コンテキスト蓄積）を回避し、
オーケストレーターには各プロファイルのコンパクトサマリーのみ届く。

---

## 10. 未解決事項・要検討

| 項目 | 内容 | 優先度 |
|---|---|---|
| サブエージェントのコスト | MemberProfilerAgentをN並列 → LLM呼び出しN倍。gpt-4o-miniへの切り替えを検討 | 中 |
| リトライ / フォールバック | サブエージェント失敗時の挙動（タイムアウト・エラーハンドリング） | 低 |
| Slack能動投稿ツール | `send_slack_notification()`をどのエージェントに持たせるか | 中 |
| refineモードとの整合 | 既存レポートをサブエージェント経由で部分更新する方式 | 低 |
