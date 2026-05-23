# TalentScope 実装計画

> このドキュメントは「唯一の実装計画書」。アイデアが固まるたびに更新する。
> 破棄したアイデアは消す。最終的に一枚の完成した計画書になる状態を目指す。
>
> 最終更新: 2026-05-23

---

## 1. プロダクト概要

あらゆる人事データをため込み、それを参照しながら情報を返す **Agentic AI（人事エージェント）**。

メインUIは **チャット形式**。ベースは ChatGPT のように保存データを参照しながら何でも答える汎用チャット。
画面上のボタンで以下のモードに切り替えられる。

| モード | 説明 | レポート |
|---|---|---|
| **💬 チャット（ベース）** | メンバー・プロジェクト・MTG・Slack データを参照して質問に何でも回答。モード指定なし | なし |
| **👤 個人スキル分析** | 対象メンバーのスキルシート・貢献度・MTG性格傾向をサイドパネルにレポート出力。Markdown でダウンロード可 | 個人スキルレポート |
| **📋 アサイン提案** | 対象**プロジェクト**に誰を・どの役割で・どのコスト感でアサインすべきかをチーム単位で提案。サイドパネルにレポート出力・Markdown ダウンロード可 | アサイン提案レポート |

各モードはボタン押下でシステムプロンプトとワークフローが切り替わる。ベースチャットは常時利用可能。

### 解決する業務課題（審査基準: ビジネスインパクト）
- 個人のスキル・貢献度・適性が「人の頭の中」「散らばったツール」に閉じている
- 次プロジェクトへのアサインが、勘と属人的な記憶で決まっている
- 1on1やMTGの文字起こしが活用されず死蔵されている

---

## 2. システム全体像（想定アーキテクチャ）

```
[外部データソース]        [取り込み/整形]         [蓄積]            [エージェント]      [UI]
 Slack  ──┐
 Notion ──┴─▶ Ingest層 ──▶ 構造化/要約 ──▶  4つのDB  ──▶  人事エージェント ──▶ チャットUI
                              (LLM)         (Cosmos DB)     (RAG + Tool呼出)    (2モード)
```

- Azure実行基盤（App Service / Container Apps / Functions のいずれか）に載せる ※後で確定
- Microsoft AI技術（Azure OpenAI / AI Foundry 等）を1つ以上利用 ※後で確定

### 重要原則: 「取り込み」と「検索」を分離する
- **取り込み(Ingest)**: 外部API（Notion等）を再帰クロールして Cosmos DB に貯める。
  一度きり、またはバッチ/定期同期で実行。遅くてよい（バックグラウンド）。
- **検索(Query)**: ユーザー質問のたびに実行。検索対象は **Cosmos DB のみ**。
  外部APIは触らない（高速・安定・デモが崩れない）。
- → エージェントは Notion を動的検索しない。Notion はあくまで入力ソース。

---

## 3. 外部アプリ連携

| サービス | 用途 | 認証 |
|---|---|---|
| Slack | 技術会話・チャンネルログの取得 | Bot Token (`.env`) |
| Notion | メンバー情報・プロジェクト・タスク・MTG文字起こし | Integration Token (`.env`) |

> Jira は廃案（Notionでタスク管理を一本化）。詳細は廃案メモ参照。
> APIキーは `.env` で管理（git管理外）。本ドキュメントには記載しない。

---

## 4. 機能一覧

### 4.1 スキルシート作成（個人データ）
- **インプット:** Notionのタスク実行結果、Slackの技術会話、MTG/1on1の文字起こし
- 基本情報は必ず**構造化データ**として保持する（後述の個人DB）

### 4.2 プロジェクト貢献度分析
- **インプット:** NotionのタスクDB（実行結果・ストーリーポイント）

### 4.3 個人能力・性格分析（MTGベース）
- **インプット:** MTG/1on1の文字起こし（Notion）→ Ingest時にLLMで事前分析・構造化済み
- 分析項目: 施策提案力 / 論理的思考力 / まとめ・ファシリテーション力 / 技術的深度 / 性格傾向
- **実装方針:** チャット・RAGはしない。Ingest時に1件ずつLLMで `member_analyses[]` を生成して保存。クエリ時はフィルターで取得するだけ
- アサイン提案モードでの補助情報としても使用（Agentが `meeting_summaries` を参照）

