"""次世代 LLM Agent 基盤開発ページに新スキーマでデモデータを投入する検証用スクリプト.

docs/data-schema.md の規約に従い、ユーザーが手動作成した3つの空DBへデータを入れる。
  STEP 1: ページ冒頭にプロジェクト基本情報（規約フォーマット）を投入
  STEP 2: メンバーDB のスキーマ定義 + 5名投入
  STEP 3: タスク管理DB のスキーマ定義 + 8タスク投入（ボードビュー）
  STEP 4: 議事録DB のスキーマ定義 + 4議事録投入

notion-client v3 前提: プロパティ操作は data_sources.*、行追加は pages.create。
"""

import os
import pathlib
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from notion_client import Client

# ============================================================
# 対象ページ / DB（読み取り済みの実IDを直書き）
# ============================================================
PROJECT_PAGE_ID = "366c7942-de09-8092-9a75-e59d205d94d0"

MEMBER_DB_ID = "367c7942-de09-80e2-b2c9-c70f94d2aa72"
MEMBER_DS_ID = "367c7942-de09-8026-af72-000b072dfb23"
TASK_DB_ID = "367c7942-de09-802c-ba1a-d51df387b950"
TASK_DS_ID = "367c7942-de09-80f0-a785-000b74ddc0fd"
MTG_DB_ID = "367c7942-de09-80bc-87c0-e79f6336ec2f"
MTG_DS_ID = "367c7942-de09-8037-8cf9-000b49c08892"

# ============================================================
# デモデータ
# ============================================================
PROJECT_INFO_LINES = [
    "概要: 人事エージェントの基盤となるLLM Agentプラットフォームの開発。",
    "期間: 2026-05-01 〜 2026-06-30",
    "ステータス: 進行中",
    "必要スキル: Python, Semantic Kernel, Azure OpenAI, RAG, CosmosDB",
]

MEMBERS = [
    {
        "名前": "小林 拓海",
        "email": "kobayashi@abc.com",
        "役職": "バックエンドエンジニア",
        "スキル": "Python, Azure, CosmosDB, FastAPI, REST API",
        "経験年数": 3,
        "一言メモ": "インフラからAPIまで幅広く対応。CosmosDB設計が得意。",
    },
    {
        "名前": "前田 彩",
        "email": "maeda@abc.com",
        "役職": "AIエンジニア",
        "スキル": "Python, Semantic Kernel, LLM, RAG, Azure OpenAI, ベクトル検索",
        "経験年数": 5,
        "一言メモ": "LLM応用の第一人者。RAGパイプラインの設計経験豊富。",
    },
    {
        "名前": "佐藤 健太",
        "email": "sato@abc.com",
        "役職": "フロントエンドエンジニア",
        "スキル": "React, TypeScript, Next.js, UI/UX, Figma",
        "経験年数": 2,
        "一言メモ": "UI実装が速い。ユーザー視点のフィードバックが鋭い。",
    },
    {
        "名前": "田中 誠",
        "email": "tanaka@abc.com",
        "役職": "テックリード",
        "スキル": "Python, アーキテクチャ設計, PM, Azure, セキュリティ設計",
        "経験年数": 7,
        "一言メモ": "チーム全体の技術判断を担う。メンバーの育成にも積極的。",
    },
    {
        "名前": "山田 花奈",
        "email": "yamada@abc.com",
        "役職": "MLOps/DevOpsエンジニア",
        "スキル": "Azure, Docker, GitHub Actions, CI/CD, Python, Kubernetes",
        "経験年数": 4,
        "一言メモ": "デプロイ・自動化の専門家。障害対応が冷静で迅速。",
    },
]

