"""MCP Inventory Report PoC — ファイル×DB横断エージェント（Streamlit + Tool use）"""
import json
import os

import anthropic
import streamlit as st

from tools import TOOL_DEFINITIONS, execute_tool

# --- モデル定義（ID・単価） ---
MODELS = {
    "Haiku 4.5（高速・低コスト）": {
        "id": "claude-haiku-4-5-20251001",
        "input_per_mtok": 1.00,
        "output_per_mtok": 5.00,
    },
    "Sonnet 4.6（バランス型）": {
        "id": "claude-sonnet-4-6",
        "input_per_mtok": 3.00,
        "output_per_mtok": 15.00,
    },
    "Opus 4.8（高品質）": {
        "id": "claude-opus-4-8",
        "input_per_mtok": 5.00,
        "output_per_mtok": 25.00,
    },
    "Fable 5（最上位・Mythos-class）": {
        "id": "claude-fable-5",
        "input_per_mtok": 10.00,
        "output_per_mtok": 50.00,
    },
}
JPY_RATE = 150  # 概算レート
MAX_TURNS = 15  # 無限ループ防止

SYSTEM_PROMPT = """あなたは製造業の在庫管理を支援するAIアシスタントです。

利用できるツール:
- list_files: データフォルダ内のファイル一覧を確認
- read_file: CSV/テキストファイルを読み取り
- list_tables: データベースのテーブル一覧を確認
- describe_table: テーブル構造とサンプルデータを確認
- query_database: データベースにSELECTクエリを実行

作業手順:
1. まずlist_filesとlist_tablesで利用可能なデータを確認する
2. 必要に応じてファイルを読み取り、DBを照会する
3. ファイルとDBのデータを突き合わせて分析する
4. 結果をわかりやすく報告する

ルール:
- SELECTクエリのみ実行可能。データの変更はできません。
- 指定フォルダ外のファイルにはアクセスできません。
- 数字を勝手に丸めたり盛ったりしない。
- 報告書のたたき台を求められたら、markdown形式で出す。
"""


def calc_cost(usage, model_info):
    """トークン使用量からコストを概算"""
    input_cost = usage.input_tokens * (model_info["input_per_mtok"] / 1_000_000)
    output_cost = usage.output_tokens * (model_info["output_per_mtok"] / 1_000_000)
    total_usd = input_cost + output_cost
    return {
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "input_usd": input_cost,
        "output_usd": output_cost,
        "total_usd": total_usd,
        "total_jpy": total_usd * JPY_RATE,
    }


# === Streamlit UI ===
st.set_page_config(page_title="在庫照会エージェント", page_icon="📦", layout="wide")
st.title("📦 在庫照会エージェント")
st.caption("ファイル（CSV）× データベース（SQLite）を横断して回答する Tool use デモ")

# --- サイドバー ---
with st.sidebar:
    st.header("🔑 APIキー")
    api_key = st.text_input(
        "Anthropic API Key",
        type="password",
        placeholder="sk-ant-...",
        help="入力したキーはこのセッション内のみ使用。サーバーに保存しません。",
    )

    st.divider()
    st.header("🤖 モデル選択")
    model_name = st.selectbox("モデル", list(MODELS.keys()), index=0)
    model_info = MODELS[model_name]
    st.caption(
        f"モデルID: `{model_info['id']}`\n\n"
        f"入力: ${model_info['input_per_mtok']:.2f}/MTok　"
        f"出力: ${model_info['output_per_mtok']:.2f}/MTok"
    )

    st.divider()
    st.header("📋 ツール一覧")
    st.markdown("""
| # | ツール | 対象 |
|---|--------|------|
| 1 | list_files | ファイル一覧 |
| 2 | read_file | CSV読み取り |
| 3 | list_tables | DBテーブル一覧 |
| 4 | describe_table | テーブル構造 |
| 5 | query_database | SELECT実行 |
    """)

    st.divider()
    st.header("🔒 安全設計")
    st.markdown("""
- DB: SELECT限定
- ファイル: 指定フォルダ外不可
- 入力: 文字数制限あり
- ループ: 最大15ターン
    """)

    st.divider()
    st.header("💰 累計コスト")
    tc = st.session_state.get("total_cost", {
        "input_tokens": 0, "output_tokens": 0,
        "input_usd": 0, "output_usd": 0,
        "total_usd": 0, "total_jpy": 0,
    })
    st.metric("累計（税抜概算）", f"¥{tc['total_jpy']:.2f}")
    col1, col2 = st.columns(2)
    col1.metric("入力", f"{tc['input_tokens']:,} tok", f"${tc['input_usd']:.4f}")
    col2.metric("出力", f"{tc['output_tokens']:,} tok", f"${tc['output_usd']:.4f}")
    st.caption(f"合計 ${tc['total_usd']:.4f}（1USD={JPY_RATE}円換算）")

    if st.button("🗑️ コストリセット"):
        st.session_state.total_cost = {
            "input_tokens": 0, "output_tokens": 0,
            "input_usd": 0, "output_usd": 0,
            "total_usd": 0, "total_jpy": 0,
        }
        st.rerun()

# --- デモ質問ボタン ---
st.markdown("**💡 デモ質問：**")
demo_cols = st.columns(2)
demo_prompts = [
    "どんなデータがありますか？",
    "在庫が安全在庫を下回っている品目は？",
    "先月の発注CSVと在庫を突き合わせて、欠品リスク品目を出して",
    "発注実績と在庫を突き合わせて、月次報告のたたき台をmarkdownで作って",
]
for i, p in enumerate(demo_prompts):
    if demo_cols[i % 2].button(p, key=f"demo_{i}", use_container_width=True):
        st.session_state["demo_input"] = p

