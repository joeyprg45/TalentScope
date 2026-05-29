"""CosmosDB の slack_channels コンテナに proj-ec-recommend のメッセージを直接 seed するスクリプト。

Slack API → ingest の2段階チェーンをバイパスして、seed_slack_demo_v2.py に定義済みの
メッセージを直接 upsert する。

実行:
  uv run python scripts/seed_cosmos_slack.py
"""

import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
from azure.cosmos import CosmosClient

DATABASE_NAME = "talentscope"
CONTAINER_NAME = "slack_channels"

CHANNEL_ID = "C0B6Q4ARV6C"
CHANNEL_NAME = "proj-ec-recommend"
PROJECT_ID = "36ac7942-de09-811f-8814-ca6c340896be"

SPEAKER_MAP = {
    "田中 誠":   "tanaka@abc.com",
    "中村 大樹": "nakamura@abc.com",
    "山田 花奈": "yamada@abc.com",
}

# seed_slack_demo_v2.py の MESSAGES["proj-ec-recommend"] をそのまま定義
MESSAGES = [
    {"speaker": "田中 誠",
     "text": "【EC推薦エンジンPJ始動】今スプリントの方針です。"
             "中村さんはデータ探索とMLモデルのベースライン構築を優先してください。"
             "山田さんはAzure MLのパイプライン設計と並行して進めてもらえると助かります。"
             "困ったことは即スレッドに書いてください。"},
    {"speaker": "中村 大樹",
     "text": "EDAレポートできました。購買データの基本統計と欠損の分布を確認しました。"
             "気になった点：人気商品TOP100が全購買の67%を占めていて、"
             "協調フィルタリングだとロングテール商品の推薦が難しそうです。"
             "LightGBMで商品特徴量を入れる方向を試してみていいですか？"},
    {"speaker": "田中 誠",
     "text": "中村さん、EDAお疲れ様です。LightGBMの提案、試してみてください。"
             "ロングテール問題はECではよくある課題なので、"
             "解決できれば差別化ポイントになります。"},
    {"speaker": "山田 花奈",
     "text": "Azure MLのパイプライン設計、ドラフトできました。"
             "学習→評価→条件付きデプロイの3ステップ構成です。"
             "中村さんのローカルコードをそのままDockerコンテナ化して取り込めます。"
             "準備できたら共有します。"},
    {"speaker": "中村 大樹",
     "text": "LightGBMの最初の実験結果が出ました。"
             "Recall@10: 協調フィルタリング 0.34 → LightGBM 0.51。大幅改善です。"
             "さらに2つの特徴量追加を検討しています。"
             "①ユーザーの直近30日の閲覧カテゴリ分布 ②商品の同カテゴリ内売れ筋ランク。"
             "先週、両方実験した結果、①の方が効果が高かったです。採用しようと思います。"},
    {"speaker": "田中 誠",
     "text": "中村さん、実験結果と根拠がセットで提案できてていいですね。"
             "採用します。山田さん、パイプラインへの組み込みをお願いします。"},
    {"speaker": "山田 花奈",
     "text": "中村さんのコード、パイプラインに組み込み完了しました！"
             "今朝から自動学習が走っています。モデルレジストリで"
             "バージョン管理も自動です。精度ログをダッシュボードに載せました。"},
    {"speaker": "中村 大樹",
     "text": "アンサンブルモデルのA/Bテスト結果が出ました。"
             "コントロール群 vs テスト群で クリック率 +23%。目標の+20%を達成しました！"
             "Recall@10も最終的に0.67まで到達。"
             "山田さんの自動再学習の仕組みが効いて、6月に入ってから更に精度が上がりました。"},
    {"speaker": "山田 花奈",
     "text": "目標達成おめでとうございます！"
             "中村さんのモデルの品質が高かったから維持・改善できました。"
             "本番デプロイの最終確認、今週中にやります。"},
    {"speaker": "田中 誠",
     "text": "【PJ完了報告】CTR +23%、Recall@10=0.67でプロジェクト目標達成です。"
             "中村さん・山田さん、6ヶ月間お疲れ様でした。"
             "中村さんはML設計からプロジェクト進行管理まで一人でやり切れるようになった。"
             "次のプロジェクトでテックリードとして力を発揮してもらいます。"},
]

# 2026-02-01 00:00:00 UTC を基点に1時間ずつずらす
BASE_TS = 1738368000


def main() -> None:
    load_dotenv()
    conn_str = os.getenv("COSMOS_CONNECTION_STRING")
    if not conn_str:
        print("ERROR: COSMOS_CONNECTION_STRING が .env に設定されていません。")
        sys.exit(1)

    cosmos = CosmosClient.from_connection_string(conn_str)
    container = cosmos.get_database_client(DATABASE_NAME).get_container_client(CONTAINER_NAME)

    print(f"CosmosDB: {DATABASE_NAME}/{CONTAINER_NAME}")
    print(f"投入対象: {CHANNEL_NAME} ({len(MESSAGES)} 件)\n")

    for i, m in enumerate(MESSAGES):
        ts_float = BASE_TS + i * 3600
        ts_str = f"{ts_float}.{i:06d}"
        posted_at = f"2026-02-01T{i:02d}:00:00+00:00"

        doc = {
            "id": f"{CHANNEL_NAME}::{i:04d}",
            "channel_id": CHANNEL_ID,
            "type": "slack_message",
            "channel_name": CHANNEL_NAME,
            "channel_kind": "project",
            "project_id": PROJECT_ID,
            "speaker": m["speaker"],
            "speaker_id": SPEAKER_MAP[m["speaker"]],
            "ts": ts_str,
            "posted_at": posted_at,
            "text": m["text"],
        }

        container.upsert_item(doc)
        print(f"  [{i+1:02d}] upserted: [{m['speaker']}] {m['text'][:60]}...")

    print(f"\n完了: {len(MESSAGES)} 件 upsert しました。")


if __name__ == "__main__":
    main()
