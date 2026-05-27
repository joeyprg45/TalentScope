# Chat機能 アーキテクチャ概要

## 基本思想

**Chatがメイン。アサイン提案・スキル分析はChatの中の固定スキルの一つ。**

ユーザーはChatを複数作成でき、それぞれ独立した会話履歴・レポートコンテキストを持つ。

---

## データフロー

```
ブラウザ (Next.js)
  └─ useChat.ts (WebSocket クライアント)
       └─ WebSocket /api/chat/ws?session_id=<uuid>
            └─ chat.py (WS ハンドラ)
                 ├─ session_store.py (インメモリ: SessionData)
                 ├─ orchestrator.py  (Semantic Kernel エージェント)
                 └─ Cosmos DB
                      ├─ chat_sessions (会話履歴・トレースログ)
                      └─ reports       (生成済みレポート)
```

---

## 識別子の種類

| 名前 | 生成タイミング | 保存先 | 役割 |
|---|---|---|---|
| `session_id` | WebSocket 接続時（ページリロードごと）| メモリのみ | `SessionData` のキー |
| `chat_id` | 新規Chat作成時 / 初回接続時 | localStorage + Cosmos | Chat単位の永続識別子 |

`session_id` は揮発性。`chat_id` が実際の「Chat」の永続ID。

---

## WebSocket プロトコル（クライアント → サーバー）

| type | ペイロード | 処理内容 |
|---|---|---|
| `load_chat` | `chat_id` | Cosmos から履歴・レポートを復元 |
| `new_chat` | `chat_id` | セッションをリセット、新規Chat開始 |
| `user_message` | `content` | インテント分類 → 各モード処理 |
| `axis_confirm` | `axis`, `original_content` | 提案軸を確定してアサイン提案を実行 |
| `set_active_report` | `report_id` | 編集対象レポートを設定 |

## WebSocket プロトコル（サーバー → クライアント）

| type | 用途 |
|---|---|
| `chat_loaded` | 履歴復元完了・表示メッセージ一覧を返す |
| `chunk` | 通常チャットのストリーミングテキスト |
| `done` | 通常チャット完了 |
| `tool_call` | ツール実行通知（start/done）|
| `report_chunk` | レポート全文（一括送信）|
| `report_done` | レポート生成完了 |
| `axis_prompt` | アサイン提案前の軸選択を促す |
| `error` | エラー通知 |

---

## インテント分類

ユーザーメッセージを受信するたびに LLM で分類する。

| インテント | 条件 | 処理 |
|---|---|---|
| `assignment` | アサイン提案の明確なリクエスト | 軸選択UI (`axis_prompt`) → `chat_batch(ASSIGNMENT)` |
| `skill` | スキル分析レポートのリクエスト | `chat_batch(SKILL_ANALYSIS)` |
| `refine` | レポート修正指示 **かつ** `current_report` が存在 | `chat_batch(ASSIGNMENT)` with 現レポート+修正指示 |
| `chat` | 上記以外（質問・情報収集・雑談） | `chat(BASE_CHAT)` ストリーミング |

---

## サーバーサイドのセッション管理（session_store.py）

```python
@dataclass
class SessionData:
    history: ChatHistory          # SK会話履歴（全ターン蓄積）
    current_report: str | None    # 現在のアサイン提案レポートMarkdown
    current_report_id: str | None # Cosmos reports コンテナのID
    current_axis: str             # 直近の提案軸
```

- `session_id` をキーにインメモリ保持
- ページリロードで `session_id` が変わっても、`load_chat` で Cosmos から復元するため機能は維持される
- `_sessions` はTTLなし（サーバー再起動でクリア）

---

## Cosmos DB スキーマ（chat_sessions コンテナ）

```json
{
  "id": "<chat_id>",
  "title": "<最初のユーザーメッセージ先頭40文字>",
  "display_messages": [
    { "role": "user", "content": "..." },
    { "role": "assistant", "content": "..." }
  ],
  "sk_history": [
    { "role": "user", "content": "..." },
    { "role": "assistant", "content": "..." }
  ],
  "current_report_id": "<reports コンテナのID or null>",
  "current_axis": "ability",
  "trace_log": [ ... ],
  "created_at": "ISO8601",
  "updated_at": "ISO8601"
}
```

`display_messages`: UI表示用（レポート生成時はサマリーのみ記録）  
`sk_history`: LLMに渡す会話履歴（レポート本文を含む完全版）  
`trace_log`: AIの思考過程ログ（開発者用、後述）

---

## 会話履歴の保持ポリシー

- `session.history`（SK ChatHistory）にすべてのターンが蓄積される
- レポート生成時も `session.history` を引き継ぎ、生成後はレポート全文がassistantメッセージとして追記される
- **トレードオフ**: 全履歴を渡すことで文脈が維持されるが、長期チャットではトークン数が増大する
- **対処**: 定期的に「新規チャット」を作成することで履歴をリセットできる

---

## 開発者向けトレースログ

各チャットターンで以下をJSON配列として `trace_log` に記録:

| type | 内容 |
|---|---|
| `user_message` | ユーザーの入力内容 |
| `intent_classification` | 分類に使ったシステムプロンプト・入力・結果 |
| `agent_invocation` | モード・使用システムプロンプト |
| `tool_call` | ツール名・引数・返り値（start/done） |
| `assistant_response` | AIの最終回答テキスト |

UIのChatサイドバー右上のターミナルアイコンから閲覧・ダウンロード可能。

---

## フロントエンド構成

```
ChatProvider (ChatContext.tsx)
  └─ useChat.ts          WebSocketクライアント・状態管理
       └─ ChatSidebar.tsx
            ├─ MessageList.tsx    メッセージ表示
            ├─ MessageInput.tsx   入力欄
            ├─ AssignAxisSelector.tsx  提案軸選択UI
            └─ Dialog（トレースログビューア）
```

`useChat` が返す主要な状態:

| 状態 | 型 | 説明 |
|---|---|---|
| `activeChatId` | `string` | 現在のChat ID |
| `messages` | `ChatMessage[]` | 表示用メッセージ一覧 |
| `status` | `ChatStatus` | WS接続状態 |
| `currentReport` | `ReportData \| null` | 最新のアサイン提案レポート |
| `activeReportTitle` | `string \| null` | 編集対象レポート名 |
| `pendingAssignmentContent` | `string \| null` | 軸選択待ちのメッセージ |