### 4.4 アサイン提案（アサイン提案モードの中核）
- **問いの単位:** 「**プロジェクト X に誰をアサインすべきか**」（チーム編成の最適化）
- **インプット:** プロジェクト要件（必要スキル・期間）、全メンバーのスキルシート・貢献度・MTG性格分析・アサインカレンダー・コスト情報
- 出力する提案内容（チーム全体で1回出力）:
  1. **推奨チーム構成**: メンバー×役割の組み合わせ（各メンバーの推薦理由つき）
  2. **プロジェクト内役割**: 各メンバーの担当領域・期待タスク
  3. **役職提案**: 本アサインを機に昇格が適切なメンバーのレコメンド
  4. **昇給レコメンド**: 貢献度・スキル成長・チームへの影響度をもとにした昇給推奨コメント（メンバー別）
  5. **プロジェクトコスト試算**: 提案チームの月次コスト × 期間 = 総コスト
- スキルギャップ・チームバランス評価も同時に提示する
- **提案軸（UI ボタンで選択）:**

| 軸 | キー | 概要 | プロンプトファイル |
|---|---|---|---|
| 🎯 能力重視 | `ability` | 必要スキルを最大カバー | `assignment.txt` |
| 💰 コスト重視 | `cost` | 予算内で最もコスト効率のよいチーム | `assignment.txt`（`{axis}` 変数で切替） |
| 🌱 育成・チャレンジ重視 | `growth` | 未経験スキルへのストレッチ機会を設計。シニアアンカー1名+若手中心で構成 | `assignment_growth.txt` |
| 🤝 チームワーク重視 | `synergy` | 過去の協働実績（共同PJ数×2+会議数）が最大のチームを選ぶ | `assignment_synergy.txt` |

### 4.4.1 アサインカレンダー
- 各メンバーが「どのPJに・いつから・いつまで」在籍しているかを管理する
- **用途:** 空き期間の確認（「このメンバーは次のPJに入れる状態か？」）、稼働の二重アサイン防止
- **データの持ち方:** `projects.assignments[]` に各メンバーの参加期間・役割をネストして保持（新コンテナ不要）
  ```json
  "assignments": [
    { "member_id": "kobayashi@abc.com", "role": "テックリード", "start_date": "2026-05-01", "end_date": "2026-06-30" },
    { "member_id": "maeda@abc.com",     "role": "バックエンド",  "start_date": "2026-05-15", "end_date": "2026-06-30" }
  ]
  ```
- **Notion側:** プロジェクトページ冒頭の規約フォーマットに `メンバー:` 行を追加（氏名,役割,開始,終了）
- **Agent側ツール:** `get_member_schedule(member_id)` — 全PJの在籍期間を返す

### 4.4.2 コスト管理
- 各メンバーの月次コスト（月給相当）を `members.monthly_cost` として保持
- **Agent側ツール:** `calc_project_cost(assignments, period)` — チーム × 期間でコスト試算
- **Notion側:** メンバーDBに `月次コスト` 列を追加（数値型）
- コストはチャット内で再計算可能（「もう少し安くして」→ メンバー入れ替え案を再提示）

### 4.5 スキルギャップ分析
- **インプット:** プロジェクトDBの「必要スキル」＋個人スキルシート
- 次プロジェクトに必要なスキルと、現チームの保有スキルを照合して不足を可視化
- チャットで「このプロジェクトに誰が向いてる？」と聞くと不足スキルも一緒に提示

### 4.6 チームバランス最適化
- **インプット:** スキルシート、リーダー適性、アサイン提案
- 個人単位ではなくチーム構成全体を評価（スキル偏り・リーダー不在・経験年数バランス等）
- 「このチーム構成は〇〇が偏りすぎ」「△△スキルの人が不足」といった指摘を提示

### 4.7 Slack能動アクション（Botからの出力）

