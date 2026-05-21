# TalentScope データスキーマ設計書

> Ingest層（Notion/Slack → Cosmos DB）が「何を・どんな形で貯めるか」の唯一の規約。
> ソース（Notion/Slack）の構造変更・Cosmosスキーマ変更があるたびに更新する。
>
> 最終更新: 2026-05-21

---

## 1. 全体図

```
[ソース]                          [Ingest層]              [Cosmos DB: talentscope]
                                                          ┌──────────────────────────┐
Notion メンバーDB ───────────┐                            │ members      /member_id  │
Slack  個人vlog (tweet_*) ───┴──▶ 名寄せ・正規化・統合 ──▶ │   + slack_vlog ネスト     │
                                                          ├──────────────────────────┤
Notion プロジェクトページ冒頭┐                            │ projects     /project_id │
Notion タスクDB (各proj) ────┴──▶ プロジェクトに集約 ────▶ │   + tasks[] ネスト        │
                                                          ├──────────────────────────┤
Notion 議事録DB (各proj) ───────▶ チャンク分割＋埋め込み ─▶ │ meetings     /meeting_id  │
                                                          ├──────────────────────────┤
Slack  プロジェクトch ───────┐                            │ slack_channels           │
Slack  全社ch ───────────────┴──▶ メッセージ単位で投入 ──▶ │              /channel_id  │
                                                          └──────────────────────────┘
```

**原則**: Ingest（取り込み）と Query（検索）は分離する。エージェントは Cosmos DB のみを参照し、
Notion/Slack を動的に叩かない（実装計画書 第2章）。

---

## 2. Notion ソース構造（取り込み規約）

Notion 側はこの構造を「規約」として固定する。フリーフォームをLLMで毎回解釈しない。

### Notion 全体構造

```
ABC_technologies（ハブページ）
├── メンバーDB                      … テーブルビュー
├── 次世代 LLM Agent 基盤開発（child_page）
│   ├── （ページ冒頭）プロジェクト基本情報   … 規約フォーマットのテキスト
│   ├── タスクDB                    … ボードビュー（ステータスでグループ化）
│   └── 議事録DB                    … テーブルビュー
├── 面接官AIエージェント（child_page）
│   └── 〃
└── 大手金融向け 予測AIモデル開発（child_page）
    └── 〃
```

> **専用のプロジェクトDBは作らない。** プロジェクト＝ハブ直下の child_page。
> プロジェクトの基本情報は各プロジェクトページの冒頭テキストに書く（§2.2）。

### 2.1 メンバーDB（`ABC_technologies` ハブ直下 / テーブルビュー）

| プロパティ | 型 | 例 |
|---|---|---|
| 名前 | title | 小林 拓海 |
| email | rich_text | kobayashi@abc.com |
| 役職 | select | バックエンドエンジニア |
| スキル | rich_text | `Python, Azure, CosmosDB, FastAPI` （カンマ区切り） |
| 経験年数 | number | 3 |
| 一言メモ | rich_text | インフラからAPIまで幅広く対応。 |

### 2.2 プロジェクト基本情報（各プロジェクトページの冒頭テキスト）

> 専用DBは作らず、各プロジェクトページ（child_page）の**冒頭に規約フォーマットのテキスト**で書く。
> Ingest は `blocks.children.list` でページ直下ブロックを読み、`ラベル: 値` 形式をパースする。
> プロジェクトの一意キー（project_id）は child_page のページIDをそのまま使う。

冒頭ブロックの規約フォーマット（段落 or コールアウト、1行=1項目）:
```
概要: 人事エージェントの基盤となるLLM Agentプラットフォームの開発。
期間: 2026-05-01 〜 2026-06-30
ステータス: 進行中
必要スキル: Python, Semantic Kernel, Azure, RAG
```
- 各行は `ラベル: 値`。ラベルは固定（`概要` / `期間` / `ステータス` / `必要スキル`）。
- 期間は `開始 〜 終了`（区切りは ` 〜 ` または `~` を許容。終了未定なら開始のみ可）。
- **メンバーは書かない** — タスクDBの担当者の和集合から自動算出する（§4.2 `member_ids`）。
- このフォーマット以降の本文ブロックは Ingest では無視（人間用の自由記述として扱う）。

