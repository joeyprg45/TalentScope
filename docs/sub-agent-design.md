# サブエージェント設計書: 会話分析 / タスク分析 / メンバープロファイラー / チーム評価

> 作成: 2026-05-27
> ステータス: 設計確定・実装待ち
> 背景: agent-architecture-proposal.md の全体方針を踏まえ、
>       4サブエージェントを具体化したもの

---

## 1. 設計の背景と方針

### なぜサブエージェントを分けるか

| 問題 | 対策 |
|---|---|
| 会議 full_text・Slack メッセージはデータ量が多くなる | 会話分析専用エージェントに隔離し、Main のコンテキストを汚染しない |
| タスク数・進捗も PJ 長期化で増加する | タスク分析専用エージェントに隔離、Main は集計結果サマリーだけ受け取る |
| 特定人物を深く分析しようとするとコンテキスト爆発する（Slack + 会議 + タスク全部） | MemberProfilerAgent に委譲し、300tokens のコンパクトプロファイルだけ受け取る |
| チーム評価（シナジー・バランス・コスト）はまとめて専用エージェントに任せたい | TeamEvaluatorAgent に隔離 |

### 全エージェント ReAct 統一

すべてのエージェント（Main / サブ）は **ReAct パターン（`FunctionChoiceBehavior.Auto()` + `ChatCompletionAgent`）** で統一する。
コードでフローを強制せず、**ツールセット × システムプロンプト** で行動範囲と深さを制御する。

### TeamEvaluator のモード決定タイミング

TeamEvaluatorAgent のプロンプト（評価の観点・出力形式）は、**IntentClassifier がモードを決定した時点**で確定させる。
アサイン提案モードならコスト試算重視、スキル分析モードならシナジー重視、というように切り替える。

---

## 2. エージェント構成

```
[Main Agent]
  受け取る: ユーザー質問 + インテント分類結果
  役割: 質問を解釈し、どのサブエージェントに何を聞くか決める + 結果を統合して回答
  持つツール: メンバー/プロジェクト概要 + サブエージェント呼び出し口
       │
       ├──► [会話分析サブエージェント]
       │      受け取る: project_id or member_id + 期間 + 分析の観点
       │      役割: Slack チャンネルメッセージ・会議 full_text を横断して
       │            発言傾向・リーダーシップ・提案内容を返す
       │      データ源: slack_channels コンテナ + meetings コンテナ
       │
       ├──► [タスク分析サブエージェント]
       │      受け取る: project_id or member_id + 分析の観点
       │      役割: タスク実績を読んで貢献度・スキル・問題解決力を返す
       │
       ├──► [MemberProfilerAgent]
       │      受け取る: member_id + プロジェクト文脈
       │      役割: Slack + 会議 + タスクを横断して1名の構造化プロファイルを生成（~300tokens）
       │      トリガー: Main が「この人を深く掘り下げたい」段階で呼ぶ
       │
       └──► [TeamEvaluatorAgent]
              受け取る: member_ids + project_id
              役割: シナジー・バランス・コストをワンショット評価
              モード: IntentClassifier のモード決定時にプロンプトも決定
```

---

## 3. 会話分析サブエージェント

Slack チャンネルメッセージと会議 full_text を「会話データ」として統一的に扱い、
発言傾向・リーダーシップ・特定テーマへの貢献を分析する。

### 想定クエリ例

| 質問 | データ源 | 処理方法 |
|---|---|---|
| 「PJ1 の1〜2月に最も発言が多いのは？」 | `slack_channels`（期間フィルタ） | `get_slack_speaker_counts()` でSQL集計 → 最大値特定 |
| 「エージェントアーキテクチャの提案が多いのは？」 | `slack_channels` + `meetings` | 両方のテキストを取得 → LLM がキーワード文脈で判断 |
| 「失敗の分析が最も得意なのは？」 | `slack_channels` + `meetings` | 両方のテキストを取得 → LLM が定性評価 |

### ツール

#### SlackPlugin（新規）

