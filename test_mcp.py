import asyncio
import os
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# .envファイルからGITHUB_ACCESS_TOKENを読み込む
load_dotenv()



# 1. GitHub MCPサーバーの起動パラメータを設定
server_params = StdioServerParameters(
    command="npx",
    args=["-y", "@modelcontextprotocol/server-github"],
    env={
        **os.environ,
        "GITHUB_PERSONAL_ACCESS_TOKEN": os.getenv("GITHUB_ACCESS_TOKEN")
    }
)

async def test_github_mcp():
    print("⏳ GitHub MCPサーバーを起動中...")
    
    # 2. MCPサーバーとパイプ（Stdio）で接続
    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            
            # 接続の初期化
            await session.initialize()
            print("✅ MCPサーバーとの接続に成功しました！\n")

            # 実験用リポジトリ（例としてfastapiの公式リポジトリを指定）
            # あなた自身の公開リポジトリ（例: "ユーザー名/リポジトリ名"）に変えてもOKです
            owner = "fastapi"
            repo = "fastapi"

            print(f"📦 {owner}/{repo} からコミット履歴を取得中...")
            
            # 3. GitHub MCPの「get_commits」というツールを呼び出す
            try:
                response = await session.call_tool(
                    name="get_commits",
                    arguments={
                        "owner": owner,
                        "repo": repo,
                        "per_page": 2 # テスト用に最新の2件だけ
                    }
                )
                
                # 4. 返ってきた生のデータを表示
                print("\n--- 📥 MCPから返ってきた生データ ---")
                print(response.content[0].text)
                print("------------------------------------\n")
                
            except Exception as e:
                print(f"❌ エラーが発生しました: {e}")

if __name__ == "__main__":
    # 非同期処理を実行
    asyncio.run(test_github_mcp())