### 2.3 タスクDB（各プロジェクトページ直下 / ボードビュー）

Notion 上は **ボードビュー（ステータスでグループ化）= カンバン**で表示する。

| プロパティ | 型 | 例 |
|---|---|---|
| タスク名 | title | Azure Cosmos DB 接続設計・実装 |
| 担当者 | rich_text | 小林 拓海 （**氏名**） |
| ステータス | select | 未着手 / 進行中 / 完了 |
| ストーリーポイント | number | 5 |
| 使用スキル | rich_text | `Python, Azure, CosmosDB` （カンマ区切り） |
| 実行結果・学び | rich_text | CosmosDB SDKでCRUDを実装… |

- **ステータスは `select` 型**で統一する（`status` 型ではない）。理由は §7 参照。
  ボードビューは `select` 型でもグループ化できるため、`select` で支障ない。
- **担当者は `rich_text`（氏名文字列）で統一**する（`people` 型は使わない）。理由は §7 参照。

### 2.4 議事録DB（各プロジェクトページ直下 / テーブルビュー）

| プロパティ | 型 | 例 |
|---|---|---|
| タイトル | title | スプリント1 キックオフMTG |
| 日付 | date | 2026-05-07 |
| 種別 | select | チームMTG / 1on1 / スプリントレビュー |
| 参加者 | rich_text | `田中 誠, 前田 彩, 小林 拓海` （カンマ区切り氏名） |
| 本文 | rich_text | 田中: 今スプリントのゴールは… |

---

## 3. Slack ソース構造

| 種別 | チャンネル | channel_id | 取り込み先 |
|---|---|---|---|
| 個人vlog | `tweet_kobayashi` | C0B51HALTNV | members（小林）にネスト |
| 個人vlog | `tweet_maeda` | C0B4TB12T7D | members（前田）にネスト |
| 個人vlog | `tweet_sato` | C0B4JGP19NX | members（佐藤）にネスト |
| 全社 | `all-abctechnologies` | C0B4UBF7JTE | slack_channels |
| プロジェクト | `proj-llm-agent-infra` | C0B5C36EL02 | slack_channels |
| プロジェクト | `proj-interviewer-ai` | （実行時取得） | slack_channels |
| プロジェクト | `proj-finance-prediction` | （実行時取得） | slack_channels |

### channel → member マップ（個人vlog用）

| channel | member email |
|---|---|
| tweet_kobayashi | kobayashi@abc.com |
| tweet_maeda | maeda@abc.com |
| tweet_sato | sato@abc.com |

### channel → project マップ（プロジェクトch用）

プロジェクトch名とプロジェクト名は別表記のため、明示マップを持つ。

| channel | プロジェクト名 |
|---|---|
| proj-llm-agent-infra | 次世代 LLM Agent 基盤開発 |
| proj-interviewer-ai | 面接官AIエージェント |
| proj-finance-prediction | 大手金融向け 予測AIモデル開発 |

---

## 4. Cosmos DB ドキュメントスキーマ

DB名: `talentscope` / 4コンテナ構成。

| コンテナ | partitionKey | 内容 |
|---|---|---|
| `members` | `/member_id`（email） | メンバープロフィール + Slack個人vlog |
| `projects` | `/project_id` | プロジェクト概要 + `tasks[]` ネスト |
| `meetings` | `/meeting_id` | 議事録チャンク（RAG用） |
| `slack_channels` | `/channel_id` | プロジェクトch・全社chのメッセージ |

> `verify_cosmosdb.py` は3コンテナ（members/projects/meetings）しか作らない。
> `slack_channels` の追加は Ingest 実装タスクで対応する。