TASKS = [
    {
        "タスク名": "Azure Cosmos DB 接続設計・実装",
        "担当者": "小林 拓海",
        "ステータス": "完了",
        "ストーリーポイント": 5,
        "使用スキル": "Python, Azure, CosmosDB, NoSQL",
        "実行結果・学び": "CosmosDB SDKでCRUDを実装。パーティションキーの設計で詰まったが、member_idをキーにすることで解決。インデックス設計も見直し、クエリ速度が3倍改善。",
    },
    {
        "タスク名": "Semantic Kernel エージェント基盤構築",
        "担当者": "前田 彩",
        "ステータス": "進行中",
        "ストーリーポイント": 8,
        "使用スキル": "Python, Semantic Kernel, Azure OpenAI",
        "実行結果・学び": "",
    },
    {
        "タスク名": "Notion Ingest パイプライン実装",
        "担当者": "小林 拓海",
        "ステータス": "完了",
        "ストーリーポイント": 5,
        "使用スキル": "Python, Notion API, REST",
        "実行結果・学び": "再帰クロールで全ブロックを取得できた。has_childrenフラグを使った実装が鍵。ページネーション処理でのバグを1件修正。",
    },
    {
        "タスク名": "RAGパイプライン設計・検証",
        "担当者": "前田 彩",
        "ステータス": "完了",
        "ストーリーポイント": 13,
        "使用スキル": "Python, Azure OpenAI, ベクトル検索, CosmosDB",
        "実行結果・学び": "CosmosDBのベクトル検索機能でRAGを実装。埋め込みモデルはtext-embedding-3-smallを採用。チャンク分割のサイズ調整で精度が大幅向上（Recall@5: 0.72→0.91）。",
    },
    {
        "タスク名": "Slack メッセージ取り込み実装",
        "担当者": "佐藤 健太",
        "ステータス": "完了",
        "ストーリーポイント": 3,
        "使用スキル": "Python, Slack API",
        "実行結果・学び": "users.listで名前解決を一度にまとめることでレート制限を回避。subtypeフィールドでシステムメッセージを除外する処理が重要だった。",
    },
    {
        "タスク名": "チャットUI実装",
        "担当者": "佐藤 健太",
        "ステータス": "未着手",
        "ストーリーポイント": 8,
        "使用スキル": "React, TypeScript, Next.js",
        "実行結果・学び": "",
    },
    {
        "タスク名": "Azure デプロイ・CI/CD 構築",
        "担当者": "山田 花奈",
        "ステータス": "未着手",
        "ストーリーポイント": 5,
        "使用スキル": "Azure Container Apps, GitHub Actions, Docker",
        "実行結果・学び": "",
    },
    {
        "タスク名": "アーキテクチャ設計・レビュー",
        "担当者": "田中 誠",
        "ステータス": "完了",
        "ストーリーポイント": 3,
        "使用スキル": "アーキテクチャ設計, Azure",
        "実行結果・学び": "Ingest/Queryの分離設計を採用。エージェントがNotionを動的参照しない設計にすることでデモ安定性が確保できた。",
    },
]

MEETINGS = [
    {
        "タイトル": "スプリント1 キックオフMTG",
        "日付": "2026-05-07",
        "種別": "チームMTG",
        "参加者": "田中 誠, 前田 彩, 小林 拓海, 佐藤 健太, 山田 花奈",
        "本文": """田中: 今スプリントのゴールはIngest層の完成とRAGの初期検証です。前田さん、RAG側の見通しはどうですか？

前田: CosmosDBのベクトル検索機能を使う方針で進めます。先週調査した結果、Azure AI Searchより構成がシンプルになりそうです。1週間で初期実装まで持っていけると思います。

田中: いいですね。小林さんはCosmosDB接続とNotionのIngestを並行でお願いしたいですが、工数的には大丈夫ですか？

小林: CosmosDB側は設計が固まれば2〜3日で実装できます。Notionのクロールは再帰処理が少し複雑ですが、前回検証で動くコードはあるので問題ないです。

佐藤: UIはまだ着手できていないので、バックエンドAPIが固まったら教えてください。モックアップは作り始めます。

山田: CI/CD側はスプリント2以降でいいですか？今はローカル開発を優先したほうがよさそう。

田中: そうですね。山田さんはDockerfileの雛形だけ今週中にお願いします。あとはスプリント2で。では各自タスクに着手しましょう。""",
    },
    {
        "タイトル": "1on1: 田中×前田",
        "日付": "2026-05-12",
        "種別": "1on1",
        "参加者": "田中 誠, 前田 彩",
        "本文": """田中: RAGの進捗どうですか？

前田: ベクトル検索の実装自体は動いています。ただチャンクサイズの調整で悩んでいて。500トークンでやると精度が低くて、200にしたら今度はコンテキストが切れてしまって。

田中: それはRAGあるあるですよね。ハイブリッド検索（キーワード+ベクトル）も試しましたか？

前田: まだです。CosmosDBがハイブリッド検索サポートしてるか確認します。

田中: 前田さんはこういう技術的な深掘りが得意ですよね。次のプロジェクトでもAIコアの設計をリードしてほしいと思っています。将来的にはテックリードも視野に入れてほしい。

前田: ありがとうございます。まだチームマネジメントは自信ないですが、技術的なリードはやっていきたいです。

田中: 焦らなくて大丈夫。今は深い専門性を磨いていきましょう。何か困ってることは？

前田: 特にないです。このプロジェクト楽しいです。""",
    },
    {
        "タイトル": "1on1: 田中×小林",
        "日付": "2026-05-14",
        "種別": "1on1",
        "参加者": "田中 誠, 小林 拓海",
        "本文": """田中: CosmosDBの設計、どうでした？

小林: パーティションキーで少し詰まりました。member_idとproject_idどちらにするか迷って。最終的にmember_idにしましたが、クロスパーティションクエリが必要なケースが出てきて、インデックスで対応しました。

田中: その判断は正しいと思います。ちゃんとトレードオフを考えて決められてますね。

小林: ありがとうございます。ただAPI設計はまだ自信なくて。エラーハンドリングとか、本番を意識した実装が弱い気がしています。

田中: それは意識できてるだけでも十分です。次のスプリントでAPIのコードレビューをしっかりやりましょう。小林さん、バックエンド全般の判断を任せたいと思っているので。

小林: わかりました、頑張ります。""",
    },
    {
        "タイトル": "スプリント1 レビュー＆レトロスペクティブ",
        "日付": "2026-05-20",
        "種別": "スプリントレビュー",
        "参加者": "田中 誠, 前田 彩, 小林 拓海, 佐藤 健太, 山田 花奈",
        "本文": """田中: スプリント1の振り返りをします。完了したタスクを確認しましょう。

小林: CosmosDB接続とNotionのIngestパイプラインは完了です。RAGとの接続まで確認できました。

前田: RAGパイプラインも完成しました。Recall@5が0.91まで出ています。ハイブリッド検索は今回は見送りましたが、精度は十分です。

佐藤: Slack取り込みを完了しました。UIはまだです。すみません。

山田: Dockerfileの雛形は作りました。

田中: 全体的に良いスプリントでした。前田さんのRAG精度は想定以上です。
次のスプリントはエージェント実装とUI着手ですね。佐藤さん、UIを最優先でお願いします。

佐藤: はい、次スプリントで必ず完成させます。

田中: KPT出しましょう。Keep: 前田・小林の実装スピード。Problem: UIが後ろ倒し。Try: 毎日15分のスタンドアップを追加する。

前田: スタンドアップ賛成です。依存関係の共有が早くできる。

小林: 同意です。""",
    },
]


