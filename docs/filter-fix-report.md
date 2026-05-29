# サブエージェントフィルター汚染バグ — 調査・修正レポート

**日付**: 2026-05-28  
**対象**: TalentScope / Base Chat モード

---

## 1. 発見した問題

### 症状

以下のクエリを投げたとき、最終回答に明らかに無関係なプロジェクトのデータが引用された。

> 「田中は次世代 LLM Agent 基盤開発においてどんなタスクをしていたの？また、そのタスクに対してなにか感じていることはある？」

LLM の最終回答に「目標の 20% 改善を達成した」という文言が田中の感想として引用されたが、これは **「大手EC向けレコメンドエンジン開発」の中間レビュー議事録** の内容であり、次世代 LLM Agent 基盤開発とは無関係なプロジェクトだった。

### トレースで確認した原因

`docs/analysys.md` のトレースログを精査した結果、`ConversationAnalysisAgent` が `MeetingPlugin-get_member_meetings` を呼び出す際、**`project_id` を一切渡さずに田中の全会議を取得**していたことが判明。

```json
{
  "type": "tool_call",
  "tool": "MeetingPlugin-get_member_meetings",
  "args": { "member_id": "tanaka@abc.com", "limit": 5 }
}
```

返ってきた結果の先頭に `project_id: 36ac7942...`（大手ECプロジェクト）が入っており、それを LLM が「田中の発言」として読み込んでしまった。

---

## 2. 根本原因の分析

### なぜフィルターが機能しなかったのか

サブエージェントへの指示はすべて **自由形式のテキスト**として渡されていた。

```
対象ID: tanaka@abc.com
質問: このメンバーがどんな発言をしているか分析して
```

`project_id` は `target_id` として渡されることもあるが、それは「対象プロジェクト」と「メンバーを絞る条件」が混在しており、会議取得の WHERE 句に使われることはなかった。

### ツール引数 vs テキスト文脈の違い

| 渡し方 | LLMの扱い |
|---|---|
| **テキスト文脈**（文章の中に書く） | 参考情報として読むが、ツール引数に反映するかは LLM の判断次第 |
| **ツール関数の引数**（`Annotated` 型定義） | JSON Schema に載るため LLM が「どの値を入れるべきか」を意識的に検討する |

`project_id` をツールの引数として定義することで、LLM は呼び出し時に「この引数に何を入れるか」を強制的に考えるようになる。

### フィルターギャップの全体像

実装前の各ツールのフィルター対応状況:

| ツール | project_id | date_from | date_to | 状態 |
|---|---|---|---|---|
| `SlackPlugin.get_member_slack_messages` | ✅ | ✅ | ✅ | 問題なし |
| `SlackPlugin.get_project_slack_messages` | ✅ | ✅ | ✅ | 問題なし |
| `MeetingPlugin.get_member_meetings` | ❌ | ❌ | ❌ | **要修正** |
| `MeetingPlugin.get_project_meetings` | ✅ | ✅ | ❌ | date_to 欠落 |
| `MeetingPlugin.get_member_meeting_analyses` | ❌ | ❌ | — | **要修正** |
| `ContributionPlugin.get_member_task_stats` | ❌ | — | — | **要修正** |

さらに、サブエージェントを呼び出す `invoke_*` 関数にも `project_id` 引数が存在しなかったため、Main Agent が `project_id` を知っていても伝える手段がなかった。

---

## 3. 修正方針

### 方針: フィルターをツール引数に昇格させ、スタック全体に伝播させる

```
Main Agent（project_id を認識）
    ↓ invoke_*（project_id を引数として渡す）
SubAgentPlugin（run() に project_id を転送）
    ↓
Sub Agent（コンテキスト文字列に project_id を明記）
    ↓
Tool（WHERE 句で DB レベルフィルター）
```

DB レベルでフィルターすることで LLM の読み違いや推論による補完の余地をなくす。

---

## 4. 実装内容

### 4-1. `agents/plugins/meeting_plugin.py`