| ツール | パラメータ | 返却データ | 用途 |
|---|---|---|---|
| `get_slack_speaker_counts(project_id, date_from?, date_to?)` | project_id + 期間（任意） | `[{speaker_id, speaker, count}]` の JSON | **定量**: 発言回数の集計（SQL、LLM不要） |
| `get_project_slack_messages(project_id, date_from?, date_to?, speaker_id?)` | project_id + 期間（任意）+ 発言者（任意） | `"田中: 〜\n前田: 〜\n..."` の連結テキスト | **定性**: LLM に渡す会話本文 |
| `get_member_slack_messages(member_id, project_id?)` | member_id + PJ（任意） | 同上（特定メンバー絞り込み） | 特定人物の Slack 発言履歴 |

> `get_slack_speaker_counts` は CosmosDB の SQL 集計で処理するため、
> 大量メッセージでも LLM コンテキストを消費しない。
> 「最多発言者は誰？」のような定量クエリはこちらだけで完結させる。

#### MeetingPlugin（既存）

| ツール | 取得データ | 用途 |
|---|---|---|
| `get_project_meetings(project_id, date_from?, limit?)` | title / date / meeting_type / **full_text** | 会議横断の分析。`limit` 未指定時は直近10件 |
| `get_member_meetings(member_id, limit?)` | 上記 + member_id フィルタ | 特定人物の会議発言。`limit` 未指定時は直近10件 |

> full_text は1件あたり数百〜数千トークンになりうる。
> `limit` を使わない場合は会議数 × full_text がコンテキスト上限（~10K）を超えるリスクがある。

### DB スキーマ: `slack_channels` コンテナ（変更なし）

現状の 1メッセージ = 1ドキュメント設計をそのまま使う。

```json
{
  "id": "C0B5C36EL02::1234567890.123",
  "channel_id": "C0B5C36EL02",
  "channel_name": "proj-llm-agent-infra",
  "channel_kind": "project",
  "project_id": "366c7942-...",
  "speaker": "田中 誠",
  "speaker_id": "tanaka@abc.com",
  "posted_at": "2026-01-15T10:30:00+00:00",
  "ts": "1234567890.123",
  "text": "エージェントのアーキテクチャですが..."
}
```

| フィールド | 用途 |
|---|---|
| `project_id` | プロジェクト別フィルタ（SQL WHERE） |
| `posted_at` | 期間フィルタ（`date_from` 〜 `date_to`） |
| `speaker_id` | メンバー別集計・フィルタ（GROUP BY） |
| `text` | LLM に渡す発言テキスト |

> スキーマ変更は不要。ツール側のクエリロジックを追加するだけでよい。

### システムプロンプト

```
あなたは会話データ（Slack・会議）を分析する専門エージェントです。

【データ形式】
- Slack メッセージ: 「氏名: 発言内容」形式で時系列に並んでいる
- 会議 full_text: 同じく「氏名: 発言内容」形式

【ツールの使い分け】
- 「誰が最も多く発言したか」などの定量質問 → get_slack_speaker_counts を使う（LLM 読み取り不要）
- 「どんな提案をしていたか」「リーダーシップがあるか」などの定性質問
  → get_project_slack_messages / get_project_meetings でテキストを取得して読む
- 期間の指定がある場合は date_from / date_to を必ず渡す

【分析観点（質問に応じて使い分ける）】
- 発言量: カウントツールの結果をそのまま使う
- リーダーシップ: 議題設定・まとめ・意思決定・他者への指示が見られるか
- 提案力: 新しいアイデアや施策を具体的に出しているか
- 失敗分析: 問題の原因を掘り下げ、再発防止や改善案を述べているか
- ファシリテーション: 議論を整理・収束させているか

【出力ルール】
- 根拠となる発言を必ず引用すること（「田中: 〜」のように）
- 定量（発言回数）と定性（内容の質）は明確に分けて述べる
- 発言が確認できたメンバーのみ評価に含める
```

---

## 4. タスク分析サブエージェント

### 想定クエリ例

