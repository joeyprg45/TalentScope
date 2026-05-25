"""デモデータ完全版投入スクリプト（改訂版）.

Notion の実構造（2026-05-25 確認）に合わせた改訂:
  - PJ-A: 期間テキスト更新のみ（既に 4/1〜7/31 に更新済みの場合はスキップ）
  - PJ-B: ユーザー手動作成済みの3DB（タスク管理/メンバーDB/議事録）にスキーマ設定＋データ投入
  - PJ-C: 既存ページ下にタスク管理DBを新規作成してデータ投入
  - メンバーDB（ハブ直下）: 中村 大樹を追加

実行:
  uv run python scripts/seed_demo_full.py
"""

import os
import pathlib
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from notion_client import Client

# ============================================================
# 既存の固定ID
# ============================================================
HUB_PAGE_ID  = "2c7c7942de0980aabf7fd79487c2ab01"     # ABC_technologies ハブ
PJ_A_PAGE_ID = "366c7942-de09-8092-9a75-e59d205d94d0" # 次世代 LLM Agent 基盤開発
MEMBER_DB_ID = "367c7942-de09-80e2-b2c9-c70f94d2aa72" # ハブ直下メンバーDB

# PJ-B (大手EC向けレコメンドエンジン開発) — ユーザー手動作成済み
PJ_B_PAGE_ID    = "36ac7942-de09-811f-8814-ca6c340896be"

PJ_B_TASK_DB_ID = "36ac7942-de09-80a9-848d-f526eab8c16a"
PJ_B_TASK_DS_ID = "36ac7942-de09-81d2-8fe4-000b0eab7a21"
# 現状: [status] ステータス, [people] 担当者, [title] 名前

PJ_B_MBR_DB_ID  = "36ac7942-de09-8009-99fb-fc447aff1964"
PJ_B_MBR_DS_ID  = "36ac7942-de09-8102-b584-000b27810cdd"
# 現状: [title] 名前 のみ

PJ_B_MTG_DB_ID  = "36ac7942-de09-80f3-8773-f026cdf125ac"
PJ_B_MTG_DS_ID  = "36ac7942-de09-81c7-aed1-000b1c607e2b"
# 現状: [title] 名前 のみ

# PJ-C (医療画像AI診断支援システム) — ページのみ、DB未作成
PJ_C_PAGE_ID    = "36ac7942-de09-8176-88d2-de8abcd9251b"

# ============================================================
# PJ-A 更新テキスト
# ============================================================
PJ_A_INFO_UPDATED = "\n".join([
    "概要: 人事エージェントの基盤となるLLM Agentプラットフォームの開発。",
    "期間: 2026-04-01 〜 2026-07-31",
    "ステータス: 進行中",
    "必要スキル: Python, Semantic Kernel, Azure OpenAI, RAG, CosmosDB",
    "メンバー: 田中 誠,テックリード,2026-04-01,2026-07-31",
    "メンバー: 前田 彩,AIコアリード,2026-04-01,2026-07-31",
    "メンバー: 小林 拓海,バックエンド,2026-04-01,2026-07-31",
    "メンバー: 佐藤 健太,フロントエンド,2026-04-15,2026-07-31",
    "メンバー: 山田 花奈,MLOps,2026-04-07,2026-07-31",
])

# ============================================================
# 中村 大樹（ハブ直下メンバーDBへの追加）
# ============================================================
NAKAMURA = {
    "名前": "中村 大樹",
    "email": "nakamura@abc.com",
    "役職": "データサイエンティスト",
    "スキル": "Python, 機械学習, LightGBM, 画像認識, PyTorch, Azure ML, 協調フィルタリング",
    "経験年数": 3,
    "月次コスト": 630_000,
    "一言メモ": "Kaggle画像系コンペで銀メダル×2。最近リーダーシップが急成長中。",
}