# ============================================================
# ユーティリティ
# ============================================================
def section(title: str) -> None:
    print(f"\n{'=' * 55}\n{title}\n{'=' * 55}")


def rt(content: str) -> list:
    """rich_text / title 用。空文字なら空配列を返す。"""
    return [{"text": {"content": content}}] if content else []


def load_env() -> None:
    env_path = pathlib.Path(__file__).resolve().parent.parent / ".env"
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def find_empty_paragraphs(client: Client, page_id: str) -> list:
    ids, cursor = [], None
    while True:
        resp = client.blocks.children.list(block_id=page_id, start_cursor=cursor, page_size=100)
        for b in resp["results"]:
            if b["type"] == "paragraph" and not b["paragraph"]["rich_text"]:
                ids.append(b["id"])
        if not resp.get("has_more"):
            break
        cursor = resp["next_cursor"]
    return ids


# ============================================================
# STEP 1: ページ冒頭の基本情報
# ============================================================
def seed_project_info(client: Client) -> None:
    section("STEP 1: プロジェクト基本情報をページ冒頭に投入")
    info_text = "\n".join(PROJECT_INFO_LINES)
    empty = find_empty_paragraphs(client, PROJECT_PAGE_ID)
    if empty:
        client.blocks.update(block_id=empty[0], paragraph={"rich_text": rt(info_text)})
        print(f"OK: 既存の空段落を更新 (block={empty[0]})")
    else:
        client.blocks.children.append(
            block_id=PROJECT_PAGE_ID,
            children=[{"object": "block", "type": "paragraph",
                       "paragraph": {"rich_text": rt(info_text)}}],
        )
        print("OK: 段落を追加")
    for line in PROJECT_INFO_LINES:
        print(f"    {line}")


# ============================================================
# STEP 2: メンバーDB
# ============================================================
def seed_members(client: Client) -> None:
    section("STEP 2: メンバーDB スキーマ定義 + 5名投入")
    client.data_sources.update(
        MEMBER_DS_ID,
        properties={
            "email": {"rich_text": {}},
            "役職": {"select": {"options": [
                {"name": "バックエンドエンジニア", "color": "blue"},
                {"name": "AIエンジニア", "color": "purple"},
                {"name": "フロントエンドエンジニア", "color": "green"},
                {"name": "テックリード", "color": "red"},
                {"name": "MLOps/DevOpsエンジニア", "color": "orange"},
            ]}},
            "スキル": {"rich_text": {}},
            "経験年数": {"number": {"format": "number"}},
            "一言メモ": {"rich_text": {}},
        },
    )
    print("OK: プロパティ定義完了")
    for m in MEMBERS:
        client.pages.create(
            parent={"database_id": MEMBER_DB_ID},
            properties={
                "名前": {"title": rt(m["名前"])},
                "email": {"rich_text": rt(m["email"])},
                "役職": {"select": {"name": m["役職"]}},
                "スキル": {"rich_text": rt(m["スキル"])},
                "経験年数": {"number": m["経験年数"]},
                "一言メモ": {"rich_text": rt(m["一言メモ"])},
            },
        )
        print(f"    + {m['名前']} ({m['役職']})")
    print(f"OK: メンバー {len(MEMBERS)} 名投入")


