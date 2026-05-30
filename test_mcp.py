import asyncio
import os
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# .envファイルからGITHUB_ACCESS_TOKENを読み込む
load_dotenv()

# 1. GitHub MCPサーバーの起動パラメータを設定
# ※ Windows環境用に "npx.cmd" にしています。もしGit Bashなどで動かない場合は "npx" に戻してください。
import shutil  # 💡 ファイルの先頭（import文のところ）に追記してください

# 1. GitHub MCPサーバーの起動パラメータを設定（Windows Git Bash完全対応版）
npx_path = shutil.which("npx") or "npx"  # PC内のnpxの絶対パスを自動で探す

server_params = StdioServerParameters(
    command=npx_path,
    args=["-y", "@modelcontextprotocol/server-github"],
    env={
        **os.environ,
        "GITHUB_PERSONAL_ACCESS_TOKEN": os.getenv("GITHUB_ACCESS_TOKEN")
    }
)

async def list_all_github_mcp_tools():
    print("⏳ GitHub MCPサーバーを起動中...")
    
    try:
        # 2. MCPサーバーとパイプ接続
        async with stdio_client(server_params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                
                # 接続の初期化
                await session.initialize()
                print("✅ MCPサーバーとの接続に成功しました！\n")

                print("🔮 GitHub MCPサーバーからツール群のリストを取得中...")
                
                # 💡 サーバーが持っている全ツールを要求
                result = await session.list_tools()
                
                # tools属性からリストを取得（念のためdict型の場合のケアも内包）
                tools_list = result.tools if hasattr(result, "tools") else getattr(result, "tools", [])

                print(f"\n=============================================")
                print(f"🛠️  GitHub MCP 利用可能ツール一覧 (全 {len(tools_list)} 件)")
                print(f"=============================================\n")

                # 3. 取得したツールを1つずつループして綺麗に表示
                for i, tool in enumerate(tools_list, 1):
                    # MCPのToolオブジェクト、または辞書型どちらでも安全に読めるようにパース
                    tool_name = getattr(tool, "name", tool.get("name") if isinstance(tool, dict) else "")
                    tool_desc = getattr(tool, "description", tool.get("description") if isinstance(tool, dict) else "")
                    input_schema = getattr(tool, "inputSchema", tool.get("inputSchema") if isinstance(tool, dict) else {})

                    print(f"{i}. 【ツール名】: {tool_name}")
                    print(f"   📝 【機能説明】: {tool_desc}")
                    
                    # そのツールを使う時に必要な引数（パラメータ）の情報をパース
                    if input_schema and "properties" in input_schema:
                        required_fields = input_schema.get("required", [])
                        print(f"   📥 【必要な引数 (Arguments)】:")
                        
                        for param_name, param_info in input_schema["properties"].items():
                            is_required = "⭐ [必須]" if param_name in required_fields else "[任意]"
                            param_type = param_info.get("type", "unknown")
                            param_desc = param_info.get("description", "説明なし")
                            print(f"     - {param_name} ({param_type}) {is_required}: {param_desc}")
                    
                    print("-" * 70)

    except Exception as e:
        print(f"❌ MCPツールの取得に失敗しました: {e}")
        print("\n💡 対策チェックリスト:")
        print("1. ターミナルで 'node -v' や 'npx -v' が通るか確認（Node.js未導入の可能性）")
        print("2. .env ファイルの変数名が 'GITHUB_ACCESS_TOKEN' で、値が正しいか確認")
        print("3. Windowsの実行環境によっては、command='npx'（.cmdなし）に戻すと動く場合があります")

if __name__ == "__main__":
    # 非同期処理を実行
    asyncio.run(list_all_github_mcp_tools())