st.divider()

# --- セッション初期化 ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "total_cost" not in st.session_state:
    st.session_state.total_cost = {
        "input_tokens": 0, "output_tokens": 0,
        "input_usd": 0, "output_usd": 0,
        "total_usd": 0, "total_jpy": 0,
    }

# --- チャット履歴表示 ---
for msg in st.session_state.messages:
    if msg["role"] == "user":
        with st.chat_message("user"):
            st.write(msg["content"])
    elif msg["role"] == "assistant_text":
        with st.chat_message("assistant"):
            st.write(msg["content"])
    elif msg["role"] == "tool_log":
        with st.chat_message("assistant"):
            with st.expander(f"🔧 {msg['tool_name']}", expanded=False):
                if msg.get("input"):
                    st.code(json.dumps(msg["input"], ensure_ascii=False, indent=2), language="json")
                st.text(msg["result"][:2000])
    elif msg["role"] == "cost_log":
        with st.chat_message("assistant"):
            st.caption(msg["text"])


def run_agent(user_input: str):
    """Claude API + Tool useでエージェント実行"""
    if not api_key:
        st.error("⚠️ サイドバーでAPIキーを入力してください。")
        return

    client = anthropic.Anthropic(api_key=api_key)

    # API用メッセージ履歴を構築
    api_messages = []
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            api_messages.append({"role": "user", "content": msg["content"]})
        elif msg["role"] == "api_raw":
            api_messages.append(msg["data"])

    api_messages.append({"role": "user", "content": user_input})

    turn_count = 0
    turn_input_tokens = 0
    turn_output_tokens = 0

    while turn_count < MAX_TURNS:
        turn_count += 1

        try:
            response = client.messages.create(
                model=model_info["id"],
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                tools=TOOL_DEFINITIONS,
                messages=api_messages,
            )
        except anthropic.AuthenticationError:
            st.error("⚠️ APIキーが無効です。正しいキーを入力してください。")
            return
        except anthropic.APIError as e:
            st.error(f"⚠️ API エラー: {e}")
            return

        # トークン集計
        turn_input_tokens += response.usage.input_tokens
        turn_output_tokens += response.usage.output_tokens

        # レスポンス解析
        assistant_content = response.content
        has_tool_use = any(block.type == "tool_use" for block in assistant_content)

        # テキスト表示
        for block in assistant_content:
            if block.type == "text" and block.text.strip():
                with st.chat_message("assistant"):
                    st.write(block.text)
                st.session_state.messages.append(
                    {"role": "assistant_text", "content": block.text}
                )

        # API履歴にassistantメッセージを追加
        raw_assistant = {
            "role": "assistant",
            "content": [
                {"type": b.type, "text": b.text} if b.type == "text"
                else {"type": "tool_use", "id": b.id, "name": b.name, "input": b.input}
                for b in assistant_content
            ],
        }
        api_messages.append(raw_assistant)
        st.session_state.messages.append({"role": "api_raw", "data": raw_assistant})

        if response.stop_reason == "end_turn" or not has_tool_use:
            break

        # ツール実行
        tool_results = []
        for block in assistant_content:
            if block.type == "tool_use":
                with st.chat_message("assistant"):
                    with st.expander(f"🔧 {block.name}", expanded=True):
                        if block.input:
                            st.code(
                                json.dumps(block.input, ensure_ascii=False, indent=2),
                                language="json",
                            )
                        with st.spinner("実行中..."):
                            result = execute_tool(block.name, block.input)
                        st.text(result[:2000])

                st.session_state.messages.append({
                    "role": "tool_log",
                    "tool_name": block.name,
                    "input": block.input,
                    "result": result,
                })
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })

        tool_msg = {"role": "user", "content": tool_results}
        api_messages.append(tool_msg)
        st.session_state.messages.append({"role": "api_raw", "data": tool_msg})

    if turn_count >= MAX_TURNS:
        with st.chat_message("assistant"):
            st.warning(f"⚠️ 最大ターン数（{MAX_TURNS}）に達しました。")

    # --- 今回のコスト表示 ---
    input_cost = turn_input_tokens * (model_info["input_per_mtok"] / 1_000_000)
    output_cost = turn_output_tokens * (model_info["output_per_mtok"] / 1_000_000)
    total_usd = input_cost + output_cost
    total_jpy = total_usd * JPY_RATE

    cost_text = (
        f"📊 今回のコスト: "
        f"入力 {turn_input_tokens:,}tok (${input_cost:.4f}) + "
        f"出力 {turn_output_tokens:,}tok (${output_cost:.4f}) = "
        f"**${total_usd:.4f}（約¥{total_jpy:.2f}）** "
        f"[{model_name}]"
    )
    with st.chat_message("assistant"):
        st.caption(cost_text)
    st.session_state.messages.append({"role": "cost_log", "text": cost_text})

    # 累計に加算
    tc = st.session_state.total_cost
    tc["input_tokens"] += turn_input_tokens
    tc["output_tokens"] += turn_output_tokens
    tc["input_usd"] += input_cost
    tc["output_usd"] += output_cost
    tc["total_usd"] += total_usd
    tc["total_jpy"] += total_jpy


# --- 入力処理 ---
demo_input = st.session_state.pop("demo_input", None)
if demo_input:
    st.session_state.messages.append({"role": "user", "content": demo_input})
    with st.chat_message("user"):
        st.write(demo_input)
    run_agent(demo_input)
    st.rerun()

user_input = st.chat_input("質問を入力...")
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)
    run_agent(user_input)
    st.rerun()