| 質問 | 何を読むか | 何を判断するか |
|---|---|---|
| 「AIアーキテクチャ設計をしていたのは誰？」 | task name / description | テーマで担当者を特定 |
| 「詰まったとき最もうまく施策を提案しているのは誰？」 | result_note | 困難克服の具体性と質 |
| 「AI学習基盤の設計・最適化が最も上手かったのは誰？」 | skills_used + description + SP + 完了率 | 複合的な貢献度評価 |
| 「このプロジェクトで誰が一番貢献したか？」 | 全タスクの SP + 完了率 + result_note | 定量 + 定性の複合評価 |

### ツール

| ツール | 取得データ | 用途 |
|---|---|---|
| `get_project_tasks(project_id)` | 全タスク（name / assignee / status / SP / skills_used / result_note / **description**） | プロジェクト内のテーマ特定・担当者マッピング |
| `get_member_task_stats(member_id)` | メンバー別 SP 合計 / 完了率 / スキル / task_descriptions | メンバー間の比較評価 |

### システムプロンプト

```
あなたはタスク実績を分析する専門エージェントです。

【データの読み方】
- name / description: タスクの内容・テーマ・スコープが書かれている
- result_note: 実際に何をしたか、どんな困難があったか、どう解決したか
- skills_used: そのタスクで実際に使ったスキル（自己申告）
- story_points / 完了率: 量的な貢献度の指標

【分析観点（質問に応じて使い分ける）】
- テーマ特定: task の name と description からキーワードで担当者を絞り込む
- 問題解決力: result_note の内容の具体性・創意工夫の有無で評価する
- スキルの深さ: skills_used の専門性 + description の内容から判断する
- 貢献度: SP × 完了率 を基本指標とし、result_note の質で補正する

【出力ルール】
- 根拠となるタスク名・result_note を必ず引用すること
- メンバー間を比較するときは数値根拠（SP・完了率）と定性評価を併記する
- description や result_note が空のタスクは定性評価から除外してよい
```

---

## 5. MemberProfilerAgent

### 目的・トリガー

Main Agent が分析・比較をするなかで「この人物を深掘りしたい」段階でトリガーされる。
Slack vlog・会議 full_text・タスク実績を1エージェント内で横断して読み、
**300tokens 以内の構造化プロファイル**を Main に返す。
これにより Main のコンテキストに生データが流入することを防ぐ。

### ツール

| ツール | 取得データ | 用途 |
|---|---|---|
| `get_member_detail(member_id)` | 基本情報 + Slack vlog（最新5件） | 人物像・コミュニケーション傾向の把握 |
| `get_member_schedule(member_id)` | 全PJの在籍期間（project_name / role / start_date / end_date） | 稼働状況・空き期間の把握 |
| `get_member_meetings(member_id)` | 参加会議の full_text | 会議での発言傾向・役割 |
| `get_member_task_stats(member_id)` | SP 合計 / 完了率 / スキル / task_descriptions | 技術力・貢献度の定量・定性把握 |

> `get_member_schedule` は `projects.assignments[]` を横断して特定メンバーのスケジュールを返す。
> `get_member_meetings` は会話分析SA と同じツールを共用する（full_text 込み）。
> MemberProfilerAgent は「横断して1人を総合評価する」用途のため、別SAとして独立させる。

### 出力フォーマット（~300tokens 上限）

```markdown
## [氏名] プロファイル
- **スキルマッチ**: Python / RAG / Azure カバー（3/3）
- **稼働**: PJ-A が 7/31 終了、8/1 〜 空き
- **タスク貢献**: SP 合計 42、完了率 88%（PJ-B）
- **会議での役割**: 施策提案 2件・ファシリテーション多数
- **Slack 傾向**: 技術共有投稿が多い、リアクションも活発
- **推薦役割**: テックリード候補
```

### システムプロンプト