**`get_member_meetings`**: `project_id`, `date_from`, `date_to` を追加。WHERE 句で動的に絞り込む。

```python
def get_member_meetings(
    self,
    member_id: Annotated[str, "メンバーのemail"],
    project_id: Annotated[str, "絞り込むプロジェクトID（空文字なら全PJ）"] = "",
    date_from: Annotated[str, "期間下限 ISO日付（空文字なら制限なし）"] = "",
    date_to: Annotated[str, "期間上限 ISO日付（空文字なら現在）"] = "",
    limit: Annotated[int, "取得件数上限（デフォルト10）"] = 10,
) -> str:
```

**`get_project_meetings`**: `date_to` を追加（上限が指定できなかった）。

**`get_member_meeting_analyses`**: `project_id`, `date_from` を追加。

### 4-2. `agents/plugins/contribution_plugin.py`

**`get_member_task_stats`**: `project_id` を追加。プロジェクト横断タスク集計の汚染を防ぐ。

```python
def get_member_task_stats(
    self,
    member_id: Annotated[str, "メンバーのemail"],
    project_id: Annotated[str, "絞り込むプロジェクトID（空文字なら全PJ）"] = "",
) -> str:
```

### 4-3. サブエージェント `run()` メソッド（3ファイル）

`conversation_analysis.py`, `task_analysis.py`, `member_profiler.py` それぞれに `project_id`, `date_from`, `date_to` を追加。コンテキスト文字列にも明示して Sub Agent が忘れないようにした。

```python
if project_id:
    ctx_lines.append(f"対象プロジェクトID: {project_id}（このPJのデータのみ取得すること）")
```

括弧内の補足（「このPJのデータのみ取得すること」）は LLM へのソフト強制として機能する。

### 4-4. `agents/plugins/sub_agent_plugin.py`

全 `invoke_*` 関数に `project_id`, `date_from`, `date_to` を Semantic Kernel の `Annotated` 型引数として追加。

```python
project_id: Annotated[str, "絞り込むプロジェクトID（プロジェクトが特定されている場合は必ず指定）"] = "",
```

`"プロジェクトが特定されている場合は必ず指定"` という description が JSON Schema に乗るため、Main Agent が project_id を知っていれば自然に渡すようになる。

### 4-5. `agents/prompts/base_chat.txt`

明示的なルールとして追記:

```
## サブエージェント呼び出し時のフィルタールール
- project_id が判明している場合は必ず project_id を渡す
  （指定しないと他PJのデータが混入する）
- 期間が特定できる場合は date_from / date_to を渡す
- project_id を渡す前に、プロジェクト名しかわからない場合は
  find_project_by_name で project_id を取得すること
```

---

## 5. 修正前後の比較

### 修正前のツール呼び出し（バグあり）

```json
{
  "tool": "MeetingPlugin-get_member_meetings",
  "args": { "member_id": "tanaka@abc.com", "limit": 5 }
}
```
→ 田中が関わる**全プロジェクトの会議**が返る（最新順のため無関係PJが先頭に）

### 修正後の期待される呼び出し

```json
{
  "tool": "MeetingPlugin-get_member_meetings",
  "args": {
    "member_id": "tanaka@abc.com",
    "project_id": "366c7942-...",
    "limit": 5
  }
}
```
→ 次世代 LLM Agent 基盤開発の会議**のみ**が返る

---

## 6. 学んだこと

1. **サブエージェントへの指示はテキストより引数で渡す**  
   テキスト文脈に書いても LLM がツール引数に反映させる保証はない。型付き引数にすることでスキーマレベルの強制力が生まれる。

2. **DB フィルターは「どこか 1 箇所」ではなくスタック全体に伝播させる**  
   Main Agent → invoke_* → run() → tool の全層でフィルターが欠けていた。どこか 1 箇所だけ直しても効果がない。

3. **プロンプトの文言は「理由付き指示」にする**  
   `"絞り込むプロジェクトID（プロジェクトが特定されている場合は必ず指定）"` のように description に理由を書くことで LLM がエッジケースでも正しく判断できる。