### 4.1 members

```json
{
  "id": "kobayashi@abc.com",
  "member_id": "kobayashi@abc.com",
  "type": "member",
  "name": "小林 拓海",
  "email": "kobayashi@abc.com",
  "role": "バックエンドエンジニア",
  "skills": ["Python", "Azure", "CosmosDB", "FastAPI", "REST API"],
  "years_experience": 3,
  "note": "インフラからAPIまで幅広く対応。CosmosDB設計が得意。",
  "slack_vlog": {
    "channel": "tweet_kobayashi",
    "channel_id": "C0B51HALTNV",
    "posts": [
      { "ts": "1716...", "posted_at": "2026-05-19T10:00:00+09:00", "text": "今日はCosmosDBの..." }
    ]
  },
  "source": { "notion_page_id": "<member-row-page-id>", "synced_at": "2026-05-21T12:00:00Z" }
}
```

- `id` と `member_id` は email と同値（パーティションキー = 主キー）。
- `slack_vlog` は個人vlogが無いメンバーでは省略可（`田中`・`山田` は tweet_* が無い）。

### 4.2 projects（tasks をネスト）

```json
{
  "id": "<notion-project-page-id>",
  "project_id": "<notion-project-page-id>",
  "type": "project",
  "name": "次世代 LLM Agent 基盤開発",
  "overview": "人事エージェントの基盤となるLLM Agentプラットフォームの開発。",
  "required_skills": ["Python", "Semantic Kernel", "Azure", "RAG"],
  "period": { "start": "2026-05-01", "end": "2026-06-30" },
  "status": "進行中",
  "member_ids": ["tanaka@abc.com", "maeda@abc.com", "kobayashi@abc.com"],
  "tasks": [
    {
      "task_id": "<notion-task-page-id>",
      "name": "Azure Cosmos DB 接続設計・実装",
      "assignee": "kobayashi@abc.com",
      "status": "完了",
      "story_points": 5,
      "skills_used": ["Python", "Azure", "CosmosDB", "NoSQL"],
      "result_note": "CosmosDB SDKでCRUDを実装。パーティションキー設計で詰まったが..."
    }
  ],
  "source": {
    "project_page_id": "<notion-project-page-id>",
    "synced_at": "2026-05-21T12:00:00Z"
  }
}
```

- `project_id` / `id` はプロジェクトページ（child_page）のID。
- `name` は child_page のタイトル。`overview` / `period` / `status` / `required_skills` はページ冒頭の基本情報ブロック（§2.2）をパースして取得。
- `member_ids` は `tasks[].assignee` の和集合（重複排除）。
- 貢献度分析・ベロシティ計算はこの `tasks[]` を集計して算出する。

### 4.3 meetings（議事録チャンク / RAG用）

チャンク1個 = 1ドキュメント。議事録1件はチャンク複数に展開される。

```json
{
  "id": "<meeting-page-id>::chunk-0",
  "meeting_id": "<meeting-page-id>",
  "type": "meeting_chunk",
  "project_id": "<notion-project-page-id>",
  "title": "スプリント1 キックオフMTG",
  "date": "2026-05-07",
  "meeting_type": "チームMTG",
  "participant_ids": ["tanaka@abc.com", "maeda@abc.com", "kobayashi@abc.com"],
  "chunk_index": 0,
  "text": "（チャンク本文）",
  "embedding": [/* 1536 floats: text-embedding-3-small */]
}
```

- 同一議事録のチャンクは `meeting_id` を共有 → パーティション内に収まりチャンク取得が高速。
- メタデータ（title/date/meeting_type/participant_ids）は各チャンクに複製して持たせる
  （`search_meetings` がチャンクを直接返すため、再結合不要にする）。

### 4.4 slack_channels（プロジェクトch・全社ch）

メッセージ1件 = 1ドキュメント。

