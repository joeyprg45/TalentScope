# プロジェクト引き継ぎドキュメント

> 最終更新: 2026-05-28
> 審査期間: 2026-06-02 〜 2026-06-18

---

## プロジェクト概要

| 項目 | 内容 |
|------|------|
| プロジェクト名 | TalentScope |
| 目的 | Agentic AI を使った人材配置・組織分析ソリューション（Zenn ハッカソン参加） |
| GitHub | https://github.com/joeyprg45/TalentScope.git |
| デプロイ先 | Azure Container Apps |

---

## 確定済み デプロイ戦略

### コンテナ構成（1コンテナ方式）

```
[ Azure Container App (port 80) ]
    nginx
     ├─ /api/*  →  FastAPI (uvicorn, port 8000)
     └─ /*      →  Next.js standalone (node,  port 3000)
```

- Next.js は `output: 'standalone'` モードでビルド
- `supervisord` で uvicorn と node の2プロセスを管理
- nginx が port 80 で受けて内部ルーティング
- CORS 設定は nginx を経由するため同一オリジンになり、実質不要になる

### CI/CD フロー

```
push to main (GitHub)
  → GitHub Actions
    → docker build (multi-stage)
    → ACR push (ACR Admin Key で認証)
    → az containerapp update (※ 後述の未解決問題あり)
```

---

## Azure リソース状況

| リソース | 名前 | 状態 |
|---------|------|------|
| Resource Group | `TalentScope-rg` | 作成済み |
| Container Registry (ACR) | `TalentscopeRegistry` | 作成済み |
| ACR login server | `talentscoperegistry.azurecr.io` | 確認済み |
| Container Apps Environment | 名前未確認 | 作成済み |
| Container App (本体) | 未決定 | **未作成** |

---

## GitHub Secrets 状況

| Secret 名 | 内容 | 状態 | 問題 |
|-----------|------|------|------|
| `ACR_SECRETS` | username:password 混在形式 | 登録済み | **形式が不正。分割が必要** |
| `ACR_USERNAME` | ACR の admin ユーザー名 | 未登録 | `ACR_SECRETS` を削除して登録しなおす |
| `ACR_PASSWORD` | ACR の admin パスワード | 未登録 | 同上 |
| `AZURE_CREDENTIALS` | Service Principal JSON | 登録不可 | 学校 Azure アカウントの権限制限 |

---

## 未解決問題・ブロッカー

### 1. deploy ステップ（最重要）

GitHub Actions の `az containerapp update` は Azure 認証（Service Principal）が必要。
学校アカウントでは Service Principal 作成不可のため、**deploy ステップの代替案が未決定**。

候補:
- **A. ACR Webhook → Container App 自動更新**  
  Container App 側でACRの特定タグ更新を監視して自動リビジョン作成。GitHub Actions は ACR push のみ担当。  
  → Portal で設定可能かどうか確認が必要。
- **B. ローカルから手動デプロイ**  
  `az containerapp update` をローカル端末から実行（az login → 対話認証）。  
  → 審査期間中の更新のたびに手動が必要。
- **C. Azure Container Apps GitHub Actions (OIDC)**  
  Workload Identity Federation で Service Principal 不要で GitHub から Azure 操作可能。  
  → Entra ID でのアプリ登録が必要。学校アカウントで可能か要確認。

**判断が必要**: A / B / C のどれを採用するか次のセッションで決定すること。

### 2. ACR_SECRETS の形式問題

現在 `ACR_SECRETS` に `username:password` が1つのシークレットとして入っている。
GitHub Actions では `username` と `password` を別々のシークレットとして渡す必要があるため、
`ACR_USERNAME` と `ACR_PASSWORD` に**登録しなおす必要がある**。

手順:
1. GitHub → Settings → Secrets → `ACR_SECRETS` を削除
2. `ACR_USERNAME` を新規追加（ACR の admin ユーザー名）
3. `ACR_PASSWORD` を新規追加（ACR の admin パスワード）

ACR のユーザー名・パスワードは Azure Portal → `TalentscopeRegistry` → Access keys で確認できる。

### 3. Container App 名・Environment 名の未確認

Container App インスタンスがまだ作成されていない。
Container Apps Environment の名前も未確認。
deploy.yml 作成前に以下を確認・決定する:

- Container App 名: `talentscope`（候補）
- Container Apps Environment 名: Portal で確認

---

## 作成が必要なファイル（すべて未作成）

| ファイル | 内容 | 優先度 |
|---------|------|--------|
| `Dockerfile` | multi-stage: Next.js standalone + Python + nginx + supervisord | 最高 |
| `nginx.conf` | `/api/*` → 8000、`/*` → 3000 のルーティング | 最高 |
| `supervisord.conf` | uvicorn と node の2プロセス管理 | 最高 |
| `docker-entrypoint.sh` | 起動スクリプト | 最高 |
| `.dockerignore` | .venv / .env / node_modules 等を除外 | 高 |
| `.github/workflows/deploy.yml` | build + push (+ deploy は未解決問題解決後) | 高 |

---

## コードの変更が必要な箇所

| ファイル | 変更内容 | 理由 |
|---------|---------|------|
| `frontend/next.config.ts` | `output: 'standalone'` を追加 | 1コンテナでの standalone モードビルドに必要 |
| `api/main.py` | `allow_origins` に本番 URL を追加 | Container App の URL が確定したら追加（nginx 経由なら実質不要だが念のため） |

---

## 技術スタック（参考）

| 項目 | 内容 |
|------|------|
| バックエンド | Python 3.12 / FastAPI / uvicorn / Semantic Kernel |
| フロントエンド | Next.js 16 / App Router / TypeScript / Tailwind CSS |
| DB | Azure Cosmos DB（4コンテナ: members / projects / meetings / slack_channels） |
| LLM | Azure OpenAI (gpt-4o) |
| パッケージ管理 | uv (`pyproject.toml`) |

---

## 環境変数（.env キー一覧）

本番環境では以下を Container Apps の Secrets / Environment Variables に設定する。

```
AZURE_OPENAI_ENDPOINT
AZURE_OPENAI_KEY
AZURE_OPENAI_DEPLOYMENT_NAME
COSMOS_ENDPOINT
COSMOS_KEY
COSMOS_DB_NAME
SLACK_BOT_TOKEN
NOTION_TOKEN
```

---

## 実装の進捗状況

### 完了済み
- Cosmos DB 4コンテナ + デモデータ投入（メンバー10名 / PJ3本 / 議事録9件 / Slack13ch）
- FastAPI バックエンド（全ルーター実装済み）
- Next.js フロントエンド（チャット UI / ホーム / レポートページ）
- Semantic Kernel エージェント（Main Agent + 基本プラグイン群）

### 未完了（実装計画: docs/implementation-plan.md 参照）
- サブエージェント4本（会話分析 / タスク分析 / MemberProfiler / TeamEvaluator）
- SlackPlugin 新規作成
- Dockerfile + 関連設定ファイル群
- GitHub Actions ワークフロー

---

## 関連ドキュメント

- [docs/implementation-plan.md](implementation-plan.md): 実装計画書（唯一の規約）
- [docs/sub-agent-design.md](sub-agent-design.md): サブエージェント設計書
- [pyproject.toml](../pyproject.toml): Python 依存パッケージ