エージェントが「答える」だけでなく「動く」見せ場。**リアルタイム連携は不要** — 適度なタイミング（バッチ実行 or 明示トリガー）で1回投稿する型にする。デモ安定性と「能動的に動くエージェント」の両立がねらい。

- **個人vlogフィードバック:** 個人チャンネル（`tweet_*`）のvlogを分析し、スキル傾向・成長点のフィードバックをBotがそのチャンネルに投稿。スキル分析モードの出力をSlackにも届ける位置づけ。
- **アサイン時プロジェクト概要通知:** アサイン提案モードでアサインが確定したら、対象プロジェクトのSlackチャンネル（`proj-*`）にプロジェクト概要（目的・必要スキル・期間・メンバー）を投稿。

> **必要権限:** Bot Token に `chat:write`（ペルソナ投稿するなら `chat:write.customize` も）を追加し Reinstall が必要。現状は読み取り専用スコープ（`channels:history` / `channels:read` / `groups:history` / `groups:read` / `users:read`）のみ。
> なお `seed_slack_demo.py` でデモ会話を投入するにも `chat:write` は必要。

---

## 5. データ設計

### 5.1 Notion DB構造（データの入力元）

| Notion 要素 | 主なプロパティ／内容 | 表示ビュー | 用途 |
|---|---|---|---|
| **メンバーDB**（ハブ直下） | 名前 / email / 役職 / スキル / 経験年数 / 一言メモ / **月次コスト** | テーブル | 個人プロフィール・スキルの正規情報・コスト管理 |
| **プロジェクトページ冒頭**（各child_page） | 概要 / 期間 / ステータス / 必要スキル / **メンバー（氏名,役割,開始,終了）** | — | アサイン提案・スキルギャップ・カレンダー管理 |
| **タスクDB**（各プロジェクト直下） | タスク名 / 担当者 / ステータス / ストーリーポイント / 使用スキル / 実行結果・学び | ボード | 貢献度分析・ベロシティ計算 |
| **議事録DB**（各プロジェクト直下） | タイトル / 日付 / 種別 / 参加者 / 本文 | テーブル | リーダー適性・性格分析 |

> 専用のプロジェクトDBは作らない。プロジェクト＝ハブ直下の child_page。詳細は [docs/data-schema.md](data-schema.md)。

### 5.2 Slack チャンネル構造

| 種別 | チャンネル例 | 用途 |
|---|---|---|
| 個人vlog | `#tweet_kobayashi` `#tweet_maeda` `#tweet_sato` | 個人の技術会話・スキル把握 |
| プロジェクト | `#project-llm-agent` 等 | プロジェクト内コミュニケーション |
| 全社 | `#all-abctechnologies` | 全社共有 |

### 5.3 Cosmos DB コンテナ構造（蓄積先）

| コンテナ | パーティションキー | 内容 |
|---|---|---|
| `members` | `/member_id`（email） | メンバープロフィール＋スキルシート＋**monthly_cost**（Notion＋Slack個人vlog統合） |
| `projects` | `/project_id` | プロジェクト概要＋`tasks[]`＋**`assignments[]`**（member_id/role/start_date/end_date） |
| `meetings` | `/meeting_id` | MTG/1on1議事録。全文 + LLM生成の全体要約 + メンバー別能力分析を1ドキュメントに保存 |
| `slack_channels` | `/channel_id` | プロジェクトch・全社chのメッセージ |

> emailをメンバーの正規キーとして全サービス間の名寄せに使う。
> 各ドキュメントの詳細スキーマ・Ingestマッピングは **[docs/data-schema.md](data-schema.md)** が唯一の規約。

---

## 6. フェーズ計画

### ✅ フェーズ0: アイデア固め
- 本ドキュメント作成

### ✅ フェーズ1: 接続検証
- [x] Notion API: 認証通過 / ページ本文取得 / 再帰クロール
- [x] Slack API: 認証通過 / 指定チャンネルのメッセージ取得（発信者名つき）
- [x] Cosmos DB: アカウント作成 → 接続 → CRUD確認
- [x] Azure OpenAI: 接続 → Chat Completion確認

