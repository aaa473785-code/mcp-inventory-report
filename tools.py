"""Tool定義と実行（ファイル読み取り2本 + DB照会3本）"""
import csv
import os
import re
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "demo.db")
DATA_DIR = os.path.join(os.path.dirname(__file__), "sample_data")

# === Anthropic API用ツール定義 ===

TOOL_DEFINITIONS = [
    {
        "name": "list_files",
        "description": "指定フォルダ内のファイル一覧を返す。Excel(.xlsx)やCSV(.csv)が対象。",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "read_file",
        "description": "指定したファイル名のCSV/テキストファイルを読み取り、内容を返す。",
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "読み取るファイル名（例: 発注実績_2026年5月.csv）",
                }
            },
            "required": ["filename"],
        },
    },
    {
        "name": "list_tables",
        "description": "データベース内のテーブル一覧を返す。",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "describe_table",
        "description": "指定テーブルのカラム情報とサンプルデータ（3件）を返す。",
        "input_schema": {
            "type": "object",
            "properties": {
                "table_name": {
                    "type": "string",
                    "description": "テーブル名（例: products）",
                }
            },
            "required": ["table_name"],
        },
    },
    {
        "name": "query_database",
        "description": "SQLiteデータベースにSELECTクエリを実行して結果を返す。SELECT文のみ許可。",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "実行するSQLクエリ（SELECT文のみ）",
                }
            },
            "required": ["query"],
        },
    },
]

# === 安全チェック ===

ALLOWED_TABLES = {"suppliers", "products", "inventory", "orders"}
MAX_INPUT_LEN = 500
MAX_QUERY_LEN = 1000
MAX_ROWS = 100


def _validate_table_name(name: str) -> str | None:
    if name not in ALLOWED_TABLES:
        return f"エラー: テーブル '{name}' は存在しないか許可されていません。許可テーブル: {', '.join(sorted(ALLOWED_TABLES))}"
    return None


def _validate_select_only(query: str) -> str | None:
    q = query.strip().upper()
    if not q.startswith("SELECT"):
        return "エラー: SELECT文のみ許可されています。"
    dangerous = re.compile(
        r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|ATTACH|DETACH|PRAGMA)\b",
        re.IGNORECASE,
    )
    if dangerous.search(query):
        return "エラー: 書き込み・変更系のSQL文は実行できません。"
    return None


# === ツール実行 ===


def execute_tool(tool_name: str, tool_input: dict) -> str:
    try:
        if tool_name == "list_files":
            return _list_files()
        elif tool_name == "read_file":
            return _read_file(tool_input.get("filename", ""))
        elif tool_name == "list_tables":
            return _list_tables()
        elif tool_name == "describe_table":
            return _describe_table(tool_input.get("table_name", ""))
        elif tool_name == "query_database":
            return _query_database(tool_input.get("query", ""))
        else:
            return f"エラー: 不明なツール '{tool_name}'"
    except Exception as e:
        return f"エラー: {type(e).__name__}: {e}"


def _list_files() -> str:
    if not os.path.isdir(DATA_DIR):
        return "エラー: データフォルダが見つかりません。"
    files = os.listdir(DATA_DIR)
    if not files:
        return "ファイルがありません。"
    lines = ["ファイル一覧:"]
    for f in sorted(files):
        size = os.path.getsize(os.path.join(DATA_DIR, f))
        lines.append(f"  - {f} ({size:,} bytes)")
    return "\n".join(lines)


def _read_file(filename: str) -> str:
    if len(filename) > MAX_INPUT_LEN:
        return "エラー: ファイル名が長すぎます。"
    # パストラバーサル防止
    if ".." in filename or "/" in filename or "\\" in filename:
        return "エラー: 不正なファイル名です。"
    filepath = os.path.join(DATA_DIR, filename)
    if not os.path.isfile(filepath):
        return f"エラー: ファイル '{filename}' が見つかりません。"

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    # 上限チェック（巨大ファイル防止）
    if len(content) > 50000:
        content = content[:50000] + "\n...(以降省略)"
    return f"ファイル '{filename}' の内容:\n{content}"


def _list_tables() -> str:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in c.fetchall()]
    conn.close()
    if not tables:
        return "テーブルがありません。"
    return "テーブル一覧: " + ", ".join(tables)


def _describe_table(table_name: str) -> str:
    if len(table_name) > MAX_INPUT_LEN:
        return "エラー: テーブル名が長すぎます。"
    err = _validate_table_name(table_name)
    if err:
        return err

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(f"PRAGMA table_info({table_name})")
    columns = c.fetchall()
    col_info = "\n".join(
        [f"  {col[1]} ({col[2]}){' PRIMARY KEY' if col[5] else ''}" for col in columns]
    )
    c.execute(f"SELECT * FROM {table_name} LIMIT 3")
    rows = c.fetchall()
    col_names = [col[1] for col in columns]
    sample = "\n".join(
        ["  " + " | ".join(str(v) for v in row) for row in rows]
    )
    conn.close()
    return f"テーブル '{table_name}' のカラム:\n{col_info}\n\nサンプルデータ（3件）:\n  {' | '.join(col_names)}\n{sample}"


def _query_database(query: str) -> str:
    if len(query) > MAX_QUERY_LEN:
        return "エラー: クエリが長すぎます（上限1000文字）。"
    err = _validate_select_only(query)
    if err:
        return err

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(query)
    columns = [desc[0] for desc in c.description] if c.description else []
    rows = c.fetchmany(MAX_ROWS)
    conn.close()

    if not rows:
        return "結果: 0件"
    header = " | ".join(columns)
    body = "\n".join(["  " + " | ".join(str(v) for v in row) for row in rows])
    result = f"結果: {len(rows)}件\n  {header}\n{body}"
    if len(rows) == MAX_ROWS:
        result += f"\n  （{MAX_ROWS}件で打ち切り）"
    return result
