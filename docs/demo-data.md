# TalentScope デモデータ概要

## メンバー一覧（10名）

| 名前 | 役職 | 経験年数 | 月次コスト | 主要スキル | 参加PJ |
|---|---|---|---|---|---|
| 田中 誠 | テックリード | 7年 | ¥900,000 | Python, アーキテクチャ設計, PM, Azure | PJ-A, PJ-B |
| 前田 彩 | シニアAIエンジニア | 5年 | ¥750,000 | Python, Semantic Kernel, LLM, RAG, Azure OpenAI | PJ-A |
| 小林 拓海 | バックエンドエンジニア | 3年 | ¥600,000 | Python, Azure, CosmosDB, FastAPI | PJ-A |
| 佐藤 健太 | フロントエンドエンジニア | 2年 | ¥500,000 | React, TypeScript, Next.js | PJ-A |
| 山田 花奈 | MLOps/DevOpsエンジニア | 4年 | ¥650,000 | Azure ML, Docker, GitHub Actions, CI/CD | PJ-A, PJ-B |
| **中村 大樹** ★ | **データサイエンティスト** | **3年** | **¥630,000** | **Python, LightGBM, 画像認識, PyTorch, Azure ML** | **PJ-B** |
| 木村 大介 | AIエンジニア | 4年 | ¥680,000 | Python, LLM fine-tuning, RAG, Transformers, Azure OpenAI, NLP | なし |
| 原田 京子 | AIエンジニア | 3年 | ¥630,000 | Python, PyTorch, 強化学習, シミュレーション, Azure ML, 最適化アルゴリズム | なし |
| 長谷川 拓 | AIエンジニア | 5年 | ¥730,000 | Python, PyTorch, 音声認識, Whisper, TTS, マルチモーダルLLM, Speech API | なし |
| 岡田 あかり | AIエンジニア | 4年 | ¥660,000 | Python, MLflow, Kubeflow, 特徴量エンジニアリング, AutoML, Azure ML, scikit-learn | なし |

> 木村・原田・長谷川・岡田の4名は画像認識・DICOM・ViT系スキルなし → 中村大樹がPJ-Cの最適候補であるデモ設計を維持。

---

## プロジェクト構成（3本）

### PJ-A: 次世代 LLM Agent 基盤開発
- **期間**: 2026-04-01 〜 2026-07-31
- **ステータス**: 進行中
- **メンバー**: 田中（TL）/ 前田（AI）/ 小林（BE）/ 佐藤（FE）/ 山田（MLOps）
- **スキル**: Python, Semantic Kernel, Azure OpenAI, RAG, CosmosDB
- **タスク**: 8件（完了4 / 進行中2 / 未着手2）
- **議事録**: 4件（スプリントMTG・1on1）

### PJ-B: 大手EC向けレコメンドエンジン開発
- **期間**: 2026-02-01 〜 **2026-07-25**（← PJ-Aとほぼ同時終了）
- **ステータス**: 進行中（終盤）
- **メンバー**: 田中 誠（TL/PM）/ 中村 大樹（MLリード）/ 山田 花奈（MLOps）
- **スキル**: Python, 協調フィルタリング, LightGBM, Azure ML, MLOps
- **タスク**: 7件（完了4 / 進行中2 / 未着手1）
- **議事録**: 5件 ← **中村の発言量変化がデモキー**

### PJ-C: 医療画像AI診断支援システム
- **期間**: 2026-08-01 〜 2026-11-30
- **ステータス**: 計画中
- **メンバー**: **未定**（← エージェントにアサイン提案させる）
- **スキル**: Python, 画像認識, CNN, Vision Transformer, PyTorch, Azure, DICOM処理
- **タスク**: 5件（全て未着手・担当者未定）

---

## デモシナリオ: 中村大樹のテックリード推薦

### 「医療画像AIのアサインを提案して」と入力したとき

エージェントが返すべき推薦根拠:

**根拠①: tweet_nakamura（Slack個人vlog）**
- 2026-04-22: Kaggle SIIM-ISIC（皮膚がん分類）で銀メダル 🥈
- 2026-06-15: Kaggle RSNA Pneumonia（胸部X線）で銀メダル 🥈
- 医療画像AI分野での実証済みスキルが tweet から読み取れる

**根拠②: PJ-B 議事録（5回の発言変化）**

| 回 | 日付 | 中村の役割 |
|---|---|---|
| 第1回 | 2026-02-10 | 聴衆のみ（「よろしくお願いします」） |
| 第2回 | 2026-03-15 | 初提案（「LightGBMを試したい」） |
| 第3回 | 2026-04-20 | 複数提案・根拠あり（「先週の検証結果から〜」） |
| 第4回 | 2026-05-25 | アジェンダ設定・議論リード |
| 第5回 | 2026-06-30 | **田中「次のPJでテックリードを担ってほしい」** |