### ▶ フェーズ2: データ投入 → Ingest層実装
1. Notion デモデータ投入
   - [x] スキーマ確定（[docs/data-schema.md](data-schema.md)）
   - [x] `次世代 LLM Agent 基盤開発` ページに新スキーマでデモ投入（`seed_llm_agent_test.py`）
         — メンバー5 / タスク8（ボードビュー）/ 議事録4 / ページ冒頭の基本情報
   - [-] 残り2プロジェクトは省略（1プロジェクトのデモデータで進める）
2. Slack デモデータ投入
   - [x] 書き込みスコープ（`chat:write` / `chat:write.customize`）追加・検証済み
   - [ ] proj-* チャンネル3つ作成（`channels:manage` 無ければ手動）
   - [ ] `seed_slack_demo.py` 実行（デモ会話55件投入）
3. Cosmos DB セットアップ
   - [x] ~~Cosmos DB ネイティブベクトル検索を採用~~ → **廃止**。meetingsはLLM事前分析+構造化保存に変更
   - [ ] `python scripts/setup_cosmosdb.py` 実行（slack_channels 追加のみ。meetings のベクトルポリシーは不要）
4. Ingest層実装（Notion/Slack → Cosmos DB）
   - [x] `ingest/slack_ingest.py` — 個人vlog → members.slack_vlog / proj-*/全社ch → slack_channels
   - [x] `ingest/run_ingest.py` — 全体オーケストレータ
   - [ ] `ingest/notion_ingest.py` — **要修正**: 議事録をチャンク+埋め込みではなく、全文+LLM要約+member_analyses[]として1ドキュメント保存に変更
   - [ ] `python -m ingest.run_ingest` 実行（Slackデモデータ投入後）
5. エージェント実装（Semantic Kernel）— ✅ **完了**
   - [x] `agents/orchestrator.py` — ChatCompletionAgent + FunctionChoiceBehavior.Auto() (ReAct)
   - [x] `agents/plugins/member_plugin.py` / `project_plugin.py` / `contribution_plugin.py` / `meeting_plugin.py`
   - [x] `agents/plugins/team_balance_plugin.py` — チームバランス評価
   - [x] `agents/plugins/synergy_plugin.py` — 協働実績マトリクス（Cosmos DB直接集計）
   - [x] `agents/prompts/` — base_chat / skill_analysis / assignment / assignment_growth / assignment_synergy
   - [x] `agents/report.py` — レポートヘッダ/フッタフォーマッタ

### ✅ フェーズ3（進行中）: チャットUI → Azureデプロイ・仕上げ
- [x] Chat UI: **Chainlit** — 常時チャット対応。自然文インテント検出でスキル分析/アサイン提案を起動
- [x] 個人スキル分析レポート（サイドパネル + Markdownダウンロード）
- [x] アサイン提案レポート 4軸（能力/コスト/育成/シナジー）
- [ ] `ingest/notion_ingest.py` 修正 — 議事録を LLM要約+`member_analyses[]`として保存
- [ ] Slack デモデータ投入（`seed_slack_demo.py`）
- [ ] Azure Container Apps デプロイ
- [ ] Zenn 記事 / 3分デモ動画 / アーキテクチャ図
- 審査期間 2026/6/2〜6/18 に動作可能な状態を維持

---

## 6.5 エージェントアーキテクチャ設計

### 基本方針
- **マルチエージェント構成**。サブエージェントを事前定義し、Orchestratorが必要に応じて起動する。
- **Orchestrator**: ReAct（Reasoning + Acting）パターン。コンテキストを収集した上で、**アサイン提案そのものを自身が生成**する（メインタスク）。
- **サブエージェント**: 個々の分析に特化。DBから取得・分析した結果を構造化して返す役割のみ。

### エージェント構成