# ============================================================
# PJ-B: タスク（7件）
# ============================================================
PJ_B_TASKS = [
    {
        "タスク名": "データ探索・前処理パイプライン設計",
        "担当者": "中村 大樹",
        "ステータス": "完了",
        "ストーリーポイント": 5,
        "使用スキル": "Python, pandas, Azure ML",
        "実行結果・学び": "購買データ10GBの前処理パイプラインを実装。欠損処理と特徴量正規化で学習精度が大幅改善。データ品質スコアを導入し信頼性の低いデータを自動フラグする仕組みを作った。",
    },
    {
        "タスク名": "協調フィルタリングベースライン実装",
        "担当者": "中村 大樹",
        "ステータス": "完了",
        "ストーリーポイント": 5,
        "使用スキル": "Python, scikit-learn, 協調フィルタリング",
        "実行結果・学び": "Matrix Factorizationでベースライン構築。Recall@10=0.34を達成。人気商品偏重の問題を確認し、LightGBMへの切り替えを決定。",
    },
    {
        "タスク名": "LightGBM特徴量エンジニアリング",
        "担当者": "中村 大樹",
        "ステータス": "完了",
        "ストーリーポイント": 8,
        "使用スキル": "Python, LightGBM, 特徴量エンジニアリング, SHAP",
        "実行結果・学び": "70種の特徴量を設計。SHAP値で重要度分析し最終的に38特徴量に絞り込み。Recall@10=0.51に改善。カテゴリ別売れ筋ランクが最重要特徴量と判明。",
    },
    {
        "タスク名": "Azure ML パイプライン構築",
        "担当者": "山田 花奈",
        "ステータス": "完了",
        "ストーリーポイント": 5,
        "使用スキル": "Azure ML, Python, MLOps, Docker",
        "実行結果・学び": "学習〜評価〜デプロイまでのパイプラインを自動化。毎朝6時に最新データで再学習が走る。モデルレジストリでバージョン管理も完備。",
    },
    {
        "タスク名": "A/Bテスト設計・評価基盤",
        "担当者": "山田 花奈",
        "ステータス": "進行中",
        "ストーリーポイント": 3,
        "使用スキル": "Python, A/Bテスト設計, Azure",
        "実行結果・学び": "",
    },
    {
        "タスク名": "モデル精度改善（アンサンブル）",
        "担当者": "中村 大樹",
        "ステータス": "進行中",
        "ストーリーポイント": 8,
        "使用スキル": "Python, LightGBM, アンサンブル学習, Kaggle手法応用",
        "実行結果・学び": "",
    },
    {
        "タスク名": "本番デプロイ・パフォーマンス最適化",
        "担当者": "山田 花奈",
        "ステータス": "未着手",
        "ストーリーポイント": 5,
        "使用スキル": "Azure Container Apps, Docker, パフォーマンス最適化",
        "実行結果・学び": "",
    },
]

# ============================================================
# PJ-B: メンバー（2名）
# ============================================================
PJ_B_MEMBERS = [
    {
        "名前": "中村 大樹",
        "email": "nakamura@abc.com",
        "役職": "データサイエンティスト",
        "スキル": "Python, 機械学習, LightGBM, 画像認識, PyTorch, Azure ML, 協調フィルタリング",
        "経験年数": 3,
        "一言メモ": "MLリード。Kaggle銀メダル×2。リーダーシップ急成長中。",
    },
    {
        "名前": "山田 花奈",
        "email": "yamada@abc.com",
        "役職": "MLOps/DevOpsエンジニア",
        "スキル": "Azure ML, Docker, GitHub Actions, CI/CD, Python, Kubernetes",
        "経験年数": 4,
        "一言メモ": "MLOps担当。Azure MLパイプライン構築・モデルドリフト検知が得意。",
    },
]