```
あなたは特定メンバーを多角的に評価する専門エージェントです。

【分析の進め方】
1. get_member_detail でメンバーの基本情報と Slack の近況を把握する
2. get_member_meetings で会議での発言傾向・役割を確認する
3. get_member_task_stats でタスク実績（定量・定性）を確認する

【出力ルール】
- 300tokens 以内の構造化 Markdown で返すこと
- スキルマッチ・稼働可否・タスク貢献・会議での役割・Slack 傾向・推薦役割 の6軸で構成する
- 根拠のないフィールドは「データなし」と明記し、推測で埋めない
- プロジェクト文脈（必要スキル・役割）が渡された場合はそれを踏まえて評価すること
```

---

## 6. TeamEvaluatorAgent

### 目的・トリガー

Main Agent がアサイン提案のドラフトを組み立てた後、**1回だけ呼ばれるレビュアー**として機能する。
ドラフト提案を受け取り、コスト・バランス・スキルカバレッジ・シナジーの観点で問題点を指摘する。
問題がなければ「承認」、問題があれば「具体的な指摘」を返す。Main はその結果を受けて最終回答を調整する。

> 会話フロー中（候補選定の途中）には呼ばない。**ドラフト完成後の一発レビューのみ**。

### 入力

```json
{
  "project_id": "366c7942-...",
  "period": { "start": "2026-08-01", "end": "2026-10-31" },
  "proposed_team": [
    { "member_id": "kimura@abc.com", "role": "テックリード" },
    { "member_id": "hasegawa@abc.com", "role": "バックエンド" }
  ]
}
```

### ツール

| ツール | 取得データ | 用途 |
|---|---|---|
| `get_collaboration_matrix(member_ids)` | 過去の共同 PJ 回数・シナジースコア | シナジー確認 |
| `evaluate_team_balance(team_json)` | 役割・スキル・シニア/ジュニア比率 | バランスチェック |
| `calc_project_cost(member_ids, project_id)` | 月次コスト × 期間 = 総コスト試算 | コスト検証 |
| `find_skill_gaps(project_id)` | PJ必要スキルと提案チームの保有スキルを照合 | スキル不足の検出 |
| `compare_members(member_ids, aspect)` | 指定メンバーのスキル・タスク貢献を横並び比較 | 役割適性の比較検証 |

### 出力フォーマット

```markdown
## レビュー結果: ✅ 承認 / ⚠️ 要修正

### 問題点（あれば）
- ⚠️ **コスト超過**: 試算 ¥11,200,000 > 予算 ¥10,000,000
- ⚠️ **テックリード不足**: 木村のリード経験が薄い → 前田への変更を推薦
- ✅ **スキルカバレッジ**: Python / RAG / Azure すべてカバー
- ✅ **シナジー**: 木村 ↔ 長谷川（PJ-B で共同実績あり）
```

---

## 7. Main Agent のツール設計

Main Agent は Cosmos DB を直接読まず、サブエージェントを呼ぶ口と概要取得ツールだけを持つ。

| ツール | 役割 |
|---|---|
| `list_all_members()` | メンバー一覧・概要把握 |
| `list_all_projects()` | プロジェクト一覧・概要把握 |
| `get_project_detail(project_id)` | プロジェクト基本情報取得 |
| `find_members_by_skill(skill)` | スキルでメンバー検索 |
| **`find_available_members(date_from, date_to?)`** | 指定期間に稼働アサインがないメンバーをDB集計で返す（アサイン提案の第一ステップ） |
| **`ask_user_clarification(question)`** | 不明点・選択肢がある場合にユーザーへ逆質問する。回答が返るまで処理を止める |
| **`invoke_conversation_agent(project_id_or_member_id, question, date_from?, date_to?)`** | 会話分析SA に委譲（Slack + 会議） |
| **`invoke_task_agent(project_id_or_member_id, question)`** | タスク分析SA に委譲 |
| **`invoke_member_profiler(member_id, project_context)`** | MemberProfilerAgent に委譲（個人深掘り） |
| **`invoke_team_evaluator(member_ids, project_id)`** | TeamEvaluatorAgent に委譲（チーム評価） |

### Main Agent システムプロンプトの方針