```
Orchestrator (ReAct)
│  全サブエージェントの出力をコンテキストとして受け取り、
│  最終的なアサイン提案 / スキルギャップ提示 / チームバランス評価を生成する
│
├── [A] ProjectInfoAgent
│       プロジェクトDBから必要スキル・期間・ステータスを取得・整理
│       Tool: Cosmos DB (projects)
│
├── [B] MemberSkillAgent
│       メンバー1人のスキルシートを構造化して返す
│       Tool: Cosmos DB (members)
│
├── [C] ContributionAgent
│       タスクDB集計から貢献度・ベロシティ・得意領域を返す
│       Tool: Cosmos DB (projects / tasks集計)
│
├── [D] MeetingAnalysisAgent
│       メンバーのMTG参加記録・要約・能力分析を取得して返す
│       Tool: Cosmos DB (meetings) ← フィルター検索のみ。LLM分析はIngest時に完了済み
│
└── [E] TeamBalanceAgent
        提案チーム構成のスキル偏り・リーダー在籍・経験バランスを評価
        Tool: なし（Orchestratorの中間出力を入力に取る）
```

### ReAct ループ（アサイン提案の例）

```
[Thought] プロジェクト要件とメンバー情報が必要
[Action]  ProjectInfoAgent / MemberSkillAgent×N / ContributionAgent×N を並列実行
[Observe] 各構造化データを取得

[Thought] リーダー要件があるためMTG分析も取得する
[Action]  MeetingAnalysisAgent を実行
[Observe] リーダー適性・性格傾向データを取得

[Thought] コンテキストが揃った → アサイン提案を生成（Orchestrator自身が推論）
[Thought] チームバランスを確認する
[Action]  TeamBalanceAgent に提案チームを渡す
[Observe] バランス評価を取得

[Final Answer] 推薦メンバー・理由・不足スキル・チームバランスコメントを返す
```

### Semantic Kernel での実装方針
- サブエージェントは `KernelFunction`（`@kernel_function`）として定義し、Kernelにプラグイン登録
- OrchestratorはSKの `ChatCompletionAgent` + `FunctionChoiceBehavior.Auto()` でReAct相当の動作を実現
- MemberSkillAgent / ContributionAgent はメンバーごとに並列呼び出しする
- MeetingAnalysisAgent のみサブエージェント内でLLM呼び出しあり（自然言語分析が必要なため）。他はDB取得 + 構造化のみ

### ツールの所有原則（重要）
- **Orchestratorのツールはサブエージェントの呼び出し口のみ**。`search_meetings` 等の低レベルCosmosツールはOrchestratorのKernelに登録しない。
- Orchestratorは「何を知りたいか」を自然言語でサブエージェントに渡す。「どうやって取るか（クエリ・ベクトル検索等）」はサブエージェントの責務。
- 例: Orchestratorは `MeetingAnalysisAgent("小林のリーダーシップ言及回数を調べて")` と呼ぶ。`search_meetings()` を直接呼ばない。
- これによりOrchestratorがCosmosの構造・検索実装を知る必要がなくなり、サブエージェントの差し替えも容易になる。

### meetings ドキュメント構造（1会議 = 1ドキュメント）

```json
{
  "id": "meeting_id",
  "meeting_id": "...",
  "project_id": "...",
  "title": "スプリント計画 #3",
  "date": "2026-05-10",
  "type": "スプリント計画",
  "participants": ["kobayashi@abc.com", "maeda@abc.com"],
  "full_text": "（生の議事録テキスト全文）",
  "overall_summary": "スプリントゴールと設計方針を決定。RAGアーキテクチャの採用が合意された。",
  "member_analyses": [
    {
      "member_id": "kobayashi@abc.com",
      "member_name": "小林拓海",
      "proposal_ability": "新しい設計案を2件提案。具体的な実装イメージまで言語化していた",
      "logical_thinking": "懸念点を先に整理してから議論を進める傾向",
      "facilitation": "議題の整理役を担うことが多い",
      "technical_depth": "インフラ・LLM両方に言及。技術的文脈の理解が深い",
      "personality_notes": "慎重派。リスクを先に挙げることが多い"
    }
  ]
}
```

> チャンク分割・ベクトル埋め込みは行わない。Ingest時に `gpt-4o` で `overall_summary` と `member_analyses[]` を生成して保存する。エージェントはフィルター（`project_id` / `participants` contains）で取得するだけでよい。