# ============================================================
# PJ-B: 議事録（5件）— 中村の発言量変化がデモキー
# ============================================================
PJ_B_MEETINGS = [
    {
        "タイトル": "キックオフMTG",
        "日付": "2026-02-10",
        "種別": "チームMTG",
        "参加者": "田中 誠, 中村 大樹, 山田 花奈",
        "本文": """田中: このプロジェクトの目的は、ECサイトのCTRを20%改善するレコメンドエンジンの構築です。期間は2月〜7月の6ヶ月。中村さんにMLコアを、山田さんにMLOpsを担当してもらいます。

中村: よろしくお願いします。データ形式はどのような形式になりますか？

田中: 購買ログCSVがメインです。ユーザーID、商品ID、タイムスタンプの3カラムが基本。詳細は明日共有します。

山田: MLOps側は学習パイプラインをAzure MLで管理します。まずローカルで動く形を作ってから移行するのがいいと思います。

中村: わかりました。まずデータの探索から始めて、来週末までにEDAレポートを出します。

田中: よろしくお願いします。分からないことがあれば遠慮なく聞いてください。""",
    },
    {
        "タイトル": "設計レビュー",
        "日付": "2026-03-15",
        "種別": "チームMTG",
        "参加者": "田中 誠, 中村 大樹, 山田 花奈",
        "本文": """田中: 2週間の探索お疲れ様でした。EDAの結果はどうでしたか？

中村: データ品質は良好で、購買履歴の密度も十分ありました。ただ協調フィルタリングだと「人気商品ばかりを推薦する」問題が出そうで。

田中: よくある課題ですね。どう対処しますか？

中村: 協調フィルタリングの代わりにLightGBMを試してみたいです。商品の特徴量（カテゴリ・価格帯・閲覧回数）を入れることでロングテール商品も拾えると思います。

田中: 面白い発想ですね。ベースラインとして協調フィルタリングを残しながら並行で試してみてください。

山田: Azure MLのパイプライン、どのタイミングで移行しますか？

中村: LightGBMで最初の結果が出た頃でいいですか？2週間後くらいを想定しています。

田中: 了解です。""",
    },
    {
        "タイトル": "実装レビューMTG",
        "日付": "2026-04-20",
        "種別": "チームMTG",
        "参加者": "田中 誠, 中村 大樹, 山田 花奈",
        "本文": """中村: 先週の検証結果を共有します。協調フィルタリングのRecall@10が0.34に対して、LightGBM単体では0.51まで改善しました。

田中: かなり大きな改善ですね。

中村: さらに特徴量を2つ追加したいと思っていて。1つは「ユーザーの直近30日の閲覧カテゴリ分布」、もう1つは「商品の同カテゴリ内の売れ筋ランク」です。先週、2種類のアプローチで実験したところ、閲覧カテゴリ分布の方が効きました。

田中: 根拠がある提案ですね。採用しましょう。

山田: Azure MLパイプライン、移行完了しました。今朝から自動学習が走っています。中村さんのコードをそのまま取り込んで動きました。

中村: ありがとうございます。山田さんのおかげでモデル開発に集中できます。次のスプリントはアンサンブルを試します。最低でも0.60は超えたい。

田中: 目標明確でいいですね。進めましょう。""",
    },
    {
        "タイトル": "中間レビュー",
        "日付": "2026-05-25",
        "種別": "スプリントレビュー",
        "参加者": "田中 誠, 中村 大樹, 山田 花奈",
        "本文": """中村: 今日のアジェンダを整理しました。①現状の精度報告、②残り課題の優先順位決め、③7月末に向けたスケジュール確認の3点です。

田中: いいですね、進めてください。

中村: 現状報告です。LightGBM＋アンサンブルでRecall@10=0.63まで来ました。目標の0.60は超えています。残り課題は2点。A/Bテスト基盤の完成と本番デプロイの最適化です。

田中: 順調ですね。優先度は？

中村: A/Bテスト基盤を先に完成させないと効果測定できないので、これを最優先にしたいです。山田さん、いつ頃完成しますか？

山田: 来週末には終わります。

中村: では、6月中旬からA/Bテスト開始で、7月中に結果を出してプロジェクト完了にしたいと思います。

田中: 中村さん、プロジェクトの進行管理もできるようになってきましたね。このまま進めましょう。""",
    },
    {
        "タイトル": "最終レビュー",
        "日付": "2026-06-30",
        "種別": "スプリントレビュー",
        "参加者": "田中 誠, 中村 大樹, 山田 花奈",
        "本文": """中村: 最終結果を報告します。A/Bテスト結果、レコメンドクリック率が従来比で23%改善しました。Recall@10=0.67まで到達、目標を大きく上回りました。

田中: 素晴らしいですね。目標の20%改善を達成した。

中村: 山田さんのMLOpsの仕組みがあってこそです。モデルの更新自動化が効いて、6月に入ってからさらに精度が上がりました。

山田: ありがとうございます。中村さんのモデルの品質が高かったから維持できたんです。

田中: 二人とも本当によく頑張ってくれました。中村さん、このプロジェクトを通じてML設計からプロジェクト管理まで一人でやり切れるようになりましたね。次のプロジェクトでテックリードの役割を担ってほしいと思っています。

中村: ありがとうございます。正直まだ自信はないですが、やってみます。

田中: 大丈夫。今回の経験があれば絶対にできます。次のPJを一緒に考えましょう。""",
    },
]