```
あなたは人材配置と組織分析を行うオーケストレーターエージェントです。

【逆質問のルール】
質問に対して前提が不足している・複数の解釈がありうる場合は、
推測で進めずに ask_user_clarification を呼んでユーザーに確認する。
例: 対象プロジェクトが特定できない / 期間が不明 / 「優秀な人」の軸が不明確
ただし、明らかに回答できる質問には使わない（過剰な確認はしない）。

【アサイン提案モードの必須手順】
アサイン提案に関する質問（「誰を入れるべきか」「チームを組んで」等）は以下の順で進める。

1. find_available_members(date_from, date_to) → 稼働アサインのない候補を取得
2. find_skill_gaps(project_id) → PJに何のスキルが必要かを確認
3. 候補の中からスキルが合う人を invoke_member_profiler で深掘り（全員でなく必要スキルに絞る）
4. プロファイル結果を元にチームドラフトを組む（役割・コストバランスを考慮）
5. ドラフトが固まったら invoke_team_evaluator にドラフトを渡してレビューを依頼（1回のみ）
6. レビューで問題が指摘されたらドラフトを修正し、最終提案をユーザーに提示
   問題なければそのまま提示

→ 稼働中のメンバーをアサイン候補に含めてはいけない。

【サブエージェントの使い分け】
- 「誰が何を担当したか」「スキルの深さ」「貢献度」→ タスク分析エージェントに委譲
- 「発言傾向」「リーダーシップ」「コミュニケーションスタイル」「特定テーマへの貢献」→ 会話分析エージェントに委譲（Slack・会議両方を見る）
- 「特定人物をもっと深く知りたい」→ MemberProfilerAgent に委譲
- 「チームとして機能するか・コストは妥当か」→ TeamEvaluatorAgent に委譲
- 両方の情報が必要な質問（「総合的に最も優秀なのは誰？」等）→ 複数のSAを呼んで統合する

【統合のルール】
- サブエージェントの結果をそのまま並べるのではなく、質問に対する最終的な判断・推薦を述べる
- 根拠はサブエージェントの分析結果を引用する形で示す
```

---

## 8. 実装構成

```
agents/
├── orchestrator.py                   ← Main Agent（invoke_* 4本を追加）
├── sub_agents/
│   ├── conversation_analysis.py      ← 会話分析サブエージェント（Slack + 会議）
│   ├── task_analysis.py              ← タスク分析サブエージェント
│   ├── member_profiler.py            ← MemberProfilerAgent
│   └── team_evaluator.py             ← TeamEvaluatorAgent
├── plugins/
│   ├── slack_plugin.py               ← 【新規】get_slack_speaker_counts / get_project_slack_messages / get_member_slack_messages
│   ├── meeting_plugin.py             ← get_project_meetings / get_member_meetings（full_text込み）
│   └── contribution_plugin.py        ← get_project_tasks / get_member_task_stats（description込み）
└── prompts/
    ├── conversation_analysis.txt     ← 会話分析SA 用システムプロンプト
    ├── task_analysis.txt             ← タスク分析SA 用システムプロンプト
    ├── member_profiler.txt           ← MemberProfilerAgent 用システムプロンプト
    ├── team_evaluator_assignment.txt ← TeamEvaluator アサインモード用
    └── team_evaluator_skill.txt      ← TeamEvaluator スキル分析モード用
```

---

## 9. コンテキスト予算

| エージェント | 主なデータ量 | 目標上限 |
|---|---|---|
| 会話分析SA | Slack メッセージ（期間フィルタ済み）+ 会議 full_text | ~10K tokens |
| タスク分析SA | タスク全件（name + description + result_note × M件） | ~8K tokens |
| MemberProfilerAgent | 1名分（Slack + 会議 + タスク） | ~6K tokens |
| TeamEvaluatorAgent | チームメンバー数分のシナジー/コストデータ | ~4K tokens |
| Main Agent | 各SAのサマリー結果 + プロジェクト概要 | ~12K tokens |

> Slack メッセージは期間フィルタ（`date_from` / `date_to`）で件数を制御する。
> 指定なしの場合は直近3ヶ月をデフォルトとする。
> 会議 full_text が超過する場合は直近N件に絞るパラメータを追加する。
