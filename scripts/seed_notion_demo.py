"""Notion デモデータ投入スクリプト（フェーズ2）.

ABC_technologies 配下の3プロジェクトに、TalentScopeのデモ用DBとデータを作成する。
  STEP 1: プロジェクトページIDを動的取得
  STEP 2: メンバーDB を hub 直下に作成 + 5名投入
  STEP 3: 各プロジェクトに タスクDB + 議事録DB を作成
  STEP 4: タスク・議事録データを投入

※ APIで作成したDBはIntegration権限が自動付与される（既存インラインDBは不可）。
"""

import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
from notion_client import Client

HUB_PAGE_ID = "2c7c7942de0980aabf7fd79487c2ab01"

# ============================================================
# ダミーデータ
# ============================================================

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

PROJECTS_DATA = {
    "次世代 LLM Agent 基盤開発": {
        "tasks": [
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
        ],
        "meetings": [
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
        ],
    },
    "面接官AIエージェント": {
        "tasks": [
            {
                "タスク名": "面接質問生成モジュール実装",
                "担当者": "前田 彩",
                "ステータス": "完了",
                "ストーリーポイント": 8,
                "使用スキル": "Python, LLM, Azure OpenAI, Semantic Kernel",
                "実行結果・学び": "候補者のスキルシートをインプットに、ポジション別の質問を自動生成。Few-shotプロンプトで質問の質が大幅に向上した。",
            },
            {
                "タスク名": "候補者回答評価ロジック実装",
                "担当者": "前田 彩",
                "ステータス": "進行中",
                "ストーリーポイント": 5,
                "使用スキル": "Python, Azure OpenAI, 評価設計",
                "実行結果・学び": "",
            },
            {
                "タスク名": "面接UI・フロー実装",
                "担当者": "佐藤 健太",
                "ステータス": "完了",
                "ストーリーポイント": 8,
                "使用スキル": "React, TypeScript, Next.js",
                "実行結果・学び": "面接のフロー（質問→回答→次の質問）をステートマシンで実装。UIのレスポンスが速く、面接官からの評判が良い。",
            },
            {
                "タスク名": "評価レポート自動生成",
                "担当者": "前田 彩",
                "ステータス": "未着手",
                "ストーリーポイント": 5,
                "使用スキル": "Python, LLM, Azure OpenAI",
                "実行結果・学び": "",
            },
            {
                "タスク名": "テスト・品質改善",
                "担当者": "田中 誠",
                "ステータス": "進行中",
                "ストーリーポイント": 3,
                "使用スキル": "Python, pytest, 品質管理",
                "実行結果・学び": "",
            },
        ],
        "meetings": [
            {
                "タイトル": "プロジェクトキックオフMTG",
                "日付": "2026-04-15",
                "種別": "チームMTG",
                "参加者": "田中 誠, 前田 彩, 佐藤 健太",
                "本文": """田中: 面接官AIエージェントプロジェクトを開始します。スコープを確認しましょう。

前田: 質問生成と回答評価が2本柱ですね。LLMを使えば自然な面接フローが作れると思います。

佐藤: UIは面接官が使いやすいシンプルなものにしたいです。リアルタイムに次の質問が出てくるインターフェースはどうですか？

田中: いいですね。前田さん、まず質問生成から着手してください。佐藤さんはUIのモックアップを。

前田: わかりました。スキルシートを入力にして、職種別に質問を生成する方向で進めます。""",
            },
            {
                "タイトル": "1on1: 田中×佐藤",
                "日付": "2026-04-28",
                "種別": "1on1",
                "参加者": "田中 誠, 佐藤 健太",
                "本文": """田中: UI実装、順調ですか？

佐藤: 基本フローは動いています。ただ、面接官が質問を途中でスキップしたいときのUX設計で悩んでいます。

田中: ユーザーインタビューはやりましたか？

佐藤: まだです。社内の採用担当に聞いてみます。

田中: 佐藤さんはユーザー視点が鋭いので、そういうフィードバックを積極的に拾ってほしい。技術だけじゃなくてプロダクト全体を見る力をつけてほしいと思っています。

佐藤: はい。自分もプロダクト視点で考えられるエンジニアになりたいです。""",
            },
            {
                "タイトル": "中間レビューMTG",
                "日付": "2026-05-08",
                "種別": "チームMTG",
                "参加者": "田中 誠, 前田 彩, 佐藤 健太",
                "本文": """田中: 中間レビューをします。前田さんから。

前田: 質問生成は完成しました。Few-shotプロンプトで質問の多様性も確保できています。デモを見てください。（デモ実施）

田中: 質問のレベルが高いですね。採用担当にも見せましょう。

佐藤: UIも完成しました。採用担当の方にフィードバックをもらって、スキップ機能と優先度設定を追加しました。

田中: 佐藤さん、ちゃんとユーザーインタビューしてくれましたね。UI完成度が高い。残りは評価ロジックとレポート生成ですね。前田さん、次スプリントで完成できますか？

前田: 評価ロジックは今週中に完成見込みです。レポート生成は来週。""",
            },
        ],
    },
    "大手金融向け 予測AIモデル開発": {
        "tasks": [
            {
                "タスク名": "データ前処理パイプライン構築",
                "担当者": "山田 花奈",
                "ステータス": "完了",
                "ストーリーポイント": 8,
                "使用スキル": "Python, Pandas, Azure Data Factory, ETL",
                "実行結果・学び": "金融データの欠損値処理と外れ値除去のパイプラインを構築。データ品質スコアを導入し、信頼性の低いデータを自動フラグする仕組みを実装。",
            },
            {
                "タスク名": "予測モデル設計・学習",
                "担当者": "前田 彩",
                "ステータス": "完了",
                "ストーリーポイント": 13,
                "使用スキル": "Python, scikit-learn, XGBoost, Azure ML",
                "実行結果・学び": "XGBoostをベースにアンサンブル学習を実装。特徴量エンジニアリングの工夫でAUC 0.89を達成。金融ドメイン知識をクライアントから吸収しながら進めた。",
            },
            {
                "タスク名": "モデル評価・チューニング",
                "担当者": "前田 彩",
                "ステータス": "進行中",
                "ストーリーポイント": 8,
                "使用スキル": "Python, MLflow, Azure ML, 統計",
                "実行結果・学び": "",
            },
            {
                "タスク名": "金融データのセキュリティ要件対応",
                "担当者": "田中 誠",
                "ステータス": "完了",
                "ストーリーポイント": 3,
                "使用スキル": "セキュリティ設計, Azure, 暗号化",
                "実行結果・学び": "金融庁ガイドラインに基づくデータ暗号化・アクセス制御を実装。Azure Key Vaultでシークレット管理を統一。",
            },
            {
                "タスク名": "本番環境デプロイ・監視",
                "担当者": "山田 花奈",
                "ステータス": "未着手",
                "ストーリーポイント": 5,
                "使用スキル": "Azure, Docker, MLflow, 監視設計",
                "実行結果・学び": "",
            },
        ],
        "meetings": [
            {
                "タイトル": "クライアントキックオフMTG",
                "日付": "2026-03-10",
                "種別": "チームMTG",
                "参加者": "田中 誠, 前田 彩, 山田 花奈",
                "本文": """田中: 大手金融クライアントとのプロジェクトが始まります。要件を整理しましょう。

前田: デフォルト予測モデルの精度向上がメインです。現状のルールベースより精度を上げることが目標。AUC 0.85以上を目指します。

山田: データはどこから来ますか？セキュリティ要件が厳しいと聞いています。

田中: Azure Data Factoryで安全に取り込む予定です。金融庁のガイドラインに準拠する必要があります。山田さん、セキュリティ設計をお願いしたい。

山田: わかりました。Azure Key Vaultを使ったシークレット管理から始めます。

前田: データが届いたら特徴量エンジニアリングから着手します。金融ドメインの知識は田中さんにサポートしてもらいながら進めます。""",
            },
            {
                "タイトル": "1on1: 田中×山田",
                "日付": "2026-03-25",
                "種別": "1on1",
                "参加者": "田中 誠, 山田 花奈",
                "本文": """田中: データパイプライン、順調ですか？

山田: 前処理の部分で金融データ特有の欠損パターンに苦労しました。でも対処法を考えて、データ品質スコアを導入しました。

田中: 面白いアプローチですね。自分で課題を見つけて解決策を出せるのは山田さんの強みです。

山田: ありがとうございます。ただMLOps側はまだ経験が浅くて、本番デプロイが少し不安です。

田中: MLflowは使ったことありますか？モデルのバージョン管理と監視ができます。一緒に設計しましょう。

山田: ぜひお願いします。インフラとMLの両方を理解できるエンジニアになりたいと思っています。

田中: 山田さんはそこが強みになりますよ。インフラとMLを繋げられる人材は希少です。""",
            },
            {
                "タイトル": "モデル精度レビューMTG",
                "日付": "2026-04-20",
                "種別": "チームMTG",
                "参加者": "田中 誠, 前田 彩, 山田 花奈",
                "本文": """田中: モデルの進捗レビューをします。

前田: XGBoostベースのアンサンブルモデルでAUC 0.89を達成しました。目標の0.85を超えています。特徴量は72個使っていて、重要度上位10件がモデルの80%以上を説明しています。

田中: 素晴らしい。クライアントへの説明可能性はどうですか？

前田: SHAP値で各予測の根拠を説明できます。金融機関には説明責任が必要なので、そこは丁寧にやりました。

山田: データパイプラインの安定性も確認できました。欠損率が高いデータは自動的に除外されています。

田中: クライアントへの中間報告ができますね。前田さん、資料作成をお願いします。山田さんはデプロイ準備を始めてください。

前田: わかりました。来週の報告に向けて準備します。

山田: デプロイはMLflowでモデルのバージョン管理をしながら進めます。""",
            },
        ],
    },
}