# ============================================================
# STEP 3: タスク管理DB（ボードビュー）
# ============================================================
def seed_tasks(client: Client) -> None:
    section("STEP 3: タスク管理DB スキーマ定義 + 8タスク投入")

    # title リネーム: 名前 -> タスク名
    client.data_sources.update(TASK_DS_ID, properties={"名前": {"name": "タスク名"}})
    print("OK: title を タスク名 にリネーム")

    # 担当者(people) を削除
    client.data_sources.update(TASK_DS_ID, properties={"担当者": None})
    print("OK: 担当者(people) を削除")

    # 担当者(rich_text) + 残りのプロパティを追加
    client.data_sources.update(
        TASK_DS_ID,
        properties={
            "担当者": {"rich_text": {}},
            "ストーリーポイント": {"number": {"format": "number"}},
            "使用スキル": {"rich_text": {}},
            "実行結果・学び": {"rich_text": {}},
        },
    )
    print("OK: 担当者(rich_text) ほかプロパティ定義完了")

    for task in TASKS:
        client.pages.create(
            parent={"database_id": TASK_DB_ID},
            properties={
                "タスク名": {"title": rt(task["タスク名"])},
                "担当者": {"rich_text": rt(task["担当者"])},
                "ステータス": {"status": {"name": task["ステータス"]}},
                "ストーリーポイント": {"number": task["ストーリーポイント"]},
                "使用スキル": {"rich_text": rt(task["使用スキル"])},
                "実行結果・学び": {"rich_text": rt(task["実行結果・学び"])},
            },
        )
        print(f"    + [{task['ステータス']}] {task['タスク名'][:30]} — {task['担当者']} / {task['ストーリーポイント']}pt")
    print(f"OK: タスク {len(TASKS)} 件投入")


# ============================================================
# STEP 4: 議事録DB
# ============================================================
def seed_meetings(client: Client) -> None:
    section("STEP 4: 議事録DB スキーマ定義 + 4議事録投入")

    client.data_sources.update(MTG_DS_ID, properties={"名前": {"name": "タイトル"}})
    print("OK: title を タイトル にリネーム")

    client.data_sources.update(
        MTG_DS_ID,
        properties={
            "日付": {"date": {}},
            "種別": {"select": {"options": [
                {"name": "チームMTG", "color": "blue"},
                {"name": "1on1", "color": "green"},
                {"name": "スプリントレビュー", "color": "orange"},
            ]}},
            "参加者": {"rich_text": {}},
            "本文": {"rich_text": {}},
        },
    )
    print("OK: プロパティ定義完了")

    for mtg in MEETINGS:
        client.pages.create(
            parent={"database_id": MTG_DB_ID},
            properties={
                "タイトル": {"title": rt(mtg["タイトル"])},
                "日付": {"date": {"start": mtg["日付"]}},
                "種別": {"select": {"name": mtg["種別"]}},
                "参加者": {"rich_text": rt(mtg["参加者"])},
                "本文": {"rich_text": rt(mtg["本文"])},
            },
        )
        print(f"    + [{mtg['種別']}] {mtg['タイトル']} ({mtg['日付']})")
    print(f"OK: 議事録 {len(MEETINGS)} 件投入")


# ============================================================
# 検証
# ============================================================
def verify(client: Client) -> None:
    section("検証: 各DBを読み直して件数確認")
    for label, ds_id in [("メンバーDB", MEMBER_DS_ID), ("タスク管理DB", TASK_DS_ID), ("議事録DB", MTG_DS_ID)]:
        rows = client.data_sources.query(data_source_id=ds_id).get("results", [])
        print(f"  {label}: {len(rows)} 行")


def main() -> int:
    load_env()
    token = os.getenv("NOTION_API_KEY")
    if not token:
        print("NG: NOTION_API_KEY が .env に見つかりません")
        return 1
    client = Client(auth=token)

    seed_project_info(client)
    seed_members(client)
    seed_tasks(client)
    seed_meetings(client)
    verify(client)

    section("完了: Notion で 次世代 LLM Agent 基盤開発 を確認してください")
    return 0


if __name__ == "__main__":
    sys.exit(main())