# ============================================================
# PJ-C: タスク（5件・計画段階）
# ============================================================
PJ_C_TASKS = [
    {
        "タスク名": "医療画像データセット調査・整備",
        "担当者": "未定",
        "ステータス": "未着手",
        "ストーリーポイント": 5,
        "使用スキル": "Python, DICOM処理, データ整備",
        "実行結果・学び": "",
    },
    {
        "タスク名": "画像前処理パイプライン（DICOM対応）",
        "担当者": "未定",
        "ステータス": "未着手",
        "ストーリーポイント": 8,
        "使用スキル": "Python, DICOM, 画像前処理, pydicom",
        "実行結果・学び": "",
    },
    {
        "タスク名": "ベースラインモデル実装（EfficientNet）",
        "担当者": "未定",
        "ステータス": "未着手",
        "ストーリーポイント": 8,
        "使用スキル": "Python, PyTorch, EfficientNet, 画像分類",
        "実行結果・学び": "",
    },
    {
        "タスク名": "Vision Transformer Fine-tuning",
        "担当者": "未定",
        "ステータス": "未着手",
        "ストーリーポイント": 13,
        "使用スキル": "Python, PyTorch, Vision Transformer, Swin Transformer",
        "実行結果・学び": "",
    },
    {
        "タスク名": "推論APIサーバー構築・Azureデプロイ",
        "担当者": "未定",
        "ステータス": "未着手",
        "ストーリーポイント": 5,
        "使用スキル": "Python, FastAPI, Azure Container Apps, Docker",
        "実行結果・学び": "",
    },
]


# ============================================================
# ユーティリティ
# ============================================================

def section(title: str) -> None:
    print(f"\n{'=' * 55}\n{title}\n{'=' * 55}")


def t(content: str) -> list:
    return [{"text": {"content": content}}] if content else []


def load_env() -> None:
    env_path = pathlib.Path(__file__).resolve().parent.parent / ".env"
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def find_first_content_block(client: Client, page_id: str) -> str | None:
    cursor = None
    while True:
        resp = client.blocks.children.list(block_id=page_id, start_cursor=cursor, page_size=100)
        for b in resp["results"]:
            if b["type"] == "paragraph" and b["paragraph"]["rich_text"]:
                return b["id"]
        if not resp.get("has_more"):
            break
        cursor = resp["next_cursor"]
    return None


# ============================================================
# STEP 1: PJ-A 期間更新
# ============================================================
def update_pja_period(client: Client) -> None:
    section("STEP 1: PJ-A 期間更新 (〜2026-07-31)")
    block_id = find_first_content_block(client, PJ_A_PAGE_ID)
    if block_id:
        client.blocks.update(
            block_id=block_id,
            paragraph={"rich_text": t(PJ_A_INFO_UPDATED)},
        )
        print(f"OK: PJ-A 冒頭ブロック更新 (block={block_id})")
    else:
        print("WARN: PJ-A に既存コンテンツブロックが見つかりません。スキップ。")


# ============================================================
# STEP 2: 中村 大樹 をハブメンバーDBに追加
# ============================================================
def add_nakamura(client: Client) -> None:
    section("STEP 2: 中村 大樹 をメンバーDBに追加")
    m = NAKAMURA
    client.pages.create(
        parent={"database_id": MEMBER_DB_ID},
        properties={
            "名前":       {"title": t(m["名前"])},
            "email":      {"rich_text": t(m["email"])},
            "役職":       {"select": {"name": m["役職"]}},
            "スキル":     {"rich_text": t(m["スキル"])},
            "経験年数":   {"number": m["経験年数"]},
            "月次コスト": {"number": m["月次コスト"]},
            "一言メモ":   {"rich_text": t(m["一言メモ"])},
        },
    )
    print(f"OK: {m['名前']} ({m['役職']}) 追加完了")


# ============================================================
# STEP 3: PJ-B スキーマ設定 + データ投入
# ============================================================