### MCPについての方針
- **MCPは使わない**。Cosmos DBアクセスはすべて SK KernelFunction（Pythonの関数）として直接実装する。
- Notion / Slack も Ingest時は直接API呼び出し（MCPサーバーを立てる必要なし）。
- MCP採用の条件: 外部サービスが公式MCPサーバーを提供していて、かつその採用にメリットがある場合のみ検討。現時点では不要。

---

## 6.6 ツール設計（KernelFunction一覧）

Cosmos DBへのアクセスはすべて `@kernel_function` で実装し、各エージェントのKernelにプラグイン登録する。

### Orchestratorが持つツール

| ツール | 概要 |
|---|---|
| `list_all_members()` | 全メンバーの概要一覧を返す。誰を分析するか判断するために使う |
| `list_all_projects(status?)` | 全プロジェクト一覧（必要スキル・ステータス含む） |

### [A] ProjectInfoAgent のツール

| ツール | 概要 |
|---|---|
| `get_project_detail(project_id)` | 必要スキル / 期間 / assignments[] / 概要を返す |
| `list_all_projects(status?)` | 全プロジェクト一覧（Orchestratorと共有） |

### [B] MemberSkillAgent のツール

| ツール | 概要 |
|---|---|
| `list_all_members()` | 全メンバーの概要一覧（Orchestratorと共有） |
| `get_member_detail(member_id)` | スキル詳細 / 役職 / monthly_cost / Slack要約を返す |
| `find_members_by_skill(skill_name)` | 特定スキルを持つメンバーを絞り込む |
| `get_member_schedule(member_id)` | 全PJの在籍期間（start_date〜end_date）を返す。空き期間確認に使う |

### [C] ContributionAgent のツール

| ツール | 概要 |
|---|---|
| `get_member_task_stats(member_id)` | プロジェクト別貢献度 / SP合計 / 完了率 / 得意タスク傾向 |
| `get_project_tasks(project_id)` | タスク一覧 + 担当者 + 実行結果・学び |
| `calc_project_cost(member_ids, project_id)` | 提案チームの月次コスト合計 × PJ期間 = 総コスト試算 |

### [D] MeetingAnalysisAgent のツール

| ツール | 概要 |
|---|---|
| `get_member_meeting_analyses(member_id)` | そのメンバーが参加した全MTGの `member_analyses` エントリを集約して返す。施策提案力・論理思考・性格傾向などの構造化データ |
| `get_project_meeting_summaries(project_id)` | プロジェクトの全MTG要約一覧（`overall_summary`）を返す |

### [E] TeamBalanceAgent のツール

なし。Orchestratorが生成した「提案チーム構成」をテキストで受け取り、LLMが推論して返す。

### [F] SynergyPlugin のツール（チームワーク重視モードで使用）

| ツール | 概要 |
|---|---|
| `get_collaboration_matrix(member_ids_json)` | 指定メンバーの全ペアについて、過去の共同PJ数・会議参加数・シナジースコア（PJ×2+会議）を集計して返す。Cosmos DBから決定論的に算出（LLM推論なし） |

> シナジースコア式: `shared_projects × 2 + shared_meetings`（PJは会議より長期の関係のため2倍重み）

---

## 6.7 レポート出力設計

### 基本方針
- レポートはチャットとは別の **Chainlit サイドパネル**（`cl.Text(display="side")`）にリアルタイム表示する
- 同時に **Markdown ファイル**（`.md`）を生成し、`cl.File` でダウンロードボタンを提供する
- Markdown は編集しやすく、GitHub / VSCode / Notion などで即開ける。PDF変換にも対応可能
- チャット本体には「レポートを生成しました」+ サマリー1〜2行のみ表示する

### レポートが出力されるタイミング

チャットは常時有効。モードに関係なく任意のメッセージを送れる。

| モード | トリガー |
|---|---|
| 👤 個人スキル分析 | 「佐藤健太のスキルを分析して」など**スキルキーワード+メンバー名**を含む自然文。または 👤ボタン でヒント表示後に入力 |
| 📋 アサイン提案 | 「次世代LLMのアサインを決めて」など**アサインキーワード+プロジェクト名**を含む自然文。または 📋ボタン でヒント表示後に入力 |

> `KEY_AWAIT_STEP` によるチャットブロック機構は廃止。`on_message` 内でキーワード+Cosmos DBエンティティ照合によるインテント検出に変更（2026-05-23）。