```json
{
  "id": "C0B4UBF7JTE::1716200000.000100",
  "channel_id": "C0B4UBF7JTE",
  "type": "slack_message",
  "channel_name": "all-abctechnologies",
  "channel_kind": "company",
  "project_id": null,
  "speaker": "田中 誠",
  "speaker_id": "tanaka@abc.com",
  "ts": "1716200000.000100",
  "posted_at": "2026-05-20T09:00:00+09:00",
  "text": "みなさん、今週のスプリント計画をお知らせします。..."
}
```

- `channel_kind`: `company`（全社ch）/ `project`（プロジェクトch）。
- `project_id`: プロジェクトch のときのみ設定（channel→projectマップ経由）。全社chは `null`。
- `id` は `channel_id::ts` で一意（再取り込み時の重複防止）。

---

## 5. 名寄せ（最重要ルール）

- **email を全サービス共通の正規キー**にする。
- Notion の「担当者」「参加者」「メンバー」、Slack の発言者は **氏名**で格納されている。
  → メンバーDB（4.1）から `氏名 → email` マップを構築し、すべて email に解決する。
- 解決できない氏名は `null` を入れ、元の氏名を別フィールド（例: `assignee_raw`）に残し、**警告ログを出す**。
  デモデータでは全氏名が解決できる想定（不一致はデータ不整合のサイン）。
- Ingest の実行順序は **members を最初**に取り込む（氏名→emailマップが他コンテナの前提になるため）。

---

## 6. Ingest マッピング表

### Notion メンバーDB → members

| ソース | → | Cosmos | 変換 |
|---|---|---|---|
| 名前 | → | name | そのまま |
| email | → | id / member_id / email | そのまま（正規キー） |
| 役職 | → | role | select値そのまま |
| スキル | → | skills | カンマ区切りを配列化 |
| 経験年数 | → | years_experience | number |
| 一言メモ | → | note | そのまま |

### Notion プロジェクトページ + タスクDB → projects

| ソース | → | Cosmos | 変換 |
|---|---|---|---|
| プロジェクトページID（child_page） | → | id / project_id | そのまま |
| child_page タイトル | → | name | そのまま |
| ページ冒頭 `概要:` 行 | → | overview | ラベル除去 |
| ページ冒頭 `必要スキル:` 行 | → | required_skills | ラベル除去→カンマ区切りを配列化 |
| ページ冒頭 `期間:` 行 | → | period.start / period.end | `開始 〜 終了` をパース |
| ページ冒頭 `ステータス:` 行 | → | status | ラベル除去 |
| （`tasks[].assignee` の和集合） | → | member_ids | 重複排除 |
| タスクDB: タスク名 | → | tasks[].name | そのまま |
| タスクDB: 担当者 | → | tasks[].assignee | 氏名→email解決 |
| タスクDB: ステータス | → | tasks[].status | select値そのまま |
| タスクDB: ストーリーポイント | → | tasks[].story_points | number |
| タスクDB: 使用スキル | → | tasks[].skills_used | カンマ区切りを配列化 |
| タスクDB: 実行結果・学び | → | tasks[].result_note | そのまま |

### Notion 議事録DB → meetings

| ソース | → | Cosmos | 変換 |
|---|---|---|---|
| 議事録ページID | → | meeting_id | そのまま |
| タイトル | → | title | そのまま |
| 日付 | → | date | dateのstart |
| 種別 | → | meeting_type | select値そのまま |
| 参加者 | → | participant_ids | 氏名→email解決して配列化 |
| 本文 | → | text（チャンク分割後） | 結合→チャンク分割→埋め込み |

### Slack → members.slack_vlog / slack_channels