def setup_pjb_task_schema(client: Client) -> None:
    """PJ-B タスク管理DB: スキーマを整備する（status型はそのまま保持）."""
    # 1. タイトル列を「タスク名」にリネーム
    client.data_sources.update(PJ_B_TASK_DS_ID, properties={"名前": {"name": "タスク名"}})
    print("OK: タスク名 にリネーム")

    # 2. 既存の people 型担当者を削除
    client.data_sources.update(PJ_B_TASK_DS_ID, properties={"担当者": None})
    print("OK: 担当者(people) 削除")

    # 3. 担当者(rich_text) + 残りのプロパティを追加
    client.data_sources.update(
        PJ_B_TASK_DS_ID,
        properties={
            "担当者":         {"rich_text": {}},
            "ストーリーポイント": {"number": {"format": "number"}},
            "使用スキル":     {"rich_text": {}},
            "実行結果・学び": {"rich_text": {}},
        },
    )
    print("OK: タスクDBプロパティ定義完了")


def setup_pjb_meeting_schema(client: Client) -> None:
    """PJ-B 議事録DB: スキーマを整備する."""
    client.data_sources.update(PJ_B_MTG_DS_ID, properties={"名前": {"name": "タイトル"}})
    print("OK: タイトル にリネーム")

    client.data_sources.update(
        PJ_B_MTG_DS_ID,
        properties={
            "日付":   {"date": {}},
            "種別":   {"select": {"options": [
                {"name": "チームMTG",         "color": "blue"},
                {"name": "1on1",              "color": "green"},
                {"name": "スプリントレビュー", "color": "orange"},
            ]}},
            "参加者": {"rich_text": {}},
            "本文":   {"rich_text": {}},
        },
    )
    print("OK: 議事録DBプロパティ定義完了")


def setup_pjb_member_schema(client: Client) -> None:
    """PJ-B メンバーDB: スキーマを整備する."""
    client.data_sources.update(
        PJ_B_MBR_DS_ID,
        properties={
            "email":    {"rich_text": {}},
            "役職":     {"select": {"options": [
                {"name": "データサイエンティスト",  "color": "purple"},
                {"name": "MLOps/DevOpsエンジニア", "color": "orange"},
            ]}},
            "スキル":   {"rich_text": {}},
            "経験年数": {"number": {"format": "number"}},
            "一言メモ": {"rich_text": {}},
        },
    )
    print("OK: メンバーDBプロパティ定義完了")


def insert_tasks_status(client: Client, db_id: str, tasks: list) -> None:
    """ステータスが status 型のタスクDBに行を挿入する（PJ-B用）."""
    for task in tasks:
        client.pages.create(
            parent={"database_id": db_id},
            properties={
                "タスク名":           {"title": t(task["タスク名"])},
                "担当者":             {"rich_text": t(task["担当者"])},
                "ステータス":         {"status": {"name": task["ステータス"]}},
                "ストーリーポイント": {"number": task["ストーリーポイント"]},
                "使用スキル":         {"rich_text": t(task["使用スキル"])},
                "実行結果・学び":     {"rich_text": t(task["実行結果・学び"])},
            },
        )
        print(f"    + [{task['ステータス']}] {task['タスク名'][:35]} — {task['担当者']} / {task['ストーリーポイント']}pt")


def insert_tasks_select(client: Client, db_id: str, tasks: list) -> None:
    """ステータスが select 型のタスクDBに行を挿入する（PJ-C用）."""
    for task in tasks:
        client.pages.create(
            parent={"database_id": db_id},
            properties={
                "タスク名":           {"title": t(task["タスク名"])},
                "担当者":             {"rich_text": t(task["担当者"])},
                "ステータス":         {"select": {"name": task["ステータス"]}},
                "ストーリーポイント": {"number": task["ストーリーポイント"]},
                "使用スキル":         {"rich_text": t(task["使用スキル"])},
                "実行結果・学び":     {"rich_text": t(task["実行結果・学び"])},
            },
        )
        print(f"    + [{task['ステータス']}] {task['タスク名'][:35]} — {task['担当者']} / {task['ストーリーポイント']}pt")


def insert_meetings(client: Client, db_id: str, meetings: list) -> None:
    for mtg in meetings:
        client.pages.create(
            parent={"database_id": db_id},
            properties={
                "タイトル": {"title": t(mtg["タイトル"])},
                "日付":     {"date": {"start": mtg["日付"]}},
                "種別":     {"select": {"name": mtg["種別"]}},
                "参加者":   {"rich_text": t(mtg["参加者"])},
                "本文":     {"rich_text": t(mtg["本文"])},
            },
        )
        print(f"    + [{mtg['種別']}] {mtg['タイトル']} ({mtg['日付']})")


