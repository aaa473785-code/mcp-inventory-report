# mcp-inventory-report

**ファイル × DB 横断 在庫照会エージェント PoC**

ローカルのCSVファイルとSQLiteデータベースを横断して、在庫照会・欠品分析・月次報告のたたき台生成を行うAIエージェントのデモ。

## デモシナリオ

> 「先月の発注CSVと在庫DBを突き合わせて、欠品リスク品目を出して、月次報告のたたき台をmarkdownで作って」

1つの質問で、AIが自律的にファイル読み取り→DB照会→突き合わせ→報告書生成を実行する。

## 構成

```
ユーザー（ブラウザ）
  ↓ 質問
Streamlit チャットUI
  ↓ Tool use
Claude API（Haiku）
  ├── Tool①: ファイル読み取り（CSV/Excel）
  ├── Tool②: DB照会（SQLite SELECT限定）
  └── 報告書をmarkdownで生成
```

## ツール一覧（5本）

| # | ツール | 機能 | 対象 |
|---|--------|------|------|
| 1 | list_files | ファイル一覧取得 | 指定フォルダ |
| 2 | read_file | CSV/テキスト読み取り | 指定フォルダ内ファイル |
| 3 | list_tables | テーブル一覧取得 | SQLite（4テーブル） |
| 4 | describe_table | テーブル構造確認 | SQLite |
| 5 | query_database | SELECTクエリ実行 | SQLite |

## 安全設計

| 項目 | 実装 |
|------|------|
| DB書き込み防止 | SELECT文のみ許可（INSERT/UPDATE/DELETE/DROPは正規表現で遮断） |
| ファイルアクセス制限 | 指定フォルダ外はパストラバーサル防止で遮断 |
| 入力長制限 | ファイル名500文字、クエリ1000文字 |
| 結果件数制限 | 最大100件で打ち切り |
| ループ防止 | 最大15ターンで強制停止 |

## MCP（Model Context Protocol）との関係

このPoCはTool useでファイルとDBの繋ぎ口を実装している。
ツール定義をMCPサーバーとして切り出せば、Claude Desktop・Copilot Studio・Slackボットなど複数クライアントから同じ繋ぎ口で叩ける。

**Tool use = アプリ内閉じ、MCP = 繋ぎ口の標準化（AIのUSB-C）**

## セットアップ

```bash
# 依存パッケージ
pip install -r requirements.txt

# デモDBの作成
python setup_db.py

# APIキー設定（PowerShell）
$env:ANTHROPIC_API_KEY = "sk-ant-..."

# 起動
streamlit run app.py
```

## デモデータ

- **SQLite**: 商品（10品目）・在庫・取引先（4社）・**発注（16件、4〜5月）**
- **CSV**: 発注実績_2026年5月.csv（11件、納品済/遅延/未納品のステータス混在）
- 在庫が安全在庫を下回る品目（P002, P004, P008）を意図的に設定済み
- 遅延1件（P002）、未納品2件（P004, P007）を仕込み済み

## モデル選択とコスト表示

画面のサイドバーでモデルを切り替えられる。コストはリアルタイム概算（1USD=150円）。

| モデル | モデルID | 入力 $/MTok | 出力 $/MTok | 特徴 |
|--------|---------|------------|------------|------|
| Haiku 4.5 | claude-haiku-4-5-20251001 | $1 | $5 | 高速・低コスト |
| Sonnet 4.6 | claude-sonnet-4-6 | $3 | $15 | バランス型 |
| Opus 4.8 | claude-opus-4-8 | $5 | $25 | 高品質 |
| Fable 5 | claude-fable-5 | $10 | $50 | 最上位（Mythos-class） |

APIキーはサイドバーから入力。セッション内のみ使用し、サーバーに保存しない。

## 技術スタック

- Python / Streamlit
- Anthropic API（Claude Haiku 4.5 / Tool use）
- SQLite
- 外部ベクトルDB・LangChain不使用（PoCの最小構成）

## ポートフォリオとしての位置づけ

| # | リポジトリ | 型 | 見せるもの |
|---|-----------|-----|-----------|
| 1 | helpdesk-rag-bot | RAG（文書Q&A） | 検索精度・ハルシネーション対策・コスト |
| 2 | ai-readiness-check | セルフチェック＋RAGデモ | 技術ON/OFF切替・理想vs現実 |
| 3 | ai-agent-db | エージェント（DB照会） | Tool use・順次実行・安全設計 |
| 4 | **mcp-inventory-report** | **横断エージェント（ファイル×DB）** | **複数データソース横断・報告書生成・MCP設計思想** |