**根拠③: アサインカレンダー**
- PJ-A終了: 2026-07-31
- PJ-B終了: 2026-07-25
- → 中村・山田は8月1日から確実に空き → PJ-C（8/1〜）に配置可能

---

## デモ入力例と期待レスポンス

| 入力 | 期待するエージェント回答 |
|---|---|
| 「中村大樹のスキルを分析して」 | Kaggle銀メダル×2・画像AI専門性・リーダー適性の成長を含むレポート |
| 「医療画像AIのアサインを提案して」 | 中村をTLに推薦。tweet・議事録・カレンダーを根拠として明示 |
| 「8月に誰が空いてますか？」 | PJ-A/B 7月末終了 → 中村・山田など8月以降フリーと回答 |
| 「コスト重視でアサインして」 | 必要スキルを最低コストでカバーするチームを提案 |
| 「育成重視でアサインして」 | 佐藤・小林をストレッチ機会として含む提案 |

---

## Slackチャンネル構成（全13チャンネル）

### 個人vlog チャンネル（tweet_*）

| チャンネル | ID | 投稿者 | 内容 |
|---|---|---|---|
| `tweet_nakamura` ★ | C0B5VR6BZH8 | 中村 大樹 | Kaggle参加記録・銀メダル2枚・ViT研究の様子（8件） |
| `tweet_yamada` | C0B5XLA6925 | 山田 花奈 | MLOps自動化・Docker最適化・Kubernetes（8件） |
| `tweet_tanaka` | C0B5XLA3AGZ | 田中 誠 | 1on1での中村の成長観察・テックリード推薦の記録（5件） |
| `tweet_maeda` | C0B4TB12T7D | 前田 彩 | LLM/RAG技術調査（12件） |
| `tweet_kobayashi` | C0B51HALTNV | 小林 拓海 | Azure/DB設計メモ（12件） |
| `tweet_sato` | C0B4JGP19NX | 佐藤 健太 | React/Next.js学習記録（11件） |
| `tweet_kimura` | C0B6Q7YBTR6 | 木村 大介 | LLM fine-tuning・RAG実装の日常（5件） |
| `tweet_harada` | C0B5VUTFHR8 | 原田 京子 | 強化学習・シミュレーション環境構築（5件） |
| `tweet_hasegawa` | C0B5SHGNVNZ | 長谷川 拓 | 音声AI・Whisper活用・マルチモーダルLLM研究（5件） |
| `tweet_okada` | C0B5PHWDL5R | 岡田 あかり | ML実験管理・MLflow構築・AutoML実験（5件） |

### プロジェクト・全社チャンネル

| チャンネル | ID | 内容 |
|---|---|---|
| `all-abctechnologies` | C0B4UBF7JTE | 全社共有（8件） |
| `proj-llm-agent-infra` | C0B5C36EL02 | PJ-A進捗（6件） |
| `proj-ec-recommend` | C0B6Q4ARV6C | PJ-B進捗・中村の貢献が見えるチャンネル（10件） |
| `proj-medical-imaging-ai` | C0B5PE8TMQB | PJ-C計画中・スキル要件・メンバー選定進行中（3件） |

---

## シードスクリプト実行順序（✅ 全て実行済み）

```bash
# 1. Notion: 中村大樹追加 + PJ-A期間更新 + PJ-B スキーマ+データ投入 + PJ-C タスクDB作成
uv run python scripts/seed_demo_full.py

# 2. Notion: PJ-B に田中誠追加 + PJ-B ページ更新 + PJ-C スキーマ整備
uv run python scripts/seed_pjb_pjc_fix.py

# 3. Notion: 新規AIエンジニア4名をハブメンバーDBに追加
uv run python scripts/seed_new_members.py

# 4. Slack: デモ会話投入（tweet_nakamura / tweet_yamada / tweet_tanaka / proj-ec-recommend / proj-medical-imaging-ai）
uv run python scripts/seed_slack_demo_v2.py

# 5. Ingest 実行（Notion + Slack → CosmosDB 同期）
uv run python -m ingest.run_ingest
```

## デモ前確認チェックリスト

- [ ] `uv run python -m ingest.run_ingest` を再実行してCosmosDBを最新状態に同期
- [ ] API起動: `uv run uvicorn api.main:app --reload --port 8000`
- [ ] Frontend起動: `cd frontend && npm run dev`
- [ ] 「医療画像AIのアサインを提案して」→ 中村大樹が推薦されることを確認
- [ ] 推薦根拠: ①tweet_nakamura Kaggle銀メダル ②PJ-B議事録のリーダー成長 ③8月空き確認