def insert_pjb_members(client: Client, db_id: str, members: list) -> None:
    for m in members:
        client.pages.create(
            parent={"database_id": db_id},
            properties={
                "名前":     {"title": t(m["名前"])},
                "email":    {"rich_text": t(m["email"])},
                "役職":     {"select": {"name": m["役職"]}},
                "スキル":   {"rich_text": t(m["スキル"])},
                "経験年数": {"number": m["経験年数"]},
                "一言メモ": {"rich_text": t(m["一言メモ"])},
            },
        )
        print(f"    + {m['名前']} ({m['役職']})")


def seed_pjb(client: Client) -> None:
    section("STEP 3: PJ-B スキーマ設定 + データ投入（大手EC向けレコメンドエンジン開発）")

    # スキーマ設定
    setup_pjb_task_schema(client)
    setup_pjb_meeting_schema(client)
    setup_pjb_member_schema(client)

    # データ投入
    section("  3a: タスク投入")
    insert_tasks_status(client, PJ_B_TASK_DB_ID, PJ_B_TASKS)
    print(f"OK: タスク {len(PJ_B_TASKS)} 件投入")

    section("  3b: 議事録投入")
    insert_meetings(client, PJ_B_MTG_DB_ID, PJ_B_MEETINGS)
    print(f"OK: 議事録 {len(PJ_B_MEETINGS)} 件投入")

    section("  3c: メンバー投入")
    insert_pjb_members(client, PJ_B_MBR_DB_ID, PJ_B_MEMBERS)
    print(f"OK: メンバー {len(PJ_B_MEMBERS)} 名投入")


# ============================================================
# STEP 4: PJ-C タスク管理DB 新規作成 + データ投入
# ============================================================

def create_pjc_task_db(client: Client) -> str:
    """PJ-C ページ下にタスク管理DBを新規作成して DB_ID を返す."""
    db = client.databases.create(
        parent={"type": "page_id", "page_id": PJ_C_PAGE_ID},
        title=t("タスク管理"),
        initial_data_source={
            "properties": {
                "タスク名":           {"title": {}},
                "担当者":             {"rich_text": {}},
                "ステータス":         {"select": {"options": [
                    {"name": "未着手", "color": "gray"},
                    {"name": "進行中", "color": "blue"},
                    {"name": "完了",   "color": "green"},
                ]}},
                "ストーリーポイント": {"number": {"format": "number"}},
                "使用スキル":         {"rich_text": {}},
                "実行結果・学び":     {"rich_text": {}},
            }
        },
    )
    return db["id"]


def seed_pjc(client: Client) -> None:
    section("STEP 4: PJ-C タスク管理DB 新規作成 + タスク投入（医療画像AI診断支援システム）")

    task_db_id = create_pjc_task_db(client)
    print(f"OK: タスク管理DB 作成 (id={task_db_id})")
    print("NOTE: Notion UIでこのDBを「ボード」ビューに切り替えてください（ステータスでグループ化）")

    insert_tasks_select(client, task_db_id, PJ_C_TASKS)
    print(f"OK: タスク {len(PJ_C_TASKS)} 件投入")


# ============================================================
# main
# ============================================================

def main() -> int:
    load_env()
    token = os.getenv("NOTION_API_KEY")
    if not token:
        print("ERROR: NOTION_API_KEY が .env に見つかりません")
        return 1
    client = Client(auth=token)

    update_pja_period(client)
    add_nakamura(client)
    seed_pjb(client)
    seed_pjc(client)

    section("完了: Notion を開いて以下を確認してください")
    print("  [PJ-A] 次世代 LLM Agent 基盤開発: 期間が 4/1〜7/31 であることを確認")
    print("  [Hub]  メンバーDB: 中村 大樹 が追加されていること")
    print("  [PJ-B] タスク管理: 7件のタスク（ボードビュー）")
    print("  [PJ-B] 議事録: 5件の議事録")
    print("  [PJ-B] メンバーデータベース: 中村 大樹・山田 花奈")
    print("  [PJ-C] タスク管理: 5件（全て未着手）— UIでボードビューに切替を推奨")
    return 0


if __name__ == "__main__":
    sys.exit(main())