### 👤 個人スキルレポート 構成

```markdown
# 個人スキル分析レポート：[氏名]
生成日: YYYY-MM-DD

## 基本情報
- 役職: ...
- 経験年数: ...
- スキル: ...
- 月次コスト: ¥...

## プロジェクト貢献度
| プロジェクト | 役割 | 期間 | SP合計 | 完了率 |
|...

## MTG能力分析
### 施策提案力
（各MTGからの抜粋・総評）

### 論理的思考力
...

### ファシリテーション
...

### 技術的深度
...

### 性格・コミュニケーション傾向
...

## Slack活動傾向
...

## 総評・推奨ネクストステップ
...
```

### 📋 アサイン提案レポート 構成

```markdown
# アサイン提案レポート：[プロジェクト名]
生成日: YYYY-MM-DD　提案軸: 能力重視 / コスト重視

## プロジェクト概要
- 期間: ...
- 必要スキル: ...

## 推奨チーム構成
| メンバー | 役割 | 推薦理由 | 月次コスト |
|...

## コスト試算
- 期間: X ヶ月
- 月次合計: ¥...
- 総コスト: ¥...

## スキルギャップ分析
- カバー済み: ...
- 不足スキル: ...（対策案つき）

## チームバランス評価
...

## 役職・昇給レコメンド
| メンバー | 現役職 | 推奨 | 昇給提案 | 理由 |
|...
```

### Chainlit 実装方針
- レポート生成中は `cl.Step` でサブタスク進捗を表示（「メンバー情報取得中...」「MTG分析中...」）
- 完了後に `cl.Text(content=md_text, display="side", name="レポート")` でサイドパネル表示
- `cl.File(path=tmp_path, name="report.md", display="inline")` でダウンロードボタン追加
- 「提案軸をコスト重視に変更して」→ 同じサイドパネルを新しい内容で上書き更新

---

## 7. 技術スタック

| 項目 | 決定 | 備考 |
|---|---|---|
| 言語 | Python | |
| エージェントFW | Semantic Kernel | Microsoft製。審査要件「Microsoft AI技術」を満たす |
| LLM | Azure OpenAI (gpt-4o) | Semantic Kernel経由で利用 |
| DB | Azure Cosmos DB | 4コンテナ（members / projects / meetings / slack_channels）。NoSQL |
| データ入力元 | Notion / Slack | Notionがタスク・メンバー・MTGの主データソース |
| Chat UI | Chainlit | ボタン切り替えによるモード選択。ストリーミング対応 |
| Azure 実行基盤 | Azure Container Apps | コンテナデプロイ。スケール0対応でコスト効率よし |

---

## 8. Notion 取り込み設計（フェーズ1検証で判明）

### 検証スクリプト
- `scripts/verify_notion.py` — 接続・トークン有効性・対象種別の検証
- `scripts/dump_notion_page.py` — ページ配下を再帰クロールしてツリー表示

### Notion API の仕様（取り込み実装で踏まえること）
- ページの中身は **ブロックの集合**。`blocks.children.list` は **直下1階層のみ** 返す。
- ブロックが `has_children: true` なら、その block_id で再度 `children.list` を呼ぶと
  中身が取れる。**トグル / 入れ子箇条書き / 表(table_row) / サブページ すべて同じルール**。
- サブページは `child_page` ブロックとして現れる。本文は別途その page_id で取得。
- 1レスポンス最大100ブロック。`has_more` / `next_cursor` でページネーション。
- DBの行ページは、プロパティ(`page.properties`)と本文ブロックが別枠。
- → 「`has_children` なら潜る」1個の再帰関数で全構造を吸い出せる（実装済み: dump_notion_page.py）。
- ハマり: インテグレーションへの **ページ共有設定が必須**（未設定だと404）。

### 方針: Notion 側にデータ構造の規約を定義する
フリーフォームを毎回LLMで解釈するのは不安定・高コスト。骨組みの今のうちに規約を決め、
取り込みを `databases.query()` ベースの確実な処理にする。→ 第5章のNotionDB構造が規約。