| ソース | → | Cosmos | 変換 |
|---|---|---|---|
| tweet_* メッセージ | → | members.slack_vlog.posts[] | channel→memberマップで対象メンバーに格納 |
| proj-* / 全社ch メッセージ | → | slack_channels ドキュメント | メッセージ単位で投入 |
| メッセージ `username` | → | speaker | ペルソナ氏名（§7参照） |
| 発言者氏名 | → | speaker_id | 氏名→email解決 |
| メッセージ `ts` | → | ts / posted_at | tsはそのまま / posted_atはISO8601変換 |

### スキル文字列の正規化

カンマ区切りスキルは区切り文字 `, ` `,` `、` をすべて区切りとして扱い、
前後空白をトリムして配列化。空要素は除外。

---

## 7. Ingest 時の注意点（ハマりどころ）

- **notion-client v3 の API**: `databases.query()` は廃止。クエリは
  `data_sources.query(data_source_id=...)` を使う。プロパティ定義もデータベースではなく
  **データソース**側にある（`databases.retrieve()` の `data_sources[].id` を取得 →
  `data_sources.retrieve()` / `data_sources.query()`）。書き込みは従来どおり
  `pages.create(parent={"database_id": ...})` でよい。
- **ステータスは `select` 型で統一**: Notion には `select` と `status` の2つの型がある。
  UI でボードを作るとデフォルトで `status` 型になりがちだが、**`status` 型はオプションを
  API で作成・変更できない**（DB を API で再現できなくなる）。タスクDBは `select` 型で作り、
  ボードビューだけ UI で後付けする（ボードは `select` でもグループ化可能）。
  Ingest 側は両対応にしておく（`prop["select"]` / `prop["status"]` どちらも `.name` で値を取る）。
- **担当者は `rich_text` で統一**: `people` 型はデモ用の氏名にひもづく Notion アカウントが
  必要になり、`氏名→email` 名寄せも複雑化する。担当者・参加者は氏名文字列（`rich_text`）で持つ。
- **Slack 発言者**: `seed_slack_demo.py` は `username` オーバーライドで投稿しているため、
  `conversations.history` の `user` フィールドは **Bot のユーザーID**になる。
  発言者名は **メッセージの `username` フィールド**から取得すること。
  `username` が取れない場合（`chat:write.customize` scope なしのフォールバック投稿）は、
  本文先頭の `[氏名] ` プレフィックスをパースする。
- システムメッセージ（`subtype` が `channel_join` / `channel_leave` 等）は **除外**する。
  ただし **Bot投稿のデモ会話は `subtype="bot_message"`**（検証済み）。これは除外してはいけない。
  → 除外は `channel_join` 等のシステムサブタイプのみ。`bot_message` は通常メッセージとして取り込む。
- Notion の議事録「本文」rich_text は長文だと複数のテキストオブジェクトに分割される
  → 全テキストオブジェクトを結合してからチャンク分割する。
- 再取り込みは **upsert**（`id` が一意キーなので冪等）。古いチャンクが残る可能性があるため、
  議事録の再取り込み時は同一 `meeting_id` の既存チャンクを削除してから入れ直す。
- Ingest 実行順序: **members → projects → meetings → slack_channels**
  （氏名→emailマップが後続の前提）。

---

## 8. RAG / ベクトル検索（未決事項）

- **埋め込み対象**: 議事録チャンク（必須）。Slack 個人vlog は任意・後続対応。
- **埋め込みモデル**: `text-embedding-3-small`（1536次元）。Azure OpenAI 経由。
- **チャンク分割**: 1チャンク 256トークン前後を目安（実装計画書のSlackログでも256が好結果）。
  発言（`話者: 本文`）の意味境界を尊重して分割する。
- **未決**: Cosmos DB ネイティブのベクトル検索（`VectorDistance`）を使うか、
  アプリ側でコサイン類似度を計算するか。
  ネイティブ機能を使う場合、`meetings` コンテナは **vector embedding policy 付きで作り直し**が必要
  （既存コンテナにはポリシーを後付けできない）。
  → Ingest 実装タスクで確定する。それまで `embedding` フィールドは配列として保持しておく。