# ============================================================
# ユーティリティ
# ============================================================

def section(title: str) -> None:
    print(f"\n{'=' * 50}\n{title}\n{'=' * 50}")


def t(content: str) -> list:
    return [{"text": {"content": content}}]


def list_children(client: Client, block_id: str) -> list:
    blocks, cursor = [], None
    while True:
        resp = client.blocks.children.list(block_id=block_id, start_cursor=cursor, page_size=100)
        blocks.extend(resp.get("results", []))
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")
    return blocks


def get_project_page_ids(client: Client) -> dict:
    """ABC_technologies 直下のプロジェクトページID一覧を返す。"""
    result = {}
    for block in list_children(client, HUB_PAGE_ID):
        if block.get("type") == "child_page":
            title = block["child_page"]["title"]
            result[title] = block["id"]
    return result


# ============================================================
# DB作成・データ投入
# ============================================================

def create_member_db(client: Client) -> str:
    db = client.databases.create(
        parent={"type": "page_id", "page_id": HUB_PAGE_ID},
        title=t("メンバーDB"),
        initial_data_source={
            "properties": {
                "名前":     {"title": {}},
                "email":    {"rich_text": {}},
                "役職":     {"select": {"options": [
                    {"name": "バックエンドエンジニア", "color": "blue"},
                    {"name": "AIエンジニア",          "color": "purple"},
                    {"name": "フロントエンドエンジニア","color": "green"},
                    {"name": "テックリード",           "color": "red"},
                    {"name": "MLOps/DevOpsエンジニア", "color": "orange"},
                ]}},
                "スキル":     {"rich_text": {}},
                "経験年数":   {"number": {"format": "number"}},
                "一言メモ":   {"rich_text": {}},
            }
        },
    )
    return db["id"]