---

## 8.5 Slack 取り込み設計（フェーズ1検証で判明）

### 検証スクリプト
- `scripts/verify_slack.py` — 接続・スコープ・対象chのメッセージ取得を検証

### 対象チャンネル
| チャンネル | ID | 用途 |
|---|---|---|
| `all-abctechnologies` | C0B4UBF7JTE | 全社共有 |
| `tweet_kobayashi` | C0B51HALTNV | 小林の個人vlog |
| `tweet_maeda` | C0B4TB12T7D | 前田の個人vlog |
| `tweet_sato` | C0B4JGP19NX | 佐藤の個人vlog |
| `#project-xxx` 等 | 未作成 | プロジェクトチャンネル（フェーズ2で追加） |

### Slack API の仕様（取り込み実装で踏まえること）
- 認証は Bot Token（`xoxb-...`）。`.env` キー名は `SLACK_BOT_OAUTH_TOKEN`。
- 必要な Bot Token Scopes: `channels:read` `groups:read` `channels:history`
  `groups:history` `users:read`。追加後は **Reinstall** が必須。
- メッセージの `user` は **ユーザーIDのみ**。`users.list` で ID→実名(`real_name`)
  辞書を一度作って解決する（毎回 `users.info` はレート制限に当たる）。
- Bot は対象chに **`/invite` で招待が必須**（未参加だと `not_in_channel`）。
- 取得フロー: `conversations.list`（ch解決）→ `users.list`（ID→名前）→
  `conversations.history`（本文）。いずれも `next_cursor` でページネーション。
- ハマり: システムメッセージ（`subtype` が `channel_join` 等）は本文が無い／ノイズなので除外する。
  ただし **Bot投稿のデモ会話は `subtype="bot_message"` になる**（検証済み）。これは除外しない。
  → 除外対象は `channel_join` 等のシステムサブタイプのみ。`bot_message` は取り込む。
- Bot が `username` 上書きで投稿したメッセージは `user=None` / `username=ペルソナ名` / `bot_id` 付き。
  発言者は `username` から取る（検証済み。data-schema.md §7）。

---

## 9. 検証ログ

| 日付 | 対象 | 結果 | メモ |
|---|---|---|---|
| 2026-05-20 | Notion API 接続 | ✅ OK | トークン有効（integration: TalentScope）。ページ「ABC_technologies」取得成功。`scripts/verify_notion.py`。ハマり: ページ共有設定が必須（404） |
| 2026-05-20 | Notion 再帰クロール | ✅ OK | `scripts/dump_notion_page.py` でトグル・入れ子トグル・サブページまで全階層取得を確認 |
| 2026-05-20 | Slack API 接続 | ✅ OK | `scripts/verify_slack.py`。team: ABC_technologies / bot: humanresourceagent。4ch から発信者名つきでメッセージ取得確認。ハマり: スコープ追加→Reinstall、各chに`/invite`が必須 |
| 2026-05-21 | Cosmos DB | ✅ OK | `scripts/verify_cosmosdb.py`。DB: talentscope / コンテナ3つ作成 / CRUD確認済み |
| 2026-05-21 | Azure OpenAI | ✅ OK | `scripts/verify_azure_openai.py`。gpt-4o-2024-11-20 / Chat Completion確認済み |
| 2026-05-21 | Notion 新スキーマ投入 | ✅ OK | `scripts/seed_llm_agent_test.py`。`次世代 LLM Agent 基盤開発` にメンバー5/タスク8/議事録4を投入。判明: notion-client v3 は `data_sources.*` API、`status`型はオプションをAPI生成不可、`people`型は削除して`rich_text`化 |
| 2026-05-21 | Slack 書き込み権限 | ✅ OK | `chat:write` / `chat:write.customize` 追加・Reinstall済み。ペルソナ投稿→読み直し→削除まで確認。Bot投稿は `subtype=bot_message` / `username`にペルソナ名 |

---

## 廃案メモ

- **Jira連携**: タスク管理をNotionに一本化したため廃案。NotionのタスクDBがベロシティ・貢献度分析の情報源となる。Ingest層のシンプル化が主な理由。