def insert_members(client: Client, db_id: str) -> None:
    for m in MEMBERS:
        client.pages.create(
            parent={"database_id": db_id},
            properties={
                "名前":   {"title": t(m["名前"])},
                "email":  {"rich_text": t(m["email"])},
                "役職":   {"select": {"name": m["役職"]}},
                "スキル": {"rich_text": t(m["スキル"])},
                "経験年数": {"number": m["経験年数"]},
                "一言メモ": {"rich_text": t(m["一言メモ"])},
            },
        )
        print(f"    + {m['名前']} ({m['役職']})")


def create_task_db(client: Client, page_id: str) -> str:
    db = client.databases.create(
        parent={"type": "page_id", "page_id": page_id},
        title=t("タスクDB"),
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


def insert_tasks(client: Client, db_id: str, tasks: list) -> None:
    for task in tasks:
        client.pages.create(
            parent={"database_id": db_id},
            properties={
                "タスク名":       {"title": t(task["タスク名"])},
                "担当者":         {"rich_text": t(task["担当者"])},
                "ステータス":     {"select": {"name": task["ステータス"]}},
                "ストーリーポイント": {"number": task["ストーリーポイント"]},
                "使用スキル":     {"rich_text": t(task["使用スキル"])},
                "実行結果・学び": {"rich_text": t(task["実行結果・学び"])},
            },
        )
        print(f"    + [{task['ステータス']}] {task['タスク名'][:35]} — {task['担当者']} / {task['ストーリーポイント']}pt")


def create_meeting_db(client: Client, page_id: str) -> str:
    db = client.databases.create(
        parent={"type": "page_id", "page_id": page_id},
        title=t("議事録DB"),
        initial_data_source={
            "properties": {
                "タイトル": {"title": {}},
                "日付":     {"date": {}},
                "種別":     {"select": {"options": [
                    {"name": "チームMTG",         "color": "blue"},
                    {"name": "1on1",              "color": "green"},
                    {"name": "スプリントレビュー", "color": "orange"},
                ]}},
                "参加者":   {"rich_text": {}},
                "本文":     {"rich_text": {}},
            }
        },
    )
    return db["id"]


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


# ============================================================
# main
# ============================================================

def main() -> int:
    load_dotenv()
    client = Client(auth=os.getenv("NOTION_API_KEY"))

    section("STEP 1: プロジェクトページID 取得")
    project_ids = get_project_page_ids(client)
    for name, pid in project_ids.items():
        print(f"  {name}: {pid}")
    if not project_ids:
        print("NG: プロジェクトページが見つかりません")
        return 1

    section("STEP 2: メンバーDB 作成 + 5名投入")
    member_db_id = create_member_db(client)
    print(f"OK: メンバーDB 作成 (id={member_db_id})")
    insert_members(client, member_db_id)
    print(f"OK: メンバー {len(MEMBERS)} 名投入")

    section("STEP 3 & 4: 各プロジェクトに タスクDB + 議事録DB 作成・投入")
    for proj_name, data in PROJECTS_DATA.items():
        page_id = project_ids.get(proj_name)
        if not page_id:
            print(f"  SKIP: '{proj_name}' のページIDが見つかりません")
            continue

        print(f"\n▶ {proj_name}")

        task_db_id = create_task_db(client, page_id)
        print(f"  OK: タスクDB 作成 (id={task_db_id})")
        insert_tasks(client, task_db_id, data["tasks"])
        print(f"  OK: タスク {len(data['tasks'])} 件投入")

        meeting_db_id = create_meeting_db(client, page_id)
        print(f"  OK: 議事録DB 作成 (id={meeting_db_id})")
        insert_meetings(client, meeting_db_id, data["meetings"])
        print(f"  OK: 議事録 {len(data['meetings'])} 件投入")

    section("完了: Notionを開いて確認してください")
    print(f"  メンバーDB: ABC_technologiesトップ直下")
    print(f"  タスクDB / 議事録DB: 各プロジェクトページ直下")
    return 0


if __name__ == "__main__":
    sys.exit(main